"""Adapter contract — what the agent side must implement for every bot."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shared.models import (
    AdapterCapabilities,
    ActionResult,
    BotSummary,
    LogEntry,
    LogsResponse,
    SettingsSchema,
    SettingsValues,
)


class BotAdapter(ABC):
    """Base class for a bot adapter running inside the agent.

    Implementations should be STATELESS between calls — any caching lives in
    the agent-level registry, not on the adapter instance — so that
    hot-reload on config changes doesn't lose important state.
    """

    slug: str                  # "lolz_bot", "loliland", "rebot"
    display_name: str          # human-readable card title
    icon: str = "bot"          # lucide icon name
    config: dict[str, Any]     # merged from manifest.yaml

    def __init__(self, adapter_config: dict[str, Any]) -> None:
        self.config = adapter_config

    # ──────────────────────────────────────────────────────────────
    # Capabilities — what this adapter actually supports
    # ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def capabilities(self) -> AdapterCapabilities: ...

    # ──────────────────────────────────────────────────────────────
    # Read-only introspection
    # ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def summary(self) -> BotSummary: ...

    async def get_settings(self) -> tuple[SettingsSchema, SettingsValues]:
        """Return current settings schema + values. Default: empty (no settings)."""
        return SettingsSchema(), SettingsValues()

    async def get_logs(
        self, cursor: str | None = None, limit: int = 200
    ) -> LogsResponse:
        """Return recent log entries. Default: empty list (no logs)."""
        return LogsResponse(entries=[], next_cursor=None, has_more=False)

    # ──────────────────────────────────────────────────────────────
    # Mutations
    # ──────────────────────────────────────────────────────────────

    async def update_settings(self, patch: dict[str, Any]) -> SettingsValues:
        """Apply a settings patch. Default: raise — override in subclass."""
        raise NotImplementedError(f"{self.slug} does not support settings updates")

    async def run_action(self, key: str, params: dict[str, Any]) -> ActionResult:
        """Execute an action by key. Default: raise — override in subclass."""
        raise NotImplementedError(f"{self.slug} has no action {key!r}")

    # ──────────────────────────────────────────────────────────────
    # Background tasks — optional long-running loops
    # ──────────────────────────────────────────────────────────────

    async def start_background(self) -> None:
        """Spawn any long-running tasks. Called once at agent startup."""
        return None

    async def stop_background(self) -> None:
        """Cancel long-running tasks. Called at agent shutdown."""
        return None
