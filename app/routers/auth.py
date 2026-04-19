"""Authentication routes: Telegram login callback, logout, /me."""
from __future__ import annotations

import datetime as _dt
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app import audit, config
from app.auth.middleware import require_session
from app.auth.session import (
    Session,
    clear_session_cookie,
    create_session,
    delete_session,
    read_session_cookie,
    set_session_cookie,
)
from app.auth.telegram import TelegramAuthError, verify_telegram_auth
from shared.models import AuditStatus, SessionUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ──────────────────────────────────────────────────────────────────────
# GET /api/auth/telegram — Login Widget callback
# ──────────────────────────────────────────────────────────────────────
#
# Telegram Login Widget posts the user here via a browser redirect with
# query-string params. We verify HMAC, check allowlist, create a session,
# and 302 to /dashboard. Nginx is configured with ``access_log off`` on
# this route so the query string (containing hash/id/names) never hits
# disk logs.
#
# Audit log: we record only {login, tg_id, username} — never the hash or
# raw payload.

@router.get("/telegram")
async def telegram_callback(request: Request) -> Response:
    params = dict(request.query_params)

    try:
        verified = verify_telegram_auth(
            params=params,
            bot_token=config.TELEGRAM_BOT_TOKEN,
            max_age_sec=config.TG_AUTH_MAX_AGE_SEC,
        )
    except TelegramAuthError as exc:
        logger.warning("telegram auth failed: %s", exc)
        audit.write_event(
            actor_tg_id=int(params.get("id", "0") or 0),
            action="login_failed",
            params={"reason": str(exc)},
            status=AuditStatus.error,
            error_summary=str(exc),
        )
        raise HTTPException(status_code=400, detail="telegram auth failed")

    tg_id = int(verified["id"])
    username = verified.get("username")
    first_name = verified.get("first_name")
    photo_url = verified.get("photo_url")

    if config.ALLOWED_TG_IDS and tg_id not in config.ALLOWED_TG_IDS:
        logger.warning("login rejected: tg_id=%d not in allowlist", tg_id)
        audit.write_event(
            actor_tg_id=tg_id,
            actor_username=username,
            action="login_rejected",
            status=AuditStatus.error,
            error_summary="not in allowlist",
        )
        raise HTTPException(status_code=403, detail="access denied")

    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:300]

    token = create_session(
        tg_id=tg_id,
        tg_username=username,
        first_name=first_name,
        photo_url=photo_url,
        ip=ip,
        user_agent=user_agent,
    )

    audit.write_event(
        actor_tg_id=tg_id,
        actor_username=username,
        action="login",
        status=AuditStatus.ok,
    )

    response = RedirectResponse(url="/dashboard", status_code=302)
    set_session_cookie(response, token)
    return response


# ──────────────────────────────────────────────────────────────────────
# POST /api/auth/logout
# ──────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request, response: Response,
                 session: Session = Depends(require_session)) -> dict:
    token = read_session_cookie(request)
    delete_session(token)
    clear_session_cookie(response)

    audit.write_event(
        actor_tg_id=session.tg_id,
        actor_username=session.tg_username,
        action="logout",
        status=AuditStatus.ok,
    )
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────
# GET /api/me
# ──────────────────────────────────────────────────────────────────────

@router.get("/../me", include_in_schema=False)  # exposed as /api/me below
async def _unused_placeholder():
    """Placeholder — real /api/me is defined in main.py at top-level because
    it does not belong under the /auth prefix."""
    raise HTTPException(status_code=404)


def me_payload(session: Session) -> SessionUser:
    return SessionUser(
        tg_id=session.tg_id,
        username=session.tg_username,
        first_name=session.first_name,
        photo_url=session.photo_url,
        session_created_at=_iso(session.created_at),
        session_expires_at=_iso(session.expires_at),
    )


def _iso(ts: int) -> str:
    return _dt.datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc).isoformat()
