from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models.history import HistoryRecord
from utils.logger import get_logger

logger = get_logger("db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL,
    content_type TEXT    NOT NULL,
    result       TEXT    NOT NULL,
    thumbnail    BLOB,
    api_model    TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at);
CREATE INDEX IF NOT EXISTS idx_history_result ON history(result);
"""


class HistoryRepository:
    """SQLite-backed history record storage with WAL mode."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        conn.executescript(CREATE_TABLE_SQL)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
        logger.info("Database initialised at %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(
        self,
        content_type: str,
        result: str,
        thumbnail: bytes | None = None,
        api_model: str | None = None,
    ) -> int:
        """Insert a new history record and return its ID."""
        created_at = datetime.now(tz=timezone.utc).isoformat()
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO history (created_at, content_type, result, thumbnail, api_model)"
            " VALUES (?, ?, ?, ?, ?)",
            (created_at, content_type, result, thumbnail, api_model),
        )
        conn.commit()
        logger.info("History saved id=%d content_type=%s", cursor.lastrowid, content_type)
        return cursor.lastrowid or 0

    def list(self, limit: int = 50, offset: int = 0) -> list[HistoryRecord]:
        """Return paginated history records, newest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, created_at, content_type, result, thumbnail, api_model"
            " FROM history ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def get_by_id(self, record_id: int) -> HistoryRecord | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, created_at, content_type, result, thumbnail, api_model"
            " FROM history WHERE id = ?",
            (record_id,),
        ).fetchone()
        return _row_to_record(row) if row else None

    def search(self, query: str) -> list[HistoryRecord]:
        """Full-text search over result column (LIKE)."""
        conn = self._get_conn()
        pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT id, created_at, content_type, result, thumbnail, api_model"
            " FROM history WHERE result LIKE ? ORDER BY created_at DESC LIMIT 100",
            (pattern,),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def delete_expired(self, retention_days: int = 7) -> int:
        """Delete records older than retention_days. Returns count deleted."""
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=retention_days)).isoformat()
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM history WHERE created_at < ?", (cutoff,))
        conn.commit()
        count = cursor.rowcount
        if count:
            logger.info("Deleted %d expired history records", count)
        return count

    def count(self) -> int:
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]


def _row_to_record(row: sqlite3.Row) -> HistoryRecord:
    return HistoryRecord(
        id=row["id"],
        created_at=row["created_at"],
        content_type=row["content_type"],
        result=row["result"],
        thumbnail=row["thumbnail"],
        api_model=row["api_model"],
    )
