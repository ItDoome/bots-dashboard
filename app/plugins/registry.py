"""Plugin registry — hybrid static inventory + dynamic capabilities enrichment.

The source of truth for WHICH bots exist is ``/etc/bots-dashboard/inventory.yaml``.
At startup (and on TTL expiry) the central app queries each agent's
``/agent/capabilities`` and merges the results with the inventory, caching
the combined view in ``/var/lib/bots-dashboard/capabilities_cache.json``
for graceful degradation when an agent is offline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app import config
from app.agent_client import AgentError, get_client
from app.plugins.base import BotPlugin
from shared.models import AdapterCapabilities, AgentCapabilities

logger = logging.getLogger(__name__)


@dataclass
class PluginEntry:
    plugin: BotPlugin
    available: bool = False
    last_seen_at: float = 0.0
    capabilities: AdapterCapabilities | None = None
    last_error: str | None = None


@dataclass
class HostState:
    url: str
    available: bool = False
    last_seen_at: float = 0.0
    last_error: str | None = None
    agent_version: str | None = None


_inventory: list[dict[str, Any]] = []
_plugins: dict[str, PluginEntry] = {}
_hosts: dict[str, HostState] = {}
_capabilities_cache: dict[str, Any] = {}
_cache_loaded_at: float = 0.0


# ──────────────────────────────────────────────────────────────────────
# Load static inventory
# ──────────────────────────────────────────────────────────────────────


def load_inventory(path: Path | None = None) -> None:
    global _inventory, _plugins, _hosts

    mp = path or config.INVENTORY_PATH
    raw: dict[str, Any] = {}
    if mp.exists():
        try:
            raw = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.error("failed to parse inventory %s: %r", mp, exc)
            raw = {}
    else:
        logger.warning("inventory not found: %s", mp)

    bots = raw.get("bots") or []
    hosts = raw.get("hosts") or {}

    _inventory = list(bots)
    _hosts = {
        name: HostState(url=(hcfg or {}).get("url", ""))
        for name, hcfg in hosts.items()
    }

    new_plugins: dict[str, PluginEntry] = {}
    for entry in bots:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        if not slug:
            continue
        plugin = BotPlugin(
            slug=slug,
            display_name=entry.get("display_name") or slug,
            icon=entry.get("icon") or "bot",
            host=entry.get("host") or "",
            adapter_key=entry.get("adapter_key") or slug,
        )
        new_plugins[slug] = PluginEntry(plugin=plugin)
    _plugins = new_plugins
    logger.info(
        "inventory loaded: %d bots across %d hosts (%s)",
        len(_plugins), len(_hosts), list(_plugins.keys()),
    )

    _load_capabilities_cache()


# ──────────────────────────────────────────────────────────────────────
# Persistent capabilities cache (for graceful cold-start)
# ──────────────────────────────────────────────────────────────────────


def _load_capabilities_cache() -> None:
    global _capabilities_cache, _cache_loaded_at
    p = config.CAPABILITIES_CACHE_PATH
    if not p.exists():
        _capabilities_cache = {}
        return
    try:
        _capabilities_cache = json.loads(p.read_text(encoding="utf-8"))
        _cache_loaded_at = time.time()
        # Re-hydrate "last seen" values for each plugin
        for slug, entry in _plugins.items():
            cache_blob = _capabilities_cache.get(slug)
            if not cache_blob:
                continue
            try:
                entry.capabilities = AdapterCapabilities.model_validate(
                    cache_blob.get("capabilities")
                )
            except Exception:
                pass
            entry.last_seen_at = cache_blob.get("last_seen_at", 0.0)
        logger.info("capabilities cache loaded: %d entries", len(_capabilities_cache))
    except Exception as exc:
        logger.warning("failed to load capabilities cache: %r", exc)
        _capabilities_cache = {}


def _persist_capabilities_cache() -> None:
    p = config.CAPABILITIES_CACHE_PATH
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {}
        for slug, entry in _plugins.items():
            if entry.capabilities is None:
                continue
            payload[slug] = {
                "last_seen_at": entry.last_seen_at,
                "capabilities": entry.capabilities.model_dump(),
            }
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception as exc:
        logger.warning("failed to persist capabilities cache: %r", exc)


# ──────────────────────────────────────────────────────────────────────
# Dynamic enrichment — ask each agent for its capabilities
# ──────────────────────────────────────────────────────────────────────


async def refresh_capabilities(timeout: float = 3.0) -> None:
    """Ping each host's /agent/capabilities. Updates _plugins/_hosts."""
    if not _hosts:
        return

    client = get_client()
    now = time.time()

    async def _one(host: str) -> tuple[str, AgentCapabilities | None, str | None]:
        try:
            raw = await asyncio.wait_for(
                client.get(host, "/agent/capabilities"),
                timeout=timeout,
            )
            return host, AgentCapabilities.model_validate(raw), None
        except AgentError as exc:
            return host, None, str(exc)
        except asyncio.TimeoutError:
            return host, None, "timeout"
        except Exception as exc:
            return host, None, f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(*(_one(h) for h in _hosts))

    for host, caps, err in results:
        state = _hosts.get(host)
        if state is None:
            continue
        if err is None and caps is not None:
            state.available = True
            state.last_seen_at = now
            state.last_error = None
            state.agent_version = caps.version
            by_key = {a.key: a for a in caps.adapters}
            for entry in _plugins.values():
                if entry.plugin.host != host:
                    continue
                adapter_cap = by_key.get(entry.plugin.adapter_key)
                if adapter_cap is not None:
                    entry.capabilities = adapter_cap
                    entry.available = True
                    entry.last_seen_at = now
                    entry.last_error = None
                else:
                    entry.available = False
                    entry.last_error = f"adapter {entry.plugin.adapter_key!r} not registered on agent"
        else:
            state.available = False
            state.last_error = err
            for entry in _plugins.values():
                if entry.plugin.host != host:
                    continue
                entry.available = False
                entry.last_error = err

    _persist_capabilities_cache()


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────


def list_plugins() -> list[PluginEntry]:
    return list(_plugins.values())


def get_plugin(slug: str) -> PluginEntry | None:
    return _plugins.get(slug)


def host_states() -> dict[str, HostState]:
    return dict(_hosts)
