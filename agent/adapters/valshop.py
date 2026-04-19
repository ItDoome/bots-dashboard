"""Adapter for Valorant Shop bot (sub-module of lolz-bot).

valshop lives at /opt/valorant-shop/ and is loaded as an aiogram router
inside lolz-bot.service. It has its own SQLite (users.db), a skins cache
(skins_cache.json), and a daily broadcast log (daily.log).

There's no separate systemd unit — health follows lolz-bot.service.
Actions: rebuild skins cache, run daily broadcast.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from agent.adapters.base import BotAdapter
from agent import systemd
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


def _actions() -> list[ActionDescriptor]:
    return [
        ActionDescriptor(
            key="run_daily",
            label="Запустить daily broadcast",
            description="Вручную прогнать рассылку скинов всем юзерам",
            danger_level=DangerLevel.medium,
            confirm_prompt="Отправит сообщения всем подписчикам valshop прямо сейчас",
            estimated_duration_sec=60,
        ),
        ActionDescriptor(
            key="rebuild_cache",
            label="Пересобрать skins cache",
            description="Скачать свежий список всех скинов Valorant из API",
            danger_level=DangerLevel.low,
            estimated_duration_sec=30,
        ),
    ]


class ValshopAdapter(BotAdapter):
    slug = "valshop"
    display_name = "Valorant Shop"
    icon = "swords"

    def __init__(self, adapter_config: dict[str, Any]) -> None:
        super().__init__(adapter_config)
        self.working_dir = Path(adapter_config.get("working_dir", "/opt/valorant-shop"))
        self.db_path = Path(adapter_config.get("db_path", self.working_dir / "users.db"))
        self.skins_cache_path = Path(adapter_config.get("skins_cache", self.working_dir / "skins_cache.json"))
        self.daily_log_path = Path(adapter_config.get("daily_log", self.working_dir / "daily.log"))
        self.venv_python = Path(adapter_config.get("venv_python", self.working_dir / "venv" / "bin" / "python"))
        self.host_systemd_unit = adapter_config.get("host_systemd_unit", "lolz-bot.service")

        self._cache_ts: float = 0.0
        self._cache: dict[str, Any] = {}

    async def capabilities(self) -> AdapterCapabilities:
        descriptors = _actions()
        return AdapterCapabilities(
            key=self.slug,
            display_name=self.display_name,
            icon=self.icon,
            supports_summary=True,
            supports_settings=False,
            supports_actions=True,
            supports_logs=True,
            action_keys=[a.key for a in descriptors],
            actions=descriptors,
        )

    async def summary(self) -> BotSummary:
        host_state = await systemd.service_state(self.host_systemd_unit)

        stats = await asyncio.to_thread(self._read_stats)
        # Fetch live shop snapshot (Riot API call, cached 2 min)
        snap = await self._get_snapshot()

        users_count = stats.get("users")
        cache_age_sec = stats.get("cache_age_sec")
        last_daily_ago_sec = stats.get("last_daily_ago_sec")

        wallet = (snap or {}).get("wallet") or {}
        daily = (snap or {}).get("daily") or {}
        bundle = (snap or {}).get("bundle") or {}

        health = HealthStatus.ok
        if host_state != ServiceState.active:
            health = HealthStatus.error
        elif not snap or not snap.get("ok"):
            health = HealthStatus.warning

        # Short status line
        msg_bits = []
        if wallet:
            msg_bits.append(f"{wallet.get('vp', 0)} VP · {wallet.get('kc', 0)} KC")
        if daily.get("items"):
            msg_bits.append(f"daily: {len(daily['items'])} скинов")
        message = " · ".join(msg_bits) if msg_bits else "нет данных"

        primary = [
            MetricValue(label="Valorant Points", value=wallet.get("vp", "—"), unit="VP"),
            MetricValue(label="Kingdom Credits", value=wallet.get("kc", "—"), unit="KC"),
            MetricValue(
                label="До обновы Daily",
                value=_fmt_age(daily.get("remaining_sec")) if daily.get("remaining_sec") else "—",
            ),
        ]
        secondary = [
            MetricValue(label="Radianite", value=wallet.get("rad", "—"), unit="RP"),
            MetricValue(label="Bundle осталось", value=_fmt_age(bundle.get("remaining_sec")) if bundle.get("remaining_sec") else "—"),
            MetricValue(label="Пользователей", value=_metric(users_count), unit="чел"),
            MetricValue(label="Last daily run", value=_fmt_age(last_daily_ago_sec) if last_daily_ago_sec else "никогда"),
            MetricValue(label="Host service", value=host_state.value),
        ]

        return BotSummary(
            slug=self.slug,
            status=host_state,
            health=health,
            primary_metrics=primary,
            secondary_metrics=secondary,
            message=message,
            extra={"valshop": snap} if snap and snap.get("ok") else None,
        )

    async def _get_snapshot(self) -> dict | None:
        """Invoke dashboard_snapshot.py as subprocess — cached 2 min."""
        now = time.monotonic()
        if hasattr(self, "_snap_ts") and (now - self._snap_ts) < 120:
            return getattr(self, "_snap", None)

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.venv_python),
                str(self.working_dir / "dashboard_snapshot.py"),
                cwd=str(self.working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            import json as _json
            snap = _json.loads(stdout.decode("utf-8", errors="replace"))
        except Exception as exc:
            logger.warning("valshop: snapshot subprocess failed: %r", exc)
            snap = {"ok": False, "error": str(exc)}

        self._snap = snap
        self._snap_ts = now
        return snap

    def _read_stats(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cache and (now - self._cache_ts) < 30:
            return self._cache

        out: dict[str, Any] = {}

        # SQLite users
        if self.db_path.exists():
            try:
                uri = f"file:{self.db_path}?mode=ro"
                conn = sqlite3.connect(uri, uri=True, timeout=3)
                try:
                    row = conn.execute("SELECT COUNT(*) FROM users;").fetchone()
                    out["users"] = int(row[0]) if row else 0
                    row = conn.execute(
                        "SELECT COUNT(*) FROM login_tokens WHERE expires_at > strftime('%s','now') AND used_at IS NULL;"
                    ).fetchone()
                    out["tokens_active"] = int(row[0]) if row else 0
                finally:
                    conn.close()
            except Exception as exc:
                logger.warning("valshop: db read failed: %r", exc)
                out["users"] = None
                out["tokens_active"] = None
        else:
            out["users"] = None
            out["tokens_active"] = None

        # Skins cache
        if self.skins_cache_path.exists():
            try:
                stat = self.skins_cache_path.stat()
                out["cache_size_kb"] = int(stat.st_size / 1024)
                out["cache_age_sec"] = int(time.time() - stat.st_mtime)
            except Exception:
                out["cache_size_kb"] = None
                out["cache_age_sec"] = None

        # Last daily run
        if self.daily_log_path.exists():
            try:
                stat = self.daily_log_path.stat()
                out["last_daily_ago_sec"] = int(time.time() - stat.st_mtime)
            except Exception:
                out["last_daily_ago_sec"] = None

        self._cache = out
        self._cache_ts = now
        return out

    async def run_action(self, key: str, params: dict[str, Any]) -> ActionResult:
        started = time.monotonic()
        if key == "rebuild_cache":
            argv = [str(self.venv_python), "-c",
                    "import shop; shop.refresh_skins_cache('/opt/valorant-shop/skins_cache.json'); print('ok')"]
            return await self._run_subprocess(argv, started, timeout=60, success_msg="Skins cache обновлён")

        if key == "run_daily":
            # Fire daily broadcast script in background
            import subprocess as _sp
            log_path = self.working_dir / "daily.log"
            _sp.Popen(
                [str(self.venv_python), str(self.working_dir / "daily.py")],
                cwd=str(self.working_dir),
                stdout=open(log_path, "a"),
                stderr=_sp.STDOUT,
                start_new_session=True,
            )
            return ActionResult(
                ok=True,
                message="Daily broadcast запущен в фоне, результат в логах через ~60 сек",
                duration_sec=time.monotonic() - started,
            )

        return ActionResult(ok=False, error=f"unknown action: {key}")

    async def _run_subprocess(self, argv: list[str], started: float, timeout: float, success_msg: str) -> ActionResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self.working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            return ActionResult(ok=False, error=f"timed out after {timeout}s",
                                duration_sec=time.monotonic() - started)
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:300]
            return ActionResult(ok=False, error=f"exit={proc.returncode}: {err}",
                                duration_sec=time.monotonic() - started)
        self._cache_ts = 0.0
        return ActionResult(ok=True, message=success_msg, duration_sec=time.monotonic() - started)

    async def get_logs(self, cursor: str | None = None, limit: int = 200) -> LogsResponse:
        """Read daily.log + filter lolz-bot journal by 'valshop'."""
        # 1. Read daily.log tail
        entries = []
        try:
            text = await asyncio.to_thread(self._read_daily_log)
            for line in text.splitlines()[-limit:]:
                if not line.strip():
                    continue
                from shared.models import LogEntry, LogLevel
                entries.append(LogEntry(
                    ts=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.daily_log_path.stat().st_mtime)),
                    level=LogLevel.error if "error" in line.lower() or "fail" in line.lower() else LogLevel.info,
                    message=line[:500],
                    source="daily.log",
                ))
        except Exception as exc:
            logger.warning("valshop: daily log read failed: %r", exc)

        # 2. Tail lolz-bot journal, filter valshop
        since_sec = int(cursor) if cursor and cursor.isdigit() else 600
        try:
            host_entries = await systemd.journal_tail(
                self.host_systemd_unit, lines=limit, since_sec=since_sec,
            )
            for e in host_entries:
                if "valshop" in e.message.lower():
                    e.source = "valshop"
                    entries.append(e)
        except Exception:
            pass

        entries.sort(key=lambda e: e.ts or "")
        return LogsResponse(entries=entries[-limit:], next_cursor=None, has_more=False)

    def _read_daily_log(self) -> str:
        if not self.daily_log_path.exists():
            return ""
        with open(self.daily_log_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


def _metric(value: Any) -> str | int:
    if value is None:
        return "—"
    return value


def _fmt_age(sec: int | None) -> str:
    if sec is None:
        return "—"
    if sec < 60:
        return f"{sec}с"
    if sec < 3600:
        return f"{sec // 60} мин"
    if sec < 86400:
        return f"{sec // 3600} ч"
    return f"{sec // 86400} дн"
