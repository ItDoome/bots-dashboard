"""CSRF defense for mutating API endpoints.

Three independent layers protect every POST/PUT/PATCH/DELETE on /api/*:

    1. Session cookie is SameSite=Lax. A cross-site POST from a malicious
       page does not include the cookie, so it fails auth.
    2. Origin / Referer must match our PUBLIC_ORIGIN. SameSite=Lax still
       allows top-level navigations, but those also can't forge custom
       headers or arbitrary bodies.
    3. A custom header ``X-Dashboard-Request: 1`` is required. Browsers
       enforce a CORS preflight for custom headers — a cross-origin page
       can't send them without us explicitly allowing it (which we don't).

Any one layer on its own is weak; together they are robust.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from app import config

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_matches(value: str) -> bool:
    if not value:
        return False
    return value.rstrip("/") == config.PUBLIC_ORIGIN.rstrip("/")


def _referer_matches(value: str) -> bool:
    if not value:
        return False
    # Referer is a full URL; take scheme+host+port prefix
    try:
        from urllib.parse import urlparse

        p = urlparse(value)
        origin = f"{p.scheme}://{p.netloc}"
        return origin.rstrip("/") == config.PUBLIC_ORIGIN.rstrip("/")
    except Exception:
        return False


def require_csrf(request: Request) -> None:
    """FastAPI dependency that enforces CSRF defense on mutating requests.

    Non-mutating methods (GET, HEAD, OPTIONS) pass through unconditionally.
    """
    if request.method.upper() not in MUTATING_METHODS:
        return

    # 1. Custom header must be present with the expected value.
    header_val = request.headers.get(config.CSRF_HEADER_NAME, "").strip()
    if header_val != config.CSRF_HEADER_VALUE:
        logger.info(
            "csrf: missing/invalid header on %s %s (client=%s)",
            request.method, request.url.path, request.client.host if request.client else "?",
        )
        raise HTTPException(
            status_code=403,
            detail=f"missing or invalid {config.CSRF_HEADER_NAME} header",
        )

    # 2. Origin OR Referer must match PUBLIC_ORIGIN.
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    if not (_origin_matches(origin) or _referer_matches(referer)):
        logger.info(
            "csrf: origin/referer mismatch on %s %s (origin=%r, referer=%r)",
            request.method, request.url.path, origin, referer,
        )
        raise HTTPException(
            status_code=403,
            detail="origin/referer mismatch",
        )
