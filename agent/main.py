"""Agent FastAPI app. Listens on 127.0.0.1:8765, bearer-auth only.

Routes:
    GET  /health                                        (no auth)
    GET  /agent/capabilities                            (auth)
    GET  /adapters/{adapter_key}/summary                (auth)
    GET  /adapters/{adapter_key}/settings               (auth)
    PUT  /adapters/{adapter_key}/settings               (auth)
    GET  /adapters/{adapter_key}/logs?cursor=&limit=    (auth)
    POST /adapters/{adapter_key}/actions/{action_key}   (auth)

Reached only via loopback or SSH tunnel from the central app. Never exposed
to the public internet.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from agent import config, locks, manifest
from agent.adapters.base import BotAdapter
from shared.models import (
    ActionResult,
    AgentCapabilities,
    BotSummary,
    LogsResponse,
    SettingsSchema,
    SettingsValues,
)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent")


# ──────────────────────────────────────────────────────────────────────
# State holder — loaded adapters
# ──────────────────────────────────────────────────────────────────────


_adapters: dict[str, BotAdapter] = {}


def get_adapter(adapter_key: str) -> BotAdapter:
    adapter = _adapters.get(adapter_key)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"unknown adapter: {adapter_key}")
    return adapter


# ──────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────


def require_bearer(authorization: str = Header(default="")) -> None:
    if not config.AGENT_TOKEN:
        raise HTTPException(status_code=500, detail="agent misconfigured: no token")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != config.AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="invalid bearer token")


# ──────────────────────────────────────────────────────────────────────
# Lifespan — load manifest, warn on single-process invariant violation
# ──────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _adapters

    logger.info("agent starting: %s", config.snapshot())
    errors = config.validate()
    for err in errors:
        logger.error("config error: %s", err)

    # Single-instance invariant
    wc = os.environ.get("WEB_CONCURRENCY")
    if wc and wc != "1":
        logger.error(
            "WEB_CONCURRENCY=%s — agent MUST run as a single process. "
            "Action mutex will silently break otherwise.", wc,
        )

    _adapters = manifest.load_manifest()
    logger.info("loaded %d adapters: %s", len(_adapters), list(_adapters.keys()))

    for slug, adapter in _adapters.items():
        try:
            await adapter.start_background()
        except Exception:
            logger.exception("start_background(%s) failed", slug)

    yield

    for slug, adapter in _adapters.items():
        try:
            await adapter.stop_background()
        except Exception:
            logger.exception("stop_background(%s) failed", slug)

    logger.info("agent shutdown")


app = FastAPI(title="bots-dashboard-agent", version=config.VERSION, lifespan=lifespan)


# ──────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "agent_id": config.AGENT_ID, "adapters": list(_adapters.keys())}


@app.get("/agent/capabilities", response_model=AgentCapabilities,
         dependencies=[Depends(require_bearer)])
async def capabilities() -> AgentCapabilities:
    import socket

    adapters_caps = []
    # Run in parallel with a per-adapter timeout so one slow adapter can't
    # take down discovery.
    async def _one(a: BotAdapter):
        try:
            return await asyncio.wait_for(a.capabilities(), timeout=3.0)
        except Exception as exc:
            logger.warning("capabilities() failed for %s: %r", a.slug, exc)
            return None

    results = await asyncio.gather(*(_one(a) for a in _adapters.values()))
    for r in results:
        if r is not None:
            adapters_caps.append(r)

    return AgentCapabilities(
        agent_id=config.AGENT_ID,
        version=config.VERSION,
        hostname=socket.gethostname(),
        adapters=adapters_caps,
    )


@app.get("/adapters/{adapter_key}/summary", response_model=BotSummary,
         dependencies=[Depends(require_bearer)])
async def adapter_summary(adapter_key: str) -> BotSummary:
    adapter = get_adapter(adapter_key)
    try:
        return await asyncio.wait_for(adapter.summary(), timeout=10.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="adapter summary timed out")
    except Exception as exc:
        logger.exception("summary(%s) failed", adapter_key)
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.get("/adapters/{adapter_key}/settings",
         dependencies=[Depends(require_bearer)])
async def adapter_settings_get(adapter_key: str) -> dict:
    adapter = get_adapter(adapter_key)
    try:
        schema, values = await asyncio.wait_for(adapter.get_settings(), timeout=10.0)
    except Exception as exc:
        logger.exception("get_settings(%s) failed", adapter_key)
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")
    return {"schema": schema.model_dump(), "values": values.model_dump()}


@app.put("/adapters/{adapter_key}/settings", response_model=SettingsValues,
         dependencies=[Depends(require_bearer)])
async def adapter_settings_put(adapter_key: str, patch: dict[str, Any]) -> SettingsValues:
    adapter = get_adapter(adapter_key)
    try:
        return await asyncio.wait_for(
            adapter.update_settings(patch), timeout=10.0,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotImplementedError:
        raise HTTPException(status_code=405, detail="settings not supported")
    except Exception as exc:
        logger.exception("update_settings(%s) failed", adapter_key)
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.get("/adapters/{adapter_key}/logs", response_model=LogsResponse,
         dependencies=[Depends(require_bearer)])
async def adapter_logs(
    adapter_key: str,
    cursor: str | None = None,
    limit: int = 200,
) -> LogsResponse:
    adapter = get_adapter(adapter_key)
    try:
        return await asyncio.wait_for(
            adapter.get_logs(cursor=cursor, limit=limit), timeout=15.0,
        )
    except Exception as exc:
        logger.exception("get_logs(%s) failed", adapter_key)
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.post("/adapters/{adapter_key}/actions/{action_key}",
          response_model=ActionResult,
          dependencies=[Depends(require_bearer)])
async def adapter_run_action(
    adapter_key: str,
    action_key: str,
    params: dict[str, Any] | None = None,
) -> ActionResult:
    adapter = get_adapter(adapter_key)
    lock = locks.try_lock(adapter_key, action_key)
    if lock.locked():
        raise HTTPException(status_code=409, detail="action already running")

    started = time.monotonic()
    async with lock:
        try:
            return await asyncio.wait_for(
                adapter.run_action(action_key, params or {}),
                timeout=config.ACTION_CLAIM_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            return ActionResult(
                ok=False,
                error=f"action timed out after {config.ACTION_CLAIM_TIMEOUT_SEC}s",
                duration_sec=time.monotonic() - started,
            )
        except NotImplementedError as exc:
            raise HTTPException(status_code=405, detail=str(exc))
        except Exception as exc:
            logger.exception("run_action(%s/%s) failed", adapter_key, action_key)
            return ActionResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_sec=time.monotonic() - started,
            )


# ──────────────────────────────────────────────────────────────────────
# Global error handler
# ──────────────────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled on %s %s: %r",
                     request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error_code": "internal_error", "message": "internal error"},
    )
