"""Dashboard overview — aggregates summaries from all plugins with caching."""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import time

from fastapi import APIRouter, Depends

from app import config
from app.agent_client import AgentError
from app.auth.middleware import require_session
from app.auth.session import Session
from app.plugins import registry
from shared.models import DashboardOverview, PluginCardData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


_cache: dict[str, object] = {}
_cache_ts: float = 0.0


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


async def _fetch_card(entry: registry.PluginEntry) -> PluginCardData:
    plugin = entry.plugin
    try:
        summary = await asyncio.wait_for(plugin.summary(), timeout=5.0)
    except asyncio.TimeoutError:
        return PluginCardData(
            slug=plugin.slug,
            display_name=plugin.display_name,
            icon=plugin.icon,
            host=plugin.host,
            available=False,
            error="agent summary timed out",
            last_successful_at=_dt.datetime.fromtimestamp(
                entry.last_seen_at, tz=_dt.timezone.utc
            ).isoformat() if entry.last_seen_at else None,
        )
    except AgentError as exc:
        return PluginCardData(
            slug=plugin.slug,
            display_name=plugin.display_name,
            icon=plugin.icon,
            host=plugin.host,
            available=False,
            error=str(exc)[:300],
            last_successful_at=_dt.datetime.fromtimestamp(
                entry.last_seen_at, tz=_dt.timezone.utc
            ).isoformat() if entry.last_seen_at else None,
        )
    except Exception as exc:
        logger.exception("unexpected error fetching %s summary", plugin.slug)
        return PluginCardData(
            slug=plugin.slug,
            display_name=plugin.display_name,
            icon=plugin.icon,
            host=plugin.host,
            available=False,
            error=f"{type(exc).__name__}: {exc}"[:300],
        )

    return PluginCardData(
        slug=plugin.slug,
        display_name=plugin.display_name,
        icon=plugin.icon,
        host=plugin.host,
        available=True,
        summary=summary,
        last_successful_at=_now_iso(),
    )


@router.get("/overview", response_model=DashboardOverview)
async def overview(session: Session = Depends(require_session)) -> DashboardOverview:
    global _cache_ts, _cache

    now = time.monotonic()
    if _cache and (now - _cache_ts) < config.OVERVIEW_CACHE_TTL_SEC:
        return _cache["payload"]   # type: ignore[return-value]

    entries = registry.list_plugins()
    cards = await asyncio.gather(*(_fetch_card(e) for e in entries))

    totals = {
        "total_bots": len(cards),
        "available": sum(1 for c in cards if c.available),
        "errors": sum(
            1 for c in cards
            if not c.available
            or (c.summary is not None and c.summary.health.value == "error")
        ),
    }

    payload = DashboardOverview(
        generated_at=_now_iso(),
        bots=list(cards),
        totals=totals,
    )
    _cache = {"payload": payload}
    _cache_ts = now
    return payload
