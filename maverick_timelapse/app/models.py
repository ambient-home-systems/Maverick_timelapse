from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    camera: str = Field(pattern=r"^camera\.[a-z0-9_]+$")
    interval_seconds: int = Field(default=30, ge=5, le=86400)
    duration_minutes: int = Field(default=60, ge=1, le=43200)
    fps: int = Field(default=30, ge=1, le=60)
    start_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Give the timelapse a name.")
        if self.start_at is not None:
            if self.start_at.tzinfo is None:
                raise ValueError("The start time must include a timezone.")
            if self.start_at < utcnow():
                raise ValueError("The start time must be in the future.")
        if self.duration_minutes * 60 / self.interval_seconds > 100000:
            raise ValueError("Use a longer interval: a job can capture at most 100,000 frames.")
        return self


class Job(BaseModel):
    id: str
    name: str
    camera: str
    interval_seconds: int
    fps: int
    start_at: float
    end_at: float
    next_capture: float
    status: Literal["scheduled", "capturing", "rendering", "completed", "failed"]
    frames: int = 0
    errors: int = 0
    last_error: str | None = None
    created_at: float
    completed_at: float | None = None
    video_bytes: int = 0
