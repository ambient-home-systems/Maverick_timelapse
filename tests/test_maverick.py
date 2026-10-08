import asyncio
import io
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import yaml
from PIL import Image
from pydantic import ValidationError

from app.camera import HomeAssistant
from app.engine import Engine, capture_error, write_frame
from app.main import create_app
from app.models import JobCreate

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-Maverick-Request": "1"}


def image_bytes(color="red", size=(320, 240)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


class FakeCamera:
    def __init__(self):
        self.calls = 0
        self.error = None

    async def cameras(self):
        return [{"entity_id": "camera.garden", "name": "Garden", "state": "idle"}]

    async def snapshot(self, entity_id):
        self.calls += 1
        if self.error:
            raise self.error
        return image_bytes("red" if self.calls % 2 else "blue")

    async def close(self):
        pass


class ConfigurationTests(unittest.TestCase):
    def test_discoverable_repository_and_architectures(self):
        repository = yaml.safe_load((ROOT / "repository.yaml").read_text())
        config = yaml.safe_load((ROOT / "maverick_timelapse/config.yaml").read_text())
        dockerfile = (ROOT / "maverick_timelapse/Dockerfile").read_text()
        self.assertEqual(repository["url"], config["url"])
        self.assertEqual(set(config["arch"]), {"amd64", "aarch64"})
        self.assertIn('io.hass.type="app"', dockerfile)
        self.assertIn('ARG BUILD_VERSION=' + config["version"], dockerfile)
        self.assertIn('FROM python:3.12-slim-bookworm@sha256:', dockerfile)
        self.assertTrue(config["homeassistant_api"])
        self.assertTrue(config["ingress"])
        self.assertNotIn("ports", config)
        self.assertIn("redirect/supervisor_add_addon_repository/", (ROOT / "README.md").read_text())

    def test_invalid_and_naive_schedules_are_rejected(self):
        for change in ({"camera": "../../private"}, {"interval_seconds": 0},
                       {"start_at": datetime.now()}, {"start_at": datetime.now(timezone.utc) - timedelta(days=1)},
                       {"duration_minutes": 43200, "interval_seconds": 5}, {"name": "   "}):
            values = {"name": "Garden", "camera": "camera.garden", **change}
            with self.subTest(change=change), self.assertRaises(ValidationError):
                JobCreate(**values)


class CameraTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_paths_authentication_discovery_and_snapshot(self):
        requests = []

        def handle(request):
            requests.append(request)
            if request.url.path.endswith("states"):
                return httpx.Response(200, json=[
                    {"entity_id": "sensor.other", "state": "1", "attributes": {}},
                    {"entity_id": "camera.garden", "state": "idle", "attributes": {"friendly_name": "Garden"}},
                ])
            return httpx.Response(200, content=image_bytes(), headers={"content-type": "image/png"})

        camera = HomeAssistant("http://supervisor/core/api", "test-only-token")
        await camera.client.aclose()
        camera.client = httpx.AsyncClient(base_url="http://supervisor/core/api/",
                                        headers={"Authorization": "Bearer test-only-token"},
                                        transport=httpx.MockTransport(handle))
        try:
            self.assertEqual((await camera.cameras())[0]["entity_id"], "camera.garden")
            self.assertEqual(await camera.snapshot("camera.garden"), image_bytes())
            self.assertEqual([request.url.path for request in requests],
                             ["/core/api/states", "/core/api/camera_proxy/camera.garden"])
            self.assertTrue(all(request.headers["authorization"] == "Bearer test-only-token" for request in requests))
        finally:
            await camera.close()

    async def test_error_responses_are_not_images(self):
        camera = HomeAssistant("http://example.test/api", "test")
        await camera.client.aclose()
        camera.client = httpx.AsyncClient(base_url="http://example.test/api/",
                                         transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>error</html>")))
        try:
            with self.assertRaises(ValueError):
                await camera.snapshot("camera.garden")
        finally:
            await camera.close()

    def test_http_errors_do_not_expose_credentials(self):
        request = httpx.Request("GET", "http://example.test/secret-token")
        error = httpx.HTTPStatusError("secret-token", request=request, response=httpx.Response(403, request=request))
        message = capture_error(error)
        self.assertIn("403", message)
        self.assertNotIn("secret-token", message)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name)
        self.camera = FakeCamera()
        self.engine = Engine(self.data, self.camera, 1, True)

    async def asyncTearDown(self):
        await self.engine.close()
        self.temporary.cleanup()

    def new_job(self, **changes):
        return self.engine.create(JobCreate(name="Garden", camera="camera.garden", **changes))

    async def drain(self):
        await asyncio.gather(*list(self.engine.tasks.values()))
        await asyncio.sleep(0)

    async def test_capture_normalizes_images_and_persists_counts(self):
        job = self.new_job()
        await self.engine.capture(job)
        frame = self.engine.directory(job.id) / "frames/00000000.jpg"
        with Image.open(frame) as image:
            self.assertEqual(image.format, "JPEG")
        self.assertEqual(self.engine.store.all()[0].frames, 1)
        self.assertFalse(list(frame.parent.glob("*.tmp")))

    async def test_capture_failure_is_counted_and_next_capture_recovers(self):
        job = self.new_job()
        self.camera.error = httpx.ReadTimeout("camera down")
        await self.engine.capture(job)
        self.assertEqual((job.frames, job.errors), (0, 1))
        self.assertIn("timed out", job.last_error)
        self.camera.error = None
        await self.engine.capture(job)
        self.assertEqual((job.frames, job.errors), (1, 1))
        self.assertIsNone(job.last_error)

    async def test_storage_limit_stops_capture_without_writing_frame(self):
        job = self.new_job()
        with patch.object(self.engine, "has_space", AsyncMock(return_value=False)):
            await self.engine.capture(job)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.frames, 0)

    async def test_scheduled_job_waits_and_cadence_does_not_catch_up(self):
        job = self.new_job(start_at=datetime.now(timezone.utc) + timedelta(hours=1))
        await self.engine.tick()
        self.assertEqual(self.camera.calls, 0)
        job.start_at = time.time() - 125
        job.end_at = time.time() + 60
        job.next_capture = job.start_at
        await self.engine.tick()
        await self.drain()
        self.assertEqual(self.camera.calls, 1)
        self.assertGreater(job.next_capture, time.time())
        await self.engine.tick()
        await self.drain()
        self.assertEqual(self.camera.calls, 1)

    async def test_inflight_capture_is_not_launched_twice(self):
        job = self.new_job()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def slow_snapshot(entity_id):
            entered.set()
            await release.wait()
            return image_bytes()

        self.camera.snapshot = slow_snapshot
        await self.engine.tick()
        await entered.wait()
        job.next_capture = 0
        await self.engine.tick()
        self.assertEqual(len(self.engine.tasks), 1)
        release.set()
        await self.drain()
        self.assertEqual(job.frames, 1)

    async def test_finish_waits_for_pending_snapshot(self):
        job = self.new_job()
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_snapshot(entity_id):
            entered.set()
            await release.wait()
            return image_bytes()

        self.camera.snapshot = slow_snapshot
        await self.engine.tick()
        await entered.wait()
        finish = asyncio.create_task(self.engine.finish(job))
        await asyncio.sleep(0)
        self.assertFalse(finish.done())
        release.set()
        await finish
        self.assertEqual(job.frames, 1)
        self.assertEqual(job.status, "rendering")

    async def test_active_job_limit_and_deletion_guard(self):
        for _ in range(8):
            self.new_job()
        with self.assertRaises(ValueError):
            self.new_job()
        with self.assertRaises(ValueError):
            await self.engine.delete(next(iter(self.engine.jobs.values())))

    async def test_empty_job_fails_instead_of_creating_empty_video(self):
        job = self.new_job()
        await self.engine.finish(job)
        await self.engine.render(job)
        self.assertEqual(job.status, "failed")
        self.assertIn("No snapshots", job.last_error)

    async def test_restart_reconciles_frame_written_before_database_commit(self):
        job = self.new_job(start_at=datetime.now(timezone.utc) + timedelta(hours=1))
        write_frame(image_bytes(), self.engine.directory(job.id) / "frames/00000000.jpg")
        await self.engine.close()
        self.engine = Engine(self.data, self.camera, 1, True)
        await self.engine.start()
        self.assertEqual(self.engine.jobs[job.id].frames, 1)
        self.assertEqual(self.engine.store.all()[0].frames, 1)

    async def test_restart_rejects_missing_frame_sequence(self):
        job = self.new_job()
        write_frame(image_bytes(), self.engine.directory(job.id) / "frames/00000002.jpg")
        await self.engine.close()
        self.engine = Engine(self.data, self.camera, 1, True)
        await self.engine.start()
        self.assertEqual(self.engine.jobs[job.id].status, "failed")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
    async def test_real_video_generation_retention_and_deletion(self):
        job = self.new_job()
        for _ in range(3):
            await self.engine.capture(job)
        await self.engine.finish(job)
        self.engine.keep_snapshots = False
        await self.engine.render(job)
        self.assertEqual(job.status, "completed", job.last_error)
        video = self.engine.directory(job.id) / "video.mp4"
        result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)],
                                text=True, capture_output=True, check=True)
        stream = json.loads(result.stdout)["streams"][0]
        self.assertEqual((stream["codec_name"], stream["width"], stream["height"], stream["nb_frames"]),
                         ("h264", 1920, 1080, "3"))
        self.assertFalse((video.parent / "frames").exists())
        await self.engine.delete(job)
        self.assertFalse(video.parent.exists())
        self.assertEqual(self.engine.store.all(), [])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
    async def test_expired_job_renders_after_restart(self):
        job = self.new_job()
        await self.engine.capture(job)
        job.end_at = time.time() - 1
        self.engine.store.save(job)
        await self.engine.close()
        self.engine = Engine(self.data, self.camera, 1, True)
        await self.engine.start()
        await self.engine.tick()
        await self.drain()
        restored = self.engine.jobs[job.id]
        self.assertEqual(restored.status, "completed", restored.last_error)
        self.assertTrue((self.engine.directory(job.id) / "frames/00000000.jpg").exists())

    async def test_render_storage_failure_can_retry_with_retained_frames(self):
        job = self.new_job()
        await self.engine.capture(job)
        with patch.object(self.engine, "has_space", AsyncMock(return_value=False)):
            await self.engine.render(job)
        self.assertEqual(job.status, "failed")
        self.assertTrue((self.engine.directory(job.id) / "frames/00000000.jpg").exists())
        await self.engine.retry_render(job)
        self.assertEqual(job.status, "rendering")

    async def test_real_storage_budget_and_invalid_image(self):
        self.engine.max_bytes = 1
        self.assertFalse(await self.engine.has_space())
        self.engine.max_bytes = 1024**3
        job = self.new_job()
        self.camera.snapshot = AsyncMock(return_value=b"not an image")
        await self.engine.capture(job)
        self.assertEqual((job.frames, job.errors), (0, 1))
        self.assertFalse(list((self.engine.directory(job.id) / "frames").glob("*")))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
    async def test_corrupt_frame_render_failure_keeps_source_and_logs_diagnosis(self):
        job = self.new_job()
        frame = self.engine.directory(job.id) / "frames/00000000.jpg"
        frame.write_bytes(b"invalid JPEG")
        job.frames = 1
        await self.engine.finish(job)
        with self.assertLogs("app.engine", level="WARNING") as logs:
            await self.engine.render(job)
        self.assertEqual(job.status, "failed")
        self.assertTrue(frame.exists())
        self.assertFalse((frame.parent.parent / "rendering.mp4").exists())
        self.assertTrue(any("FFmpeg failed" in line for line in logs.output))


class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.application = create_app(Path(self.temporary.name), FakeCamera(), development=True)
        self.lifespan = self.application.router.lifespan_context(self.application)
        await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.application), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.temporary.cleanup()

    async def test_index_cameras_health_and_storage(self):
        index = await self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("./static/app.js", index.text)
        self.assertEqual((await self.client.get("/health")).json(), {"ready": True})
        self.assertEqual((await self.client.get("/api/cameras")).json()[0]["entity_id"], "camera.garden")
        self.assertEqual((await self.client.get("/api/status")).json()["limit_bytes"], 10 * 1024**3)

    async def test_create_list_finish_delete_and_validation(self):
        payload = {"name": "Garden", "camera": "camera.garden",
                   "start_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        self.assertEqual((await self.client.post("/api/jobs", json=payload)).status_code, 403)
        result = await self.client.post("/api/jobs", json=payload, headers=HEADERS)
        self.assertEqual(result.status_code, 201)
        job_id = result.json()["id"]
        self.assertEqual(len((await self.client.get("/api/jobs")).json()), 1)
        self.assertEqual((await self.client.delete(f"/api/jobs/{job_id}", headers=HEADERS)).status_code, 409)
        self.assertEqual((await self.client.get(f"/api/jobs/{job_id}/video")).status_code, 404)
        await self.client.post(f"/api/jobs/{job_id}/finish", headers=HEADERS)
        engine = self.application.state.engine
        await engine.tick()
        await asyncio.gather(*list(engine.tasks.values()))
        await asyncio.sleep(0)
        self.assertEqual((await self.client.delete(f"/api/jobs/{job_id}", headers=HEADERS)).status_code, 204)
        self.assertEqual((await self.client.post("/api/jobs", json={**payload, "camera": "../secret"}, headers=HEADERS)).status_code, 422)

    async def test_unknown_job_paths_are_not_filesystem_paths(self):
        self.assertEqual((await self.client.get("/api/jobs/not-a-job/snapshot")).status_code, 404)

    async def test_production_only_accepts_supervisor_ingress_and_local_health(self):
        app = create_app(Path(self.temporary.name), FakeCamera(), development=False)
        # Use the running test engine while exercising the production request boundary.
        app.state.engine = self.application.state.engine
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.168.1.5", 1234)), base_url="http://test") as outside:
            self.assertEqual((await outside.get("/api/jobs")).status_code, 403)
            self.assertEqual((await outside.get("/health")).status_code, 403)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)), base_url="http://test") as local:
            self.assertEqual((await local.get("/api/jobs")).status_code, 403)
            self.assertEqual((await local.get("/health")).status_code, 200)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("172.30.32.2", 1234)), base_url="http://test") as ingress:
            self.assertEqual((await ingress.get("/api/jobs")).status_code, 200)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
    async def test_video_playback_range_and_download(self):
        engine = self.application.state.engine
        job = engine.create(JobCreate(name="Garden", camera="camera.garden",
                                     start_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        await engine.capture(job)
        await engine.finish(job)
        await engine.render(job)
        self.assertEqual(job.status, "completed", job.last_error)
        video = await self.client.get(f"/api/jobs/{job.id}/video", headers={"Range": "bytes=0-99"})
        self.assertEqual(video.status_code, 206)
        self.assertEqual(len(video.content), 100)
        download = await self.client.get(f"/api/jobs/{job.id}/video?download=true")
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertEqual(download.headers["content-type"], "video/mp4")


if __name__ == "__main__":
    unittest.main()
