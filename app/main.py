"""Bots Dashboard — central FastAPI app.

Invariants (see plan + README):
    * uvicorn --workers 1. Action mutex and in-memory caches assume one
      Python process. Multi-worker deployment is explicitly unsupported.
    * App never touches bot files / systemd / PG directly. Everything goes
      through the HTTP agents on each server.
    * Every mutating endpoint requires CSRF defense (Origin + custom header).
    * Session cookies: __Host-dash_session, 256-bit random, stored as sha256.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app import config, db
from app.agent_client import get_client as get_agent_client
from app.auth.csrf import require_csrf
from app.auth.middleware import require_session
from app.auth.session import Session
from app.plugins import registry as plugin_registry
from app.routers import audit as audit_router
from app.routers import auth as auth_router
from app.routers import dashboard as dashboard_router
from app.routers import plugins as plugins_router
from app.routers.auth import me_payload

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bots-dashboard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("bots-dashboard starting up, version=%s sha=%s",
                config.VERSION, config.BUILD_SHA)

    # Single-worker invariant check. If someone ever sets this, log loud.
    web_concurrency = os.environ.get("WEB_CONCURRENCY")
    if web_concurrency and web_concurrency != "1":
        logger.error(
            "WEB_CONCURRENCY=%s — multi-worker mode is NOT supported. "
            "Action mutex will silently break. Set WEB_CONCURRENCY=1 in systemd.",
            web_concurrency,
        )

    errors = config.validate_critical_config()
    if errors:
        for err in errors:
            logger.error("config error: %s", err)
        logger.error(
            "config is incomplete — login and agent calls will fail until "
            "/etc/bots-dashboard/env is populated. See README for required keys."
        )

    logger.info("config snapshot: %s", config.snapshot())
    db.init_db()

    # Load static inventory and (best-effort) refresh capabilities from
    # each agent. Failure here is non-fatal — the cold-start path shows
    # bots as "unavailable" until an agent becomes reachable.
    plugin_registry.load_inventory()
    try:
        await plugin_registry.refresh_capabilities()
    except Exception as exc:
        logger.warning("initial capabilities refresh failed: %r", exc)

    yield

    try:
        await get_agent_client().close()
    except Exception:
        pass
    logger.info("bots-dashboard shutdown")


app = FastAPI(
    title="Bots Dashboard",
    version=config.VERSION,
    lifespan=lifespan,
    # CSRF is enforced as a global dependency — every endpoint runs it,
    # non-mutating methods pass through for free.
    dependencies=[Depends(require_csrf)],
)


# ──────────────────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────────────────

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(plugins_router.router)
app.include_router(audit_router.router)


# ──────────────────────────────────────────────────────────────────────
# Top-level endpoints (not under /auth)
# ──────────────────────────────────────────────────────────────────────


@app.get("/api/me")
async def get_me(session: Session = Depends(require_session)) -> dict:
    return me_payload(session).model_dump()


@app.get("/api/version")
async def get_version() -> dict:
    return {
        "version": config.VERSION,
        "build_sha": config.BUILD_SHA,
    }


@app.get("/api/health")
async def get_health() -> dict:
    """Liveness probe. No auth, no side effects, minimal info."""
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────
# Global error handlers
# ──────────────────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s: %r",
                     request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error_code": "internal_error", "message": "internal server error"},
    )
