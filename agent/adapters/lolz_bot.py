"""Adapter for lolz-bot (Valorant/miHoYo marketplace automation)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from agent import config as agent_config
from agent import systemd
from agent.adapters.base import BotAdapter
from agent.file_ops import patch_json, read_json
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
    SettingField,
    SettingFieldType,
    SettingsSchema,
    SettingsSection,
    SettingsValues,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Settings schema — what can be edited via the dashboard
# ──────────────────────────────────────────────────────────────────────

# Flat whitelist of keys that may be touched in state.json. Anything outside
# is rejected by file_ops.patch_json(). The list is intentionally tiny in v1.
STATE_WHITELIST = {
    "autosell_enabled",
    "autosell_interval_minutes",
}

# Whitelist for watcher_config.json — user-tunable knobs only, no paths/URLs.
WATCHER_WHITELIST = {
    "enabled",
    "enable_public_watcher",
    "enable_my_items_watcher",
    "autobuy_enabled",
    "autoreprice_enabled",
    "alerts_enabled",
    "alert_on_sold",
    "working_limit_rpm",
    "soft_limit_rpm",
    "emergency_limit_rpm",
    "reprice_after_hours",
    "autobuy_daily_budget",
    "max_consecutive_403",
}


def _build_schema() -> SettingsSchema:
    return SettingsSchema(
        sections=[
            SettingsSection(
                title="Autosell",
                description="Авто-продажа купленных аккаунтов Valorant",
                fields=[
                    SettingField(
                        path="state.autosell_enabled",
                        label="Включён",
                        type=SettingFieldType.boolean,
                        default=False,
                        help="Запускает цикл публикации автоматически",
                    ),
                    SettingField(
                        path="state.autosell_interval_minutes",
                        label="Интервал (минуты)",
                        type=SettingFieldType.integer,
                        default=15,
                        minimum=5,
                        maximum=240,
                        help="Пауза между циклами автосейла",
                    ),
                ],
            ),
            SettingsSection(
                title="Watcher / Autobuy",
                description="Отслеживание рынка и автопокупка лотов",
                fields=[
                    SettingField(
                        path="watcher.enabled",
                        label="Watcher включён",
                        type=SettingFieldType.boolean,
                        default=False,
                    ),
                    SettingField(
                        path="watcher.autobuy_enabled",
                        label="Autobuy включён",
                        type=SettingFieldType.boolean,
                        default=False,
                        help="Автопокупка лотов, проходящих через evaluate gate",
                    ),
                    SettingField(
                        path="watcher.autobuy_daily_budget",
                        label="Дневной бюджет (₽)",
                        type=SettingFieldType.integer,
                        default=5000,
                        minimum=0,
                        maximum=1_000_000,
                    ),
                    SettingField(
                        path="watcher.autoreprice_enabled",
                        label="Auto-reprice включён",
                        type=SettingFieldType.boolean,
                        default=False,
                    ),
                    SettingField(
                        path="watcher.alerts_enabled",
                        label="Алерты в Telegram",
                        type=SettingFieldType.boolean,
                        default=True,
                    ),
                    SettingField(
                        path="watcher.working_limit_rpm",
                        label="Rate limit: working (RPM)",
                        type=SettingFieldType.integer,
                        default=120,
                        minimum=10,
                        maximum=600,
                    ),
                    SettingField(
                        path="watcher.max_consecutive_403",
                        label="Max 403 подряд",
                        type=SettingFieldType.integer,
                        default=5,
                        minimum=1,
                        maximum=20,
                    ),
                ],
            ),
        ],
    )


def _actions() -> list[ActionDescriptor]:
    return [
        ActionDescriptor(
            key="restart_service",
            label="Перезапустить lolz-bot",
            description="systemctl restart lolz-bot.service",
            danger_level=DangerLevel.medium,
            confirm_prompt="Процесс будет перезапущен (несколько секунд downtime)",
            estimated_duration_sec=15,
        ),
        ActionDescriptor(
            key="start_service",
            label="Запустить",
            danger_level=DangerLevel.low,
        ),
        ActionDescriptor(
            key="stop_service",
            label="Остановить",
            danger_level=DangerLevel.high,
            confirm_prompt="Бот перестанет торговать до повторного запуска",
        ),
        ActionDescriptor(
            key="bump_now",
            label="Поднять аккаунты",
            description="Выберет top-10 лотов по приоритету и поднимет через API",
            danger_level=DangerLevel.medium,
            confirm_prompt="Будет потрачено до 10 платных поднятий. Приоритет: дорогие лоты (33-50₽) > дешёвые (29-30₽), внутри тира — самые старые.",
            estimated_duration_sec=30,
        ),
    ]


# ──────────────────────────────────────────────────────────────────────
# Adapter
# ──────────────────────────────────────────────────────────────────────


class LolzBotAdapter(BotAdapter):
    slug = "lolz_bot"
    display_name = "LOLZ Valorant Resell"
    icon = "bot"

    def __init__(self, adapter_config: dict[str, Any]) -> None:
        super().__init__(adapter_config)
        self.systemd_unit: str = adapter_config.get("systemd_unit", "lolz-bot.service")
        self.working_dir: Path = Path(adapter_config.get("working_dir", "/opt/tg_bot"))
        state_files = adapter_config.get("state_files") or {}
        self.state_json_path = Path(state_files.get("state_json", self.working_dir / "state.json"))
        self.watcher_config_path = Path(state_files.get("watcher", self.working_dir / "watcher_config.json"))
        self.watcher_diag_path = Path(state_files.get("watcher_diag", self.working_dir / "watcher_diagnostics.json"))
        self.loliland_store_path = Path(state_files.get("loliland", self.working_dir / "loliland_accounts.json"))
        self.monopoly_path = Path(state_files.get("monopoly", self.working_dir / "monopoly_snapshots.json"))

        # Tiny in-process cache to keep summary() cheap (30s TTL)
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
            supports_settings=True,
            supports_actions=True,
            supports_logs=True,
            action_keys=[a.key for a in descriptors],
            actions=descriptors,
        )

    # ──────────────────────────────────────────────────────────────

    async def summary(self) -> BotSummary:
        # 1. Service state via systemctl
        service_state = await systemd.service_state(self.systemd_unit)

        # 2. Read lightweight JSON files in a thread
        data = await asyncio.to_thread(self._read_files)

        state = data.get("state") or {}
        watcher_cfg = data.get("watcher_cfg") or {}
        loliland = data.get("loliland") or {"accounts": []}
        monopoly_latest = data.get("monopoly_latest")

        autosell_on = bool(state.get("autosell_enabled"))
        autosell_interval = int(state.get("autosell_interval_minutes") or 0)
        watcher_on = bool(watcher_cfg.get("enabled"))
        autobuy_on = bool(watcher_cfg.get("autobuy_enabled"))

        # loliland aggregate
        loli_accounts = loliland.get("accounts") or []
        loli_total_coins = sum(int(a.get("total_claimed", 0) or 0) for a in loli_accounts)

        # monopoly — if we have a snapshot, pull the freshest
        sold_24h = 0
        active_miho = 0
        share = 0.0
        revenue_24h = 0.0
        sold_7d_avg = 0.0
        revenue_7d = 0.0
        mayo_count = 0
        mayo_oldest = 0
        total_cheap = 0
        my_cheap = 0
        sellers: dict[str, int] = {}
        new_competitors: dict[str, int] = {}
        price_dist: dict[str, int] = {}
        if isinstance(monopoly_latest, dict):
            sold_24h = int(monopoly_latest.get("my_sold_24h", 0) or 0)
            active_miho = int(monopoly_latest.get("my_mihoyo_active", 0) or 0)
            revenue_24h = float(monopoly_latest.get("my_revenue_24h", 0) or 0)
            sold_7d_avg = float(monopoly_latest.get("my_sold_7d_avg", 0) or 0)
            revenue_7d = float(monopoly_latest.get("my_revenue_7d", 0) or 0)
            mayo_count = int(monopoly_latest.get("mayo_cheap_count", 0) or 0)
            mayo_oldest = int(monopoly_latest.get("mayo_cheap_oldest_age_days", 0) or 0)
            total_cheap = int(monopoly_latest.get("total_cheap_zone", 0) or 0)
            my_cheap = int(monopoly_latest.get("my_cheap_zone_count", 0) or 0)
            sellers = monopoly_latest.get("cheap_market_sellers") or {}
            new_competitors = monopoly_latest.get("new_competitors_7d") or {}
            price_dist = monopoly_latest.get("my_price_distribution") or {}
            try:
                share = float(monopoly_latest.get("my_cheap_zone_share", 0) or 0)
            except (TypeError, ValueError):
                share = 0.0

        health = HealthStatus.ok
        if service_state != ServiceState.active:
            health = HealthStatus.error
        elif not autosell_on and not watcher_on:
            health = HealthStatus.warning

        message_bits = []
        if autosell_on:
            message_bits.append(f"autosell ON ({autosell_interval}m)")
        if watcher_on:
            message_bits.append("watcher ON")
        if autobuy_on:
            message_bits.append("autobuy ON")
        message = " · ".join(message_bits) if message_bits else "всё выключено"

        primary = [
            MetricValue(label="miHoYo активных", value=active_miho, unit="лот"),
            MetricValue(label="Продано 24ч", value=sold_24h),
            MetricValue(label="Выручка 24ч", value=f"{revenue_24h:.0f}", unit="₽"),
        ]
        secondary = [
            MetricValue(label="Avg продаж 7д", value=f"{sold_7d_avg:.1f}", unit="/день"),
            MetricValue(label="Выручка 7д", value=f"{revenue_7d:.0f}", unit="₽"),
            MetricValue(label="Autosell interval", value=autosell_interval, unit="мин"),
            MetricValue(label="Loliland coins", value=loli_total_coins),
            MetricValue(label="Loliland аккаунтов", value=len(loli_accounts)),
        ]

        # Structured monopoly data for the frontend MonopolyCard.
        # Primary source: API (my_cheap_zone_count). Fallback: parser (sellers dict).
        # Replace the parser's "me" entry with the API count so badge and bar match.
        final_sellers = dict(sellers)
        if final_sellers and my_cheap > 0:
            me_name = max(final_sellers, key=final_sellers.get)  # type: ignore[arg-type]
            final_sellers[me_name] = my_cheap
        final_total = sum(final_sellers.values()) if final_sellers else total_cheap

        monopoly_extra = {
            "share_pct": (my_cheap / final_total * 100) if final_total > 0 else share,
            "my_count": my_cheap,
            "total_count": final_total,
            "mayo_count": mayo_count,
            "mayo_oldest_days": mayo_oldest,
            "price_distribution": price_dist,
            "sellers": final_sellers,
            "new_competitors_7d": new_competitors,
            "sold_24h": sold_24h,
            "revenue_24h": revenue_24h,
            "sold_7d_avg": sold_7d_avg,
            "revenue_7d": revenue_7d,
        } if total_cheap > 0 else None

        return BotSummary(
            slug=self.slug,
            status=service_state,
            health=health,
            primary_metrics=primary,
            secondary_metrics=secondary,
            message=message,
            extra={"monopoly": monopoly_extra} if monopoly_extra else None,
        )

    def _read_files(self) -> dict[str, Any]:
        """Blocking reads — must be wrapped by asyncio.to_thread by caller."""
        now = time.monotonic()
        if self._cache and (now - self._cache_ts) < agent_config.COUNT_CACHE_TTL_SEC:
            return self._cache

        out: dict[str, Any] = {}
        try:
            out["state"] = read_json(self.state_json_path) or {}
        except Exception as exc:
            logger.warning("lolz: state.json read failed: %r", exc)
            out["state"] = {}
        try:
            out["watcher_cfg"] = read_json(self.watcher_config_path) or {}
        except Exception as exc:
            logger.warning("lolz: watcher_config.json read failed: %r", exc)
            out["watcher_cfg"] = {}
        try:
            out["loliland"] = read_json(self.loliland_store_path) or {}
        except Exception as exc:
            logger.warning("lolz: loliland store read failed: %r", exc)
            out["loliland"] = {}
        try:
            monopoly = read_json(self.monopoly_path) or {}
            snapshots = monopoly.get("snapshots") if isinstance(monopoly, dict) else None
            out["monopoly_latest"] = snapshots[-1] if snapshots else None
        except Exception as exc:
            logger.warning("lolz: monopoly snapshots read failed: %r", exc)
            out["monopoly_latest"] = None

        self._cache = out
        self._cache_ts = now
        return out

    # ──────────────────────────────────────────────────────────────

    async def get_settings(self) -> tuple[SettingsSchema, SettingsValues]:
        data = await asyncio.to_thread(self._read_files)
        state = data.get("state") or {}
        watcher_cfg = data.get("watcher_cfg") or {}
        values: dict[str, Any] = {}
        for key in STATE_WHITELIST:
            values[f"state.{key}"] = state.get(key)
        for key in WATCHER_WHITELIST:
            values[f"watcher.{key}"] = watcher_cfg.get(key)
        return _build_schema(), SettingsValues(values=values)

    async def update_settings(self, patch: dict[str, Any]) -> SettingsValues:
        """Apply a settings patch. Keys are ``state.XXX`` or ``watcher.XXX``."""
        state_patch: dict[str, Any] = {}
        watcher_patch: dict[str, Any] = {}
        bad: list[str] = []
        for key, value in patch.items():
            if key.startswith("state."):
                sub = key.split(".", 1)[1]
                if sub not in STATE_WHITELIST:
                    bad.append(key)
                    continue
                state_patch[sub] = value
            elif key.startswith("watcher."):
                sub = key.split(".", 1)[1]
                if sub not in WATCHER_WHITELIST:
                    bad.append(key)
                    continue
                watcher_patch[sub] = value
            else:
                bad.append(key)
        if bad:
            raise ValueError(f"keys not allowed: {sorted(bad)}")

        if state_patch:
            await asyncio.to_thread(
                patch_json, self.state_json_path, state_patch,
                whitelist=STATE_WHITELIST,
            )
        if watcher_patch:
            await asyncio.to_thread(
                patch_json, self.watcher_config_path, watcher_patch,
                whitelist=WATCHER_WHITELIST,
            )

        # Invalidate the cache so the next summary() re-reads files
        self._cache_ts = 0.0

        _schema, values = await self.get_settings()
        return values

    # ──────────────────────────────────────────────────────────────

    async def run_action(self, key: str, params: dict[str, Any]) -> ActionResult:
        started = time.monotonic()

        # Systemctl actions
        if key in ("restart_service", "start_service", "stop_service"):
            try:
                if key == "restart_service":
                    await systemd.service_restart(self.systemd_unit)
                    msg = f"restarted {self.systemd_unit}"
                elif key == "start_service":
                    await systemd.service_start(self.systemd_unit)
                    msg = f"started {self.systemd_unit}"
                else:
                    await systemd.service_stop(self.systemd_unit)
                    msg = f"stopped {self.systemd_unit}"
            except Exception as exc:
                return ActionResult(
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}"[:400],
                    duration_sec=time.monotonic() - started,
                )
            self._cache_ts = 0.0
            return ActionResult(ok=True, message=msg, duration_sec=time.monotonic() - started)

        # Auto-bump — fire-and-forget. Fetch + bump takes ~90 seconds,
        # way too long for a synchronous HTTP request. We launch the process
        # detached and return immediately. Result goes to journal (visible
        # in the Logs tab).
        if key == "bump_now":
            import subprocess as _sp
            count = int(params.get("count", 10))
            argv = [
                str(self.working_dir / ".venv" / "bin" / "python"),
                "-m", "watcher_system.auto_bump_cli", "bump",
                "--count", str(count),
            ]
            env = {
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": str(self.working_dir),
                "LANG": "en_US.UTF-8",
                "PYTHONPATH": str(self.working_dir),
            }
            logger.info("lolz: launching auto-bump in background: %s", " ".join(argv))

            # Use systemd-run to get output in journal, or plain Popen
            # with output to a log file.
            log_path = self.working_dir / "auto_bump_last.log"
            log_fd = open(log_path, "w")
            _sp.Popen(
                argv,
                cwd=str(self.working_dir),
                env=env,
                stdout=log_fd,
                stderr=_sp.STDOUT,
                start_new_session=True,
            )

            return ActionResult(
                ok=True,
                message=f"Запущено в фоне (до {count} лотов). Результат через ~90 сек в логах.",
                duration_sec=time.monotonic() - started,
            )

        return ActionResult(ok=False, error=f"unknown action: {key}")

    # ──────────────────────────────────────────────────────────────

    async def get_logs(
        self, cursor: str | None = None, limit: int = 200
    ) -> LogsResponse:
        # cursor is "seconds_ago" integer for v1
        since_sec = 0
        if cursor:
            try:
                since_sec = max(0, int(cursor))
            except ValueError:
                since_sec = 0
        entries = await systemd.journal_tail(
            self.systemd_unit, lines=limit, since_sec=since_sec,
        )
        return LogsResponse(entries=entries, next_cursor=None, has_more=False)
