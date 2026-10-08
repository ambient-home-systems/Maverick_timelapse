import asyncio
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .camera import HomeAssistant
from .engine import Engine, storage_bytes
from .models import JobCreate
from .version import APP_VERSION

STATIC = Path(__file__).parent / "static"
LOGGER = logging.getLogger(__name__)


def create_app(data_dir: Path | None = None, camera=None, development: bool | None = None) -> FastAPI:
    data = data_dir or Path(os.environ.get("MAVERICK_DATA_DIR", "/data"))
    dev = development if development is not None else os.environ.get("MAVERICK_DEV") == "1"
    index_html = (STATIC / "index.html").read_text().replace("__APP_VERSION__", APP_VERSION)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        options_path = data / "options.json"
        options = json.loads(options_path.read_text()) if options_path.exists() else {}
        limit = options.get("max_storage_gb", 10)
        keep = options.get("keep_snapshots", False)
        if type(limit) is not int or not 1 <= limit <= 1000 or type(keep) is not bool:
            raise RuntimeError("Invalid app options: check max_storage_gb and keep_snapshots.")
        token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN")
        if camera is None and not token:
            raise RuntimeError("Home Assistant API access is required. Enable homeassistant_api or set HA_TOKEN for local development.")
        connection = camera or HomeAssistant(os.environ.get("HA_API_URL", "http://supervisor/core/api"), token)
        engine = Engine(data, connection, limit, keep)
        application.state.engine = engine
        await engine.start()
        try:
            yield
        finally:
            await engine.close()

    application = FastAPI(title="Maverick Timelapse", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @application.middleware("http")
    async def ingress_only(request: Request, call_next):
        host = request.client.host if request.client else ""
        is_local = host in {"127.0.0.1", "::1"}
        if not (host == "172.30.32.2" or (is_local and (dev or request.url.path == "/health"))):
            return JSONResponse({"detail": "Open this app through Home Assistant ingress."}, status_code=403)
        if request.method in {"POST", "DELETE", "PUT", "PATCH"}:
            if request.headers.get("x-maverick-request") != "1":
                return JSONResponse({"detail": "Missing request header."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self'; media-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'self'"
        if request.url.path == "/" or request.url.path.startswith(("/api/", "/static/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_engine() -> Engine:
        return application.state.engine

    def get_job(job_id: str):
        job = get_engine().jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Timelapse not found.")
        return job

    @application.exception_handler(ValueError)
    async def invalid_request(request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @application.get("/health")
    async def health():
        engine = get_engine()
        ready = engine.scheduler is not None and not engine.scheduler.done()
        return JSONResponse({"ready": ready}, status_code=200 if ready else 503)

    @application.get("/")
    async def index():
        return HTMLResponse(index_html)

    @application.get("/api/cameras")
    async def cameras():
        try:
            return await get_engine().camera.cameras()
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(502, "Could not list cameras. Check Home Assistant API access and the app log.") from None

    @application.get("/api/status")
    async def status():
        engine = get_engine()
        used = await asyncio.to_thread(storage_bytes, engine.data)
        free = await asyncio.to_thread(lambda: shutil.disk_usage(engine.data).free)
        return {"used_bytes": used, "limit_bytes": engine.max_bytes, "free_bytes": free,
                "keep_snapshots": engine.keep_snapshots}

    @application.get("/api/jobs")
    async def jobs():
        return sorted(get_engine().jobs.values(), key=lambda job: job.created_at, reverse=True)

    @application.post("/api/jobs", status_code=201)
    async def create_job(request: JobCreate):
        if not await get_engine().has_space():
            raise HTTPException(409, "Storage limit reached. Delete older jobs before creating a recording.")
        return get_engine().create(request)

    @application.post("/api/jobs/{job_id}/finish")
    async def finish_job(job_id: str):
        job = get_job(job_id)
        await get_engine().finish(job)
        return job

    @application.post("/api/jobs/{job_id}/retry")
    async def retry_job(job_id: str):
        job = get_job(job_id)
        await get_engine().retry_render(job)
        return job

    @application.delete("/api/jobs/{job_id}", status_code=204)
    async def delete_job(job_id: str):
        await get_engine().delete(get_job(job_id))

    @application.get("/api/jobs/{job_id}/snapshot")
    async def snapshot(job_id: str):
        job = get_job(job_id)
        frame = get_engine().directory(job.id) / "frames" / f"{job.frames - 1:08d}.jpg"
        if not job.frames or not frame.is_file():
            raise HTTPException(404, "No saved snapshot is available.")
        return FileResponse(frame, media_type="image/jpeg")

    @application.get("/api/jobs/{job_id}/video")
    async def video(job_id: str, download: bool = False):
        job = get_job(job_id)
        path = get_engine().directory(job.id) / "video.mp4"
        if job.status != "completed" or not path.is_file():
            raise HTTPException(404, "This video is not available yet.")
        # FileResponse supports byte ranges for browser playback; filenames contain no user input.
        return FileResponse(path, media_type="video/mp4",
                            filename=f"maverick-{job.id}.mp4" if download else None)

    # Relative module imports inherit this release directory, so CSS, JS, and
    # imported modules all get new URLs when the installed version changes.
    application.mount(f"/static/{APP_VERSION}", StaticFiles(directory=STATIC), name="release_static")
    # Allow already-open pages from earlier releases to keep resolving assets.
    application.mount("/static", StaticFiles(directory=STATIC), name="static")
    return application


app = create_app()
