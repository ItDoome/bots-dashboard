"""Session middleware / dependencies for FastAPI routes.

Usage:
    @router.get("/api/some-protected")
    async def protected(session: Session = Depends(require_session)):
        ...
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from app import config
from app.auth.session import Session, load_session, read_session_cookie

logger = logging.getLogger(__name__)


def require_session(request: Request) -> Session:
    """FastAPI dependency — returns the active session or raises 401."""
    token = read_session_cookie(request)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")

    session = load_session(token, update_last_seen=True)
    if session is None:
        raise HTTPException(status_code=401, detail="session expired or invalid")

    # Runtime allowlist check — lets us revoke access by just editing the env
    # file and restarting, without having to wipe sessions from the DB first.
    if config.ALLOWED_TG_IDS and session.tg_id not in config.ALLOWED_TG_IDS:
        logger.warning(
            "session exists for tg_id=%d but user is no longer allowlisted",
            session.tg_id,
        )
        raise HTTPException(status_code=403, detail="access revoked")

    return session


def optional_session(request: Request) -> Session | None:
    """Same as ``require_session`` but returns ``None`` if not logged in."""
    token = read_session_cookie(request)
    if not token:
        return None
    session = load_session(token, update_last_seen=True)
    if session is None:
        return None
    if config.ALLOWED_TG_IDS and session.tg_id not in config.ALLOWED_TG_IDS:
        return None
    return session
