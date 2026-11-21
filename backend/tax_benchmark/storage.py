import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS runs_request_key "
                "ON runs(json_extract(payload, '$.request.request_key')) "
                "WHERE json_extract(payload, '$.request.request_key') IS NOT NULL"
            )

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def save(self, run: dict):
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO runs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (run["id"], json.dumps(run)),
            )

    def get(self, run_id: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def get_request_key(self, request_key: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM runs WHERE json_extract(payload, '$.request.request_key')=?",
                (request_key,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("SELECT payload FROM runs ORDER BY rowid DESC LIMIT 200").fetchall()
        return [json.loads(row[0]) for row in rows]

    def interrupt_pending(self):
        for run in self.list():
            if run["status"] in {"queued", "running"}:
                run.update(status="interrupted", updated_at=utc_now())
                self.save(run)
