"""Server-side sessions.

Design:
    * Token generated on the server via ``secrets.token_urlsafe(32)`` — 256-bit.
    * DB stores only ``sha256(token)`` — raw token never touches disk.
    * Cookie name uses the ``__Host-`` prefix which forces ``Secure``,
      ``Path=/``, no ``Domain`` — browsers reject any cookie violating those.
    * ``SameSite=Lax`` + CSRF custom-header check + Origin check gives
      tri-layer CSRF defense (see ``auth/csrf.py``).
    * Sessions can be revoked immediately by deleting the row — no stale JWTs.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response

from app import config, db

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_hash: str
    tg_id: int
    tg_username: str | None
    first_name: str | None
    photo_url: str | None
    created_at: int
    last_seen_at: int
    expires_at: int

    @classmethod
    def from_row(cls, row: Any) -> "Session":
        return cls(
            session_hash=row["session_hash"],
            tg_id=row["tg_id"],
            tg_username=row["tg_username"],
            first_name=row["first_name"],
            photo_url=row["photo_url"],
            created_at=row["created_at"],
            last_seen_at=row["last_seen_at"],
            expires_at=row["expires_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tg_id": self.tg_id,
            "tg_username": self.tg_username,
            "first_name": self.first_name,
            "photo_url": self.photo_url,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


# ──────────────────────────────────────────────────────────────────────
# Token helpers
# ──────────────────────────────────────────────────────────────────────


def new_token() -> str:
    return secrets.token_urlsafe(32)   # ~43 chars, 256 bits of entropy


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────


def create_session(
    tg_id: int,
    tg_username: str | None = None,
    first_name: str | None = None,
    photo_url: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Create a new session row. Returns the raw token (plaintext).

    The raw token is the ONLY place the plaintext exists — it goes straight
    into the cookie. The DB only stores its sha256.
    """
    token = new_token()
    session_hash = hash_token(token)
    now = int(time.time())
    expires = now + config.SESSION_MAX_AGE_SEC

    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions(session_hash, tg_id, tg_username, first_name,
                                 photo_url, created_at, last_seen_at, expires_at,
                                 ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_hash,
                tg_id,
                tg_username,
                first_name,
                photo_url,
                now,
                now,
                expires,
                ip,
                user_agent,
            ),
        )

    logger.info(
        "session created: tg_id=%d, username=%r, expires_at=%d",
        tg_id, tg_username, expires,
    )
    return token


def load_session(token: str, update_last_seen: bool = True) -> Session | None:
    """Look up a session by its raw token. Returns None if not found/expired."""
    if not token:
        return None
    session_hash = hash_token(token)
    now = int(time.time())

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_hash = ? AND expires_at >= ?",
            (session_hash, now),
        ).fetchone()
        if row is None:
            return None

        if update_last_seen:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE session_hash = ?",
                (now, session_hash),
            )

    return Session.from_row(row)


def delete_session(token: str) -> bool:
    """Delete a session row. Returns True if something was deleted."""
    if not token:
        return False
    session_hash = hash_token(token)
    with db.get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE session_hash = ?", (session_hash,)
        )
        return (cur.rowcount or 0) > 0


def delete_all_for_user(tg_id: int) -> int:
    """Revoke every session belonging to a given user."""
    with db.get_conn() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE tg_id = ?", (tg_id,))
        return cur.rowcount or 0


# ──────────────────────────────────────────────────────────────────────
# Cookie helpers
# ──────────────────────────────────────────────────────────────────────


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie to a response.

    Note: Domain is explicitly NOT set, which is required for the
    ``__Host-`` prefix to be accepted by the browser.
    """
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        max_age=config.SESSION_MAX_AGE_SEC,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=config.SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def read_session_cookie(request: Request) -> str:
    return request.cookies.get(config.SESSION_COOKIE_NAME, "")
