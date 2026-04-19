"""Central-side plugin base — proxies everything to the agent via agent_client.

Plugins are ~40-line wrappers: they hold only metadata (slug, icon, host,
adapter_key) and inherit all behavior from this class.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agent_client import AgentClient, AgentError, AgentUnavailable, get_client
from shared.models import (
    ActionResult,
    BotSummary,
    LogsResponse,
    SettingsSchema,
    SettingsValues,
)


@dataclass
class BotPlugin:
    slug: str
    display_name: str
    icon: str
    host: str              # must match a key in config.AGENT_URLS
    adapter_key: str       # must match an adapter registered on the agent

    @property
    def _client(self) -> AgentClient:
        return get_client()

    @property
    def base(self) -> str:
        return f"/adapters/{self.adapter_key}"

    # ──────────────────────────────────────────────────────────────

    async def summary(self) -> BotSummary:
        raw = await self._client.get(self.host, f"{self.base}/summary")
        return BotSummary.model_validate(raw)

    async def get_settings(self) -> tuple[SettingsSchema, SettingsValues]:
        raw = await self._client.get(self.host, f"{self.base}/settings")
        schema = SettingsSchema.model_validate(raw.get("schema") or {})
        values = SettingsValues.model_validate(raw.get("values") or {})
        return schema, values

    async def update_settings(self, patch: dict[str, Any]) -> SettingsValues:
        raw = await self._client.put(self.host, f"{self.base}/settings", json=patch)
        return SettingsValues.model_validate(raw)

    async def get_logs(self, cursor: str | None = None, limit: int = 200) -> LogsResponse:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        raw = await self._client.get(self.host, f"{self.base}/logs", params=params)
        return LogsResponse.model_validate(raw)

    async def run_action(self, action_key: str, params: dict[str, Any] | None = None) -> ActionResult:
        raw = await self._client.post(
            self.host,
            f"{self.base}/actions/{action_key}",
            json=params or {},
        )
        return ActionResult.model_validate(raw)
