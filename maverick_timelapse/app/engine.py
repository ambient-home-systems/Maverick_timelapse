import asyncio
import io
import logging
import math
import shutil
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageOps

from .camera import HomeAssistant
from .models import Job, JobCreate
from .store import Store

LOGGER = logging.getLogger(__name__)
ACTIVE = {"scheduled", "capturing", "rendering"}
DISK_RESERVE = 256 * 1024 * 1024


def storage_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except FileNotFoundError:
            pass
    return total


def write_frame(raw: bytes, target: Path):
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("The camera image exceeds 40 megapixels.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1920, 1080))
        temporary = target.with_suffix(".tmp")
        try:
            image.save(temporary, format="JPEG", quality=90)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def capture_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"Home Assistant returned HTTP {error.response.status_code}. Check the camera entity and app API access."
    if isinstance(error, httpx.TimeoutException):
        return "The camera request timed out. Capture will retry at the next interval."
    if isinstance(error, httpx.RequestError):
        return "Could not reach Home Assistant. Capture will retry at the next interval."
    if isinstance(error, (ValueError, OSError)):
        return "Could not save a valid snapshot. Check the camera image and available storage."
    return "Snapshot capture failed. Check the app log."


class Engine:
    def __init__(self, data: Path, camera: HomeAssistant, max_storage_gb: int, keep_snapshots: bool):
        self.data = data
        self.data.mkdir(parents=True, exist_ok=True)
        self.camera = camera
        self.max_bytes = max_storage_gb * 1024**3
        self.keep_snapshots = keep_snapshots
        self.store = Store(data / "jobs.sqlite3")
        self.jobs = {job.id: job for job in self.store.all()}
        self.tasks: dict[str, asyncio.Task] = {}
        self.capture_slots = asyncio.Semaphore(2)
        self.render_slot = asyncio.Semaphore(1)
        self.storage_lock = asyncio.Lock()
        self.scheduler: asyncio.Task | None = None

    def directory(self, job_id: str) -> Path:
        # Paths are only derived from generated IDs in the persisted job registry.
        return self.data / "jobs" / job_id

    async def start(self):
        for job in self.jobs.values():
            if job.status in ACTIVE:
                frames_dir = self.directory(job.id) / "frames"
                frames = sorted(frames_dir.glob("*.jpg"))
                expected = [f"{index:08d}.jpg" for index in range(len(frames))]
                if [frame.name for frame in frames] != expected:
                    job.status = "failed"
                    job.last_error = "Stored frames are incomplete. Delete this job and create a new recording."
                else:
                    # Reconcile a snapshot written just before an interrupted database commit.
                    job.frames = len(frames)
                self.store.save(job)
        self.scheduler = asyncio.create_task(self.run())

    async def close(self):
        if self.scheduler:
            self.scheduler.cancel()
            await asyncio.gather(self.scheduler, return_exceptions=True)
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.store.close()
        await self.camera.close()

    def create(self, request: JobCreate) -> Job:
        if sum(job.status in ACTIVE for job in self.jobs.values()) >= 8:
            raise ValueError("At most eight jobs can be active. Finish a recording before adding another.")
        now = time.time()
        start = request.start_at.timestamp() if request.start_at else now
        job = Job(id=uuid.uuid4().hex, name=request.name, camera=request.camera,
                  interval_seconds=request.interval_seconds, fps=request.fps,
                  start_at=start, end_at=start + request.duration_minutes * 60,
                  next_capture=start, status="scheduled", created_at=now)
        (self.directory(job.id) / "frames").mkdir(parents=True)
        self.store.save(job)
        self.jobs[job.id] = job
        return job

    async def finish(self, job: Job):
        if job.status not in {"scheduled", "capturing"}:
            raise ValueError("Only a scheduled or capturing job can be finished.")
        # Wait for any in-flight snapshot before marking the job ready to render.
        job.end_at = time.time()
        self.store.save(job)
        task = self.tasks.get(job.id)
        if task:
            await asyncio.shield(task)
        job.status = "rendering"
        self.store.save(job)

    async def retry_render(self, job: Job):
        if job.status != "failed" or not job.frames:
            raise ValueError("Only a failed job with saved snapshots can retry video creation.")
        if sum(item.status in ACTIVE for item in self.jobs.values()) >= 8:
            raise ValueError("At most eight jobs can be active.")
        job.status = "rendering"
        job.last_error = None
        self.store.save(job)

    async def delete(self, job: Job):
        if job.status in ACTIVE or job.id in self.tasks:
            raise ValueError("Finish the job before deleting it.")
        await asyncio.to_thread(shutil.rmtree, self.directory(job.id), True)
        self.store.delete(job.id)
        del self.jobs[job.id]

    async def has_space(self, additional: int = 0) -> bool:
        used, free = await asyncio.gather(
            asyncio.to_thread(storage_bytes, self.data),
            asyncio.to_thread(lambda: shutil.disk_usage(self.data).free),
        )
        return used + additional < self.max_bytes and free - additional > DISK_RESERVE

    async def run(self):
        while True:
            await self.tick()
            await asyncio.sleep(1)

    async def tick(self):
        now = time.time()
        for job in list(self.jobs.values()):
            if job.id in self.tasks or job.status not in ACTIVE:
                continue
            if job.status in {"scheduled", "capturing"} and now >= job.end_at:
                job.status = "rendering"
                self.store.save(job)
            if job.status == "rendering":
                self.launch(job, self.render(job))
            elif now >= job.next_capture:
                job.status = "capturing"
                # Maintain the original cadence without issuing a burst after downtime.
                slots = math.floor((now - job.start_at) / job.interval_seconds) + 1
                job.next_capture = job.start_at + slots * job.interval_seconds
                self.store.save(job)
                self.launch(job, self.capture(job))

    def launch(self, job: Job, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks[job.id] = task

        def done(completed: asyncio.Task):
            self.tasks.pop(job.id, None)
            if not completed.cancelled() and completed.exception():
                LOGGER.error("Job %s failed: %s", job.id, type(completed.exception()).__name__)
                job.status = "failed"
                job.last_error = "The job encountered an unexpected error. Check the app log."
                self.store.save(job)

        task.add_done_callback(done)

    async def capture(self, job: Job):
        async with self.capture_slots:
            # A job may expire while waiting for another camera request.
            if time.time() >= job.end_at:
                return
            try:
                raw = await self.camera.snapshot(job.camera)
                async with self.storage_lock:
                    if not await self.has_space(len(raw)):
                        job.status = "failed"
                        job.last_error = "Storage limit reached. Delete older jobs or increase max_storage_gb, then retry video creation."
                        return
                    target = self.directory(job.id) / "frames" / f"{job.frames:08d}.jpg"
                    await asyncio.to_thread(write_frame, raw, target)
                    job.frames += 1
                    job.last_error = None
            except Exception as error:
                job.errors += 1
                job.last_error = capture_error(error)
                LOGGER.warning("Snapshot failed for job %s: %s", job.id, type(error).__name__)
            finally:
                self.store.save(job)

    async def render(self, job: Job):
        async with self.render_slot:
            if not job.frames:
                job.status = "failed"
                job.last_error = "No snapshots were captured. Verify the camera, then create a new job."
                self.store.save(job)
                return
            directory = self.directory(job.id)
            temporary = directory / "rendering.mp4"
            temporary.unlink(missing_ok=True)
            process = None
            try:
                if not await self.has_space():
                    raise ValueError("Insufficient storage for video creation. Delete older jobs or increase max_storage_gb.")
                with (directory / "ffmpeg.log").open("wb") as log:
                    process = await asyncio.create_subprocess_exec(
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                        "-framerate", str(job.fps), "-start_number", "0",
                        "-i", str(directory / "frames" / "%08d.jpg"),
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-threads", "2", "-filter_threads", "1", "-movflags", "+faststart",
                        str(temporary), stdout=asyncio.subprocess.DEVNULL, stderr=log,
                    )
                    while process.returncode is None:
                        try:
                            await asyncio.wait_for(process.wait(), timeout=1)
                        except asyncio.TimeoutError:
                            if not await self.has_space():
                                raise ValueError("Storage limit reached during rendering. Free storage, then retry video creation.")
                    if process.returncode:
                        LOGGER.error("FFmpeg failed for job %s: %s", job.id,
                                     (directory / "ffmpeg.log").read_text(errors="replace")[-2000:])
                        raise ValueError("FFmpeg could not create the video. Saved snapshots are available for a retry.")
                if not await self.has_space():
                    raise ValueError("Video exceeded the storage limit. Free storage, then retry video creation.")
                # A successful encoder exit is insufficient: verify that every frame made it into the output.
                probe = await asyncio.create_subprocess_exec(
                    "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                    "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(temporary),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    output, _ = await asyncio.wait_for(probe.communicate(), timeout=120)
                finally:
                    if probe.returncode is None:
                        probe.kill()
                        await probe.wait()
                if probe.returncode or output.decode().strip() != str(job.frames):
                    raise ValueError("The video did not contain all captured frames. Retry video creation.")
                temporary.replace(directory / "video.mp4")
                job.video_bytes = (directory / "video.mp4").stat().st_size
                job.completed_at = time.time()
                job.status = "completed"
                job.last_error = None
                self.store.save(job)
                if not self.keep_snapshots:
                    await asyncio.to_thread(shutil.rmtree, directory / "frames", True)
            except asyncio.CancelledError:
                # Preserve rendering status so the next startup resumes video creation.
                raise
            except (OSError, ValueError, asyncio.TimeoutError) as error:
                LOGGER.warning("Video creation failed for job %s: %s", job.id, type(error).__name__)
                job.status = "failed"
                job.last_error = str(error) if isinstance(error, ValueError) else "Video creation failed. Check FFmpeg and available storage, then retry."
                self.store.save(job)
            finally:
                if process is not None and process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                temporary.unlink(missing_ok=True)
