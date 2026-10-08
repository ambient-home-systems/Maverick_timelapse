import json
import sqlite3
from pathlib import Path

from .models import Job


class Store:
    """One event loop owns this connection; writes commit before returning."""

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.connection.commit()

    def save(self, job: Job):
        self.connection.execute(
            "INSERT INTO jobs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
            (job.id, job.model_dump_json()),
        )
        self.connection.commit()

    def all(self) -> list[Job]:
        return [Job.model_validate(json.loads(row[0])) for row in self.connection.execute("SELECT data FROM jobs")]

    def delete(self, job_id: str):
        self.connection.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        self.connection.commit()

    def close(self):
        self.connection.close()
