"""Manifest loader — parses /etc/bots-dashboard-agent/manifest.yaml and
instantiates the right BotAdapter subclasses.

Manifest shape (server-a example):

    agent_id: server-a
    adapters:
      - key: lolz_bot
        class: agent.adapters.lolz_bot.LolzBotAdapter
        working_dir: /opt/tg_bot
        systemd_unit: lolz-bot.service
        state_files:
          state_json: /opt/tg_bot/state.json
          watcher: /opt/tg_bot/watcher_config.json
          ...
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from agent import config
from agent.adapters.base import BotAdapter

logger = logging.getLogger(__name__)


def _import_adapter_class(dotted: str) -> type[BotAdapter]:
    module_path, _, class_name = dotted.rpartition(".")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not issubclass(cls, BotAdapter):
        raise TypeError(f"{dotted} is not a BotAdapter subclass")
    return cls


def load_manifest(path: Path | None = None) -> dict[str, BotAdapter]:
    """Return dict[slug -> BotAdapter instance]."""
    mp = path or config.MANIFEST_PATH
    if not mp.exists():
        logger.error("manifest not found: %s — no adapters loaded", mp)
        return {}

    raw = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    adapters_cfg: list[dict[str, Any]] = raw.get("adapters") or []

    result: dict[str, BotAdapter] = {}
    for entry in adapters_cfg:
        if not isinstance(entry, dict):
            logger.warning("manifest: skipping non-dict entry: %r", entry)
            continue
        dotted = entry.get("class") or ""
        if not dotted:
            logger.warning("manifest: entry missing 'class' key: %r", entry)
            continue
        try:
            cls = _import_adapter_class(dotted)
        except Exception as exc:
            logger.error("manifest: cannot import %s: %r", dotted, exc)
            continue

        adapter_config = {k: v for k, v in entry.items() if k != "class"}
        try:
            adapter = cls(adapter_config)
        except Exception as exc:
            logger.error("manifest: failed to instantiate %s: %r", dotted, exc)
            continue

        if adapter.slug in result:
            logger.warning("manifest: duplicate slug %s, overwriting", adapter.slug)
        result[adapter.slug] = adapter
        logger.info("manifest: loaded adapter %s (%s)", adapter.slug, dotted)

    return result
