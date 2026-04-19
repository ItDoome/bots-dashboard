"""Adapter for rebot (ReManga card game / gamification bot).

rebot lives on server B at /opt/rebot/current/. It owns a single SQLite
database (bot.sqlite3) and two systemd units:
    - rebot-bot.service      — the Telegram bot process
    - rebot-crawler.service  — the ReManga card crawler

For v1 this adapter is **read + restart only** — no config/DB mutations.
Queries are wrapped in try/except so a schema drift on the bot side
doesn't poison the whole summary() call. Missing tables are reported as
``None`` metrics rather than as errors.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from agent import config as agent_config
from agent import systemd
from agent.adapters.base import BotAdapter
from shared.models import (
    ActionDescriptor,
    ActionResult,
    AdapterCapabilities,
    BotSummary,
    DangerLevel,
    HealthStatus,
    LogsResponse,
    MetricValue,
    ServiceState,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Actions — read + restart only, no mutations
# ──────────────────────────────────────────────────────────────────────


def _actions() -> list[ActionDescriptor]:
    return [
        ActionDescriptor(
            key="restart_bot",
            label="Перезапустить rebot-bot",
            description="systemctl restart rebot-bot.service",
            danger_level=DangerLevel.medium,
            confirm_prompt="Telegram-бот перезапустится, ~5–10 сек downtime",
            estimated_duration_sec=15,
        ),
        ActionDescriptor(
            key="restart_crawler",
            label="Перезапустить rebot-crawler",
            description="systemctl restart rebot-crawler.service",
            danger_level=DangerLevel.medium,
            confirm_prompt="Crawler перезапустится, очередь обновится",
            estimated_duration_sec=15,
        ),
        ActionDescriptor(
            key="start_bot",
            label="Запустить rebot-bot",
            danger_level=DangerLevel.low,
        ),
        ActionDescriptor(
            key="stop_bot",
            label="Остановить rebot-bot",
            danger_level=DangerLevel.high,
            confirm_prompt="Бот перестанет отвечать пользователям",
        ),
        ActionDescriptor(
            key="start_crawler",
            label="Запустить rebot-crawler",
            danger_level=DangerLevel.low,
        ),
        ActionDescriptor(
            key="stop_crawler",
            label="Остановить rebot-crawler",
            danger_level=DangerLevel.high,
            confirm_prompt="Crawler остановится, новые карты не появятся",
        ),
    ]


_ACTION_DISPATCH = {
    "restart_bot":     ("bot_unit",     systemd.service_restart),
    "restart_crawler": ("crawler_unit", systemd.service_restart),
    "start_bot":       ("bot_unit",     systemd.service_start),
    "stop_bot":        ("bot_unit",     systemd.service_stop),
    "start_crawler":   ("crawler_unit", systemd.service_start),
    "stop_crawler":    ("crawler_unit", systemd.service_stop),
}


# ──────────────────────────────────────────────────────────────────────
# Adapter
# ──────────────────────────────────────────────────────────────────────


class RebotAdapter(BotAdapter):
    slug = "rebot"
    display_name = "reBot ReManga"
    icon = "gamepad-2"

    def __init__(self, adapter_config: dict[str, Any]) -> None:
        super().__init__(adapter_config)
        self.working_dir = Path(adapter_config.get("working_dir", "/opt/rebot/current"))
        self.db_path = Path(
            adapter_config.get("db_path", self.working_dir / "bot.sqlite3")
        )
        self.bot_unit: str = adapter_config.get("bot_unit", "rebot-bot.service")
        self.crawler_unit: str = adapter_config.get("crawler_unit", "rebot-crawler.service")

        # 30s cache to keep summary() cheap and avoid hammering the bot's DB
        # (the bot itself writes to it constantly).
        self._cache_ts: float = 0.0
        self._cache: dict[str, Any] = {}

    # ──────────────────────────────────────────────────────────────

    async def capabilities(self) -> AdapterCapabilities:
        descriptors = _actions()
        return AdapterCapabilities(
            key=self.slug,
            display_name=self.display_name,
            icon=self.icon,
            supports_summary=True,
            supports_settings=False,   # read-only in v1
            supports_actions=True,
            supports_logs=True,
            action_keys=[a.key for a in descriptors],
            actions=descriptors,
        )

    # ──────────────────────────────────────────────────────────────

    async def summary(self) -> BotSummary:
        bot_state, crawler_state = await asyncio.gather(
            systemd.service_state(self.bot_unit),
            systemd.service_state(self.crawler_unit),
        )

        stats = await asyncio.to_thread(self._collect_db_stats)

        health = HealthStatus.ok
        if bot_state != ServiceState.active:
            health = HealthStatus.error
        elif crawler_state != ServiceState.active:
            health = HealthStatus.warning
        elif stats.get("_errors"):
            health = HealthStatus.warning

        message_bits: list[str] = []
        if bot_state == ServiceState.active:
            message_bits.append("bot ON")
        else:
            message_bits.append(f"bot {bot_state.value}")
        if crawler_state == ServiceState.active:
            message_bits.append("crawler ON")
        else:
            message_bits.append(f"crawler {crawler_state.value}")
        message = " · ".join(message_bits)

        linked_profiles = stats.get("linked_profiles")
        tg_users = stats.get("tg_users")
        active_cards = stats.get("new_card_subscriptions")
        total_deliveries = stats.get("total_deliveries")
        total_events = stats.get("total_events")
        total_bank_cards = stats.get("bank_cards")
        deposit_pending = stats.get("deposit_pending")

        primary = [
            MetricValue(
                label="Привязано ReManga",
                value=_metric(linked_profiles),
                unit="проф",
            ),
            MetricValue(
                label="Карт выдано",
                value=_metric(total_bank_cards),
            ),
            MetricValue(
                label="Доставок всего",
                value=_metric(total_deliveries),
            ),
        ]
        secondary = [
            MetricValue(
                label="Событий всего",
                value=_metric(total_events),
            ),
            MetricValue(
                label="Подписок на карты",
                value=_metric(active_cards),
            ),
            MetricValue(
                label="Депозиты в ожидании",
                value=_metric(deposit_pending),
            ),
            MetricValue(
                label="rebot-bot",
                value=bot_state.value,
            ),
            MetricValue(
                label="rebot-crawler",
                value=crawler_state.value,
            ),
        ]

        # Pick the worst systemd state as the top-level card status so it
        # shows up on /dashboard as a single dot.
        status = bot_state
        if status == ServiceState.active and crawler_state != ServiceState.active:
            status = crawler_state

        return BotSummary(
            slug=self.slug,
            status=status,
            health=health,
            primary_metrics=primary,
            secondary_metrics=secondary,
            message=message,
        )

    # ──────────────────────────────────────────────────────────────

    def _collect_db_stats(self) -> dict[str, Any]:
        """Blocking SQLite reads — caller must wrap in ``asyncio.to_thread``.

        Every query is individually try/except'ed so a missing table or a
        renamed column doesn't poison the whole summary. Errors are
        collected into ``_errors`` and surfaced via HealthStatus.warning.
        """
        now = time.monotonic()
        if self._cache and (now - self._cache_ts) < agent_config.COUNT_CACHE_TTL_SEC:
            return self._cache

        out: dict[str, Any] = {"_errors": []}

        if not self.db_path.exists():
            out["_errors"].append(f"db not found: {self.db_path}")
            self._cache = out
            self._cache_ts = now
            return out

        try:
            # Read-only mode. botsagent has rwx ACL on the parent dir so
            # SQLite can create/update the -shm file needed for WAL reads.
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=3.0)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA busy_timeout = 2000;")

                existing_tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table';"
                    ).fetchall()
                }

                def _count(table: str) -> int | None:
                    if table not in existing_tables:
                        return None
                    try:
                        row = conn.execute(
                            f"SELECT COUNT(*) AS c FROM {table};"
                        ).fetchone()
                        return int(row["c"]) if row else None
                    except sqlite3.Error as exc:
                        out["_errors"].append(f"{table}: {exc}")
                        return None

                def _count_where(table: str, where: str) -> int | None:
                    if table not in existing_tables:
                        return None
                    try:
                        row = conn.execute(
                            f"SELECT COUNT(*) AS c FROM {table} WHERE {where};"
                        ).fetchone()
                        return int(row["c"]) if row else None
                    except sqlite3.Error as exc:
                        out["_errors"].append(f"{table}: {exc}")
                        return None

                out["linked_profiles"] = _count("linked_profiles")
                out["tg_users"] = _count("tg_user_settings")
                out["bank_cards"] = _count("bank_cards")

                out["new_card_subscriptions"] = _count("new_card_subscriptions")
                out["total_deliveries"] = _count("new_card_deliveries")
                out["total_events"] = _count("user_event_logs")

                # Pending / open deposit requests — real schema uses
                # status='wait_accept' for pending trades. Fall back to
                # counting all rows if the status column is absent.
                out["deposit_pending"] = None
                if "bank_deposit_requests" in existing_tables:
                    for where_clause in (
                        "status = 'wait_accept'",
                        "status = 'pending'",
                        "status = 'new'",
                        "1=1",
                    ):
                        val = _count_where("bank_deposit_requests", where_clause)
                        if val is not None:
                            out["deposit_pending"] = val
                            break
            finally:
                conn.close()
        except sqlite3.Error as exc:
            out["_errors"].append(f"sqlite: {exc}")
        except Exception as exc:
            logger.warning("rebot: db read failed: %r", exc)
            out["_errors"].append(f"{type(exc).__name__}: {exc}")

        self._cache = out
        self._cache_ts = now
        return out

    @staticmethod
    def _count_last_24h(
        conn: sqlite3.Connection,
        table: str,
        existing_tables: set[str],
        errors: list[str],
    ) -> int | None:
        """Try a few common timestamp column names for a 24h count.

        rebot's schema uses unix epoch integers in most event tables — we
        try ``created_at``, ``ts``, ``timestamp``, ``delivered_at`` in turn.
        """
        if table not in existing_tables:
            return None
        try:
            cols = {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({table});").fetchall()
            }
        except sqlite3.Error as exc:
            errors.append(f"{table}.pragma: {exc}")
            return None

        candidates = ("created_at", "ts", "timestamp", "delivered_at", "event_ts")
        for col in candidates:
            if col not in cols:
                continue
            try:
                row = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table} "
                    f"WHERE {col} >= strftime('%s', 'now') - 86400;"
                ).fetchone()
                if row is not None:
                    return int(row["c"])
            except sqlite3.Error as exc:
                errors.append(f"{table}.{col}: {exc}")
                continue
        return None

    # ──────────────────────────────────────────────────────────────

    async def run_action(self, key: str, params: dict[str, Any]) -> ActionResult:
        dispatch = _ACTION_DISPATCH.get(key)
        if not dispatch:
            return ActionResult(ok=False, error=f"unknown action: {key}")

        attr_name, fn = dispatch
        unit = getattr(self, attr_name)

        started = time.monotonic()
        try:
            await fn(unit)
        except Exception as exc:
            return ActionResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}"[:400],
                duration_sec=time.monotonic() - started,
            )

        # Invalidate cache so next summary reflects the fresh state.
        self._cache_ts = 0.0
        return ActionResult(
            ok=True,
            message=f"{key} -> {unit}",
            duration_sec=time.monotonic() - started,
        )

    # ──────────────────────────────────────────────────────────────

    async def get_logs(self, cursor: str | None = None, limit: int = 200) -> LogsResponse:
        # rebot has two services — v1 merges logs from both and interleaves
        # them by timestamp prefix.
        since_sec = 0
        if cursor:
            try:
                since_sec = max(0, int(cursor))
            except ValueError:
                since_sec = 0

        # Split the limit roughly 50/50 between the two units so neither
        # side starves out the other.
        per_unit = max(10, limit // 2)
        bot_entries, crawler_entries = await asyncio.gather(
            systemd.journal_tail(self.bot_unit, lines=per_unit, since_sec=since_sec),
            systemd.journal_tail(self.crawler_unit, lines=per_unit, since_sec=since_sec),
            return_exceptions=True,
        )

        entries = []
        if isinstance(bot_entries, list):
            for e in bot_entries:
                e.source = "rebot-bot"
                entries.append(e)
        if isinstance(crawler_entries, list):
            for e in crawler_entries:
                e.source = "rebot-crawler"
                entries.append(e)

        entries.sort(key=lambda e: e.ts or "")
        entries = entries[-limit:]
        return LogsResponse(entries=entries, next_cursor=None, has_more=False)


def _metric(value: Any) -> str | int:
    if value is None:
        return "—"
    return value
