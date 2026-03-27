from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class OpsLogStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    status TEXT NOT NULL,
                    job_id TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "operations", "job_id", "TEXT")
            conn.commit()

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "OpsLogStore":
        return cls(data_dir / "admin_ops.db")

    @staticmethod
    def new_job_id() -> str:
        return str(uuid.uuid4())

    def record(
        self,
        *,
        action: str,
        target: str,
        actor: str,
        status: str,
        detail: str | None = None,
        job_id: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operations (action, target, actor, status, job_id, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (action, target, actor, status, job_id, detail, _utc_iso()),
            )
            conn.commit()

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, action, target, actor, status, job_id, detail, created_at
                FROM operations
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "action": row[1],
                "target": row[2],
                "actor": row[3],
                "status": row[4],
                "job_id": row[5],
                "detail": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        existing = {str(row[1]) for row in cursor.fetchall()}
        if column in existing:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
