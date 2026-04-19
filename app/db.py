"""SQLite database — sessions, audit log, allowlist cache.

Concurrency model:
    * One uvicorn worker, async FastAPI, sync ``sqlite3`` stdlib module.
    * Connections are short-lived (one per request via ``Depends(get_conn)``).
    * WAL mode allows concurrent readers + one writer without locking contention.
    * busy_timeout=5000 retries locks for up to 5s inside SQLite itself, so the
      app never sees ``database is locked`` under normal load.

All blocking calls are wrapped at the caller with ``asyncio.to_thread`` so the
event loop stays responsive.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app import config

logger = logging.getLogger(__name__)

_SCHEMA_INITIALIZED = False
_INIT_LOCK = threading.Lock()


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """PRAGMAs applied to every fresh connection."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")


SCHEMA_SQL = """
-- Server-side sessions. We store sha256(token), never the raw token.
CREATE TABLE IF NOT EXISTS sessions (
    session_hash   TEXT PRIMARY KEY,
    tg_id          INTEGER NOT NULL,
    tg_username    TEXT,
    first_name     TEXT,
    photo_url      TEXT,
    created_at     INTEGER NOT NULL,
    last_seen_at   INTEGER NOT NULL,
    expires_at     INTEGER NOT NULL,
    ip             TEXT,
    user_agent     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_tg_id ON sessions(tg_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- Audit log. Every mutating action (and the login event itself) writes a row.
CREATE TABLE IF NOT EXISTS audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              INTEGER NOT NULL,
    actor_tg_id     INTEGER NOT NULL,
    actor_username  TEXT,
    plugin_slug     TEXT,
    action          TEXT NOT NULL,
    params_json     TEXT,         -- redacted JSON blob
    status          TEXT NOT NULL,  -- queued | running | ok | error | timeout
    result_json     TEXT,         -- redacted JSON blob
    error_summary   TEXT,
    remote_host     TEXT,
    duration_sec    REAL,
    updated_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_slug_ts ON audit(plugin_slug, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor_ts ON audit(actor_tg_id, ts DESC);

-- Allowlist is env-driven in v1, but we keep a mirror table for future UI.
-- For now it's purely informational.
CREATE TABLE IF NOT EXISTS allowlist (
    tg_id       INTEGER PRIMARY KEY,
    username    TEXT,
    added_at    INTEGER NOT NULL,
    added_by    INTEGER,
    note        TEXT
);

-- Schema version for future migrations.
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db() -> None:
    """Create schema and set PRAGMAs. Idempotent. Safe to call multiple times."""
    global _SCHEMA_INITIALIZED
    with _INIT_LOCK:
        if _SCHEMA_INITIALIZED:
            return
        _ensure_parent_dir(config.DB_PATH)
        conn = sqlite3.connect(str(config.DB_PATH), isolation_level=None, timeout=5.0)
        try:
            _apply_pragmas(conn)
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('version', '1') "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            )
            logger.info("database initialized at %s", config.DB_PATH)
        finally:
            conn.close()
        _SCHEMA_INITIALIZED = True


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(config.DB_PATH),
        isolation_level=None,   # autocommit — we manage transactions explicitly
        timeout=5.0,
    )
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Short-lived connection context manager. Use as FastAPI dependency.

    Example:
        def _route(conn = Depends(get_conn)):
            rows = conn.execute(...).fetchall()
    """
    if not _SCHEMA_INITIALIZED:
        init_db()
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────
# Helpers for common operations
# ──────────────────────────────────────────────────────────────────────


def now_ts() -> int:
    return int(time.time())


def purge_expired_sessions() -> int:
    """Delete sessions past their ``expires_at``. Returns count deleted."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_ts(),))
        return cur.rowcount or 0


def session_stats() -> dict[str, Any]:
    """For observability — not exposed via API."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE expires_at >= ?", (now_ts(),)
        ).fetchone()[0]
        return {"total": total, "active": active}
