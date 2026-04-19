"""Audit log — records every login, logout, settings edit, and action trigger.

All params/result blobs are passed through ``redact.redact()`` before being
serialized to JSON and written to SQLite. No raw tokens, passwords, or
cookies end up on disk.

Lifecycle of an action row:
    1. ``begin_action(...)`` creates a row in ``status='queued'`` and returns id
    2. ``mark_running(id)`` transitions to ``status='running'``
    3. ``mark_result(id, ok=True, output=...)`` → ``status='ok'``
       ``mark_result(id, ok=False, error=...)`` → ``status='error'``
       ``mark_timeout(id)`` → ``status='timeout'``

Query helpers return ``AuditPage`` / ``AuditEntry`` pydantic models.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app import db
from app.redact import redact, redact_text
from shared.models import AuditEntry, AuditPage, AuditStatus

logger = logging.getLogger(__name__)


def _dump(value: Any) -> str:
    """JSON-serialize a value, applying ``redact()`` first. Returns '' on None."""
    if value is None:
        return ""
    try:
        redacted = redact(value)
        return json.dumps(redacted, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("audit: failed to json-serialize %r: %r", type(value).__name__, exc)
        return json.dumps({"error": "serialization_failed"})


def write_event(
    *,
    actor_tg_id: int,
    actor_username: str | None = None,
    action: str,
    plugin_slug: str | None = None,
    params: Any = None,
    status: AuditStatus | str = AuditStatus.ok,
    result: Any = None,
    error_summary: str | None = None,
    remote_host: str | None = None,
    duration_sec: float | None = None,
) -> int:
    """Write a one-shot audit row (already in a terminal state). Returns id."""
    now = int(time.time())
    status_str = status.value if isinstance(status, AuditStatus) else str(status)
    with db.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO audit(
                ts, actor_tg_id, actor_username, plugin_slug, action,
                params_json, status, result_json, error_summary,
                remote_host, duration_sec, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                actor_tg_id,
                actor_username,
                plugin_slug,
                action,
                _dump(params),
                status_str,
                _dump(result),
                redact_text(error_summary) if error_summary else None,
                remote_host,
                duration_sec,
                now,
            ),
        )
        return cur.lastrowid


def begin_action(
    *,
    actor_tg_id: int,
    actor_username: str | None,
    plugin_slug: str,
    action: str,
    params: Any,
    remote_host: str | None = None,
) -> int:
    """Create a queued audit row for a long-running action."""
    return write_event(
        actor_tg_id=actor_tg_id,
        actor_username=actor_username,
        plugin_slug=plugin_slug,
        action=action,
        params=params,
        status=AuditStatus.queued,
        remote_host=remote_host,
    )


def mark_running(audit_id: int) -> None:
    now = int(time.time())
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE audit SET status = 'running', updated_at = ? WHERE id = ?",
            (now, audit_id),
        )


def mark_result(
    audit_id: int,
    *,
    ok: bool,
    result: Any = None,
    error: BaseException | str | None = None,
    started_at: int | None = None,
) -> None:
    now = int(time.time())
    duration = None
    if started_at is not None:
        duration = max(0.0, now - started_at)

    status = AuditStatus.ok if ok else AuditStatus.error
    error_summary: str | None = None
    if error is not None and not ok:
        if isinstance(error, BaseException):
            error_summary = redact_text(f"{type(error).__name__}: {error}")[:500]
        else:
            error_summary = redact_text(str(error))[:500]

    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE audit
               SET status = ?,
                   result_json = ?,
                   error_summary = ?,
                   duration_sec = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (
                status.value,
                _dump(result),
                error_summary,
                duration,
                now,
                audit_id,
            ),
        )


def mark_timeout(audit_id: int, *, started_at: int | None = None) -> None:
    now = int(time.time())
    duration = None
    if started_at is not None:
        duration = max(0.0, now - started_at)
    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE audit
               SET status = 'timeout',
                   error_summary = 'action timed out',
                   duration_sec = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (duration, now, audit_id),
        )


# ──────────────────────────────────────────────────────────────────────
# Query helpers
# ──────────────────────────────────────────────────────────────────────


def list_entries(
    page: int = 1,
    page_size: int = 50,
    plugin_slug: str | None = None,
    actor_tg_id: int | None = None,
) -> AuditPage:
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    offset = (page - 1) * page_size

    where: list[str] = []
    params: list[Any] = []
    if plugin_slug:
        where.append("plugin_slug = ?")
        params.append(plugin_slug)
    if actor_tg_id is not None:
        where.append("actor_tg_id = ?")
        params.append(actor_tg_id)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with db.get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM audit {where_sql}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT id, ts, actor_tg_id, actor_username, plugin_slug, action,
                   params_json, status, result_json, error_summary,
                   remote_host, duration_sec
              FROM audit
              {where_sql}
             ORDER BY ts DESC
             LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

    entries = [
        AuditEntry(
            id=row["id"],
            ts=_ts_to_iso(row["ts"]),
            actor_tg_id=row["actor_tg_id"],
            actor_username=row["actor_username"],
            plugin_slug=row["plugin_slug"],
            action=row["action"],
            params_json=row["params_json"] or None,
            status=AuditStatus(row["status"]),
            result_json=row["result_json"] or None,
            error_summary=row["error_summary"],
            remote_host=row["remote_host"],
            duration_sec=row["duration_sec"],
        )
        for row in rows
    ]

    return AuditPage(entries=entries, page=page, total=total, page_size=page_size)


def _ts_to_iso(ts: int | float) -> str:
    import datetime as _dt

    return _dt.datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc).isoformat()
