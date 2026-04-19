"""Per-plugin routes: /api/plugins, summary, settings, logs, actions."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app import audit
from app.agent_client import AgentError, AgentUnavailable
from app.auth.middleware import require_session
from app.auth.session import Session
from app.plugins import registry
from shared.models import (
    ActionResult,
    AuditStatus,
    BotSummary,
    LogsResponse,
    SettingsValues,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


def _require_entry(slug: str) -> registry.PluginEntry:
    entry = registry.get_plugin(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"unknown plugin: {slug}")
    return entry


# ──────────────────────────────────────────────────────────────────────
# Read-only
# ──────────────────────────────────────────────────────────────────────


@router.get("")
async def list_plugins(session: Session = Depends(require_session)) -> dict:
    out = []
    for e in registry.list_plugins():
        out.append(
            {
                "slug": e.plugin.slug,
                "display_name": e.plugin.display_name,
                "icon": e.plugin.icon,
                "host": e.plugin.host,
                "adapter_key": e.plugin.adapter_key,
                "available": e.available,
                "last_error": e.last_error,
                "capabilities": e.capabilities.model_dump() if e.capabilities else None,
            }
        )
    return {"plugins": out, "hosts": {
        name: {
            "available": s.available,
            "last_seen_at": s.last_seen_at,
            "last_error": s.last_error,
            "agent_version": s.agent_version,
        }
        for name, s in registry.host_states().items()
    }}


@router.get("/{slug}/summary", response_model=BotSummary)
async def plugin_summary(slug: str, session: Session = Depends(require_session)) -> BotSummary:
    entry = _require_entry(slug)
    try:
        return await entry.plugin.summary()
    except AgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{slug}/settings")
async def plugin_settings(slug: str, session: Session = Depends(require_session)) -> dict:
    entry = _require_entry(slug)
    try:
        schema, values = await entry.plugin.get_settings()
    except AgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"schema": schema.model_dump(), "values": values.model_dump()}


@router.get("/{slug}/logs", response_model=LogsResponse)
async def plugin_logs(
    slug: str,
    cursor: str | None = None,
    limit: int = 200,
    session: Session = Depends(require_session),
) -> LogsResponse:
    entry = _require_entry(slug)
    try:
        return await entry.plugin.get_logs(cursor=cursor, limit=limit)
    except AgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────
# Mutations — audited
# ──────────────────────────────────────────────────────────────────────


@router.put("/{slug}/settings", response_model=SettingsValues)
async def update_plugin_settings(
    slug: str,
    patch: dict[str, Any],
    request: Request,
    session: Session = Depends(require_session),
) -> SettingsValues:
    entry = _require_entry(slug)

    audit_id = audit.begin_action(
        actor_tg_id=session.tg_id,
        actor_username=session.tg_username,
        plugin_slug=slug,
        action="update_settings",
        params=patch,
        remote_host=entry.plugin.host,
    )
    audit.mark_running(audit_id)

    try:
        values = await entry.plugin.update_settings(patch)
        audit.mark_result(audit_id, ok=True, result=values.model_dump())
        return values
    except AgentError as exc:
        audit.mark_result(audit_id, ok=False, error=exc)
        status = exc.status or 502
        raise HTTPException(status_code=status, detail=str(exc))
    except Exception as exc:
        audit.mark_result(audit_id, ok=False, error=exc)
        logger.exception("update_settings(%s) failed", slug)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{slug}/actions/{action_key}", response_model=ActionResult)
async def run_plugin_action(
    slug: str,
    action_key: str,
    params: dict[str, Any] | None = None,
    session: Session = Depends(require_session),
) -> ActionResult:
    entry = _require_entry(slug)

    audit_id = audit.begin_action(
        actor_tg_id=session.tg_id,
        actor_username=session.tg_username,
        plugin_slug=slug,
        action=action_key,
        params=params or {},
        remote_host=entry.plugin.host,
    )
    audit.mark_running(audit_id)

    try:
        result = await entry.plugin.run_action(action_key, params)
        audit.mark_result(audit_id, ok=result.ok, result=result.model_dump(),
                          error=result.error)
        return result
    except AgentError as exc:
        audit.mark_result(audit_id, ok=False, error=exc)
        status = exc.status or 502
        raise HTTPException(status_code=status, detail=str(exc))
    except Exception as exc:
        audit.mark_result(audit_id, ok=False, error=exc)
        logger.exception("run_action(%s/%s) failed", slug, action_key)
        raise HTTPException(status_code=500, detail=str(exc))
