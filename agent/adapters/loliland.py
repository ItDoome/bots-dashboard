"""Adapter for the Loliland bonus claimer.

Loliland lives as a module inside lolz-bot, not a separate process. The
adapter reads its account store, summarizes per-account state, and can
trigger a manual claim via the ``watcher_system.loliland_cli`` module
running in the lolz-bot's own venv (not ``python -c``).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.adapters.base import BotAdapter
from agent.file_ops import read_json
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
            key="claim_all_now",
            label="Клеймить сейчас",
            description="Запуск check_and_claim_all() через loliland_cli",
            danger_level=DangerLevel.low,
            estimated_duration_sec=30,
        ),
    ]


class LolilandAdapter(BotAdapter):
    slug = "loliland"
    display_name = "Loliland Bonus Claimer"
    icon = "coins"

    def __init__(self, adapter_config: dict[str, Any]) -> None:
        super().__init__(adapter_config)
        self.working_dir = Path(adapter_config.get("working_dir", "/opt/tg_bot"))
        self.accounts_file = Path(
            adapter_config.get("accounts_file", self.working_dir / "loliland_accounts.json")
        )
        self.venv_python = Path(
            adapter_config.get("venv_python", self.working_dir / ".venv" / "bin" / "python")
        )
        self.cli_module = adapter_config.get("cli_module", "watcher_system.loliland_cli")
        # lolz-bot carries loliland; if lolz-bot is down loliland can't do anything
        self.host_systemd_unit: str | None = adapter_config.get("host_systemd_unit", "lolz-bot.service")

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
        data = await asyncio.to_thread(self._read_accounts)
        accounts: list[dict[str, Any]] = data.get("accounts") or []

        total_coins = sum(int(a.get("total_claimed", 0) or 0) for a in accounts)
        total_claims = sum(int(a.get("claim_count", 0) or 0) for a in accounts)
        with_password = sum(1 for a in accounts if a.get("password"))
        with_errors = [a for a in accounts if a.get("last_error")]

        # Pull last claim across all accounts
        last_claim_iso: str | None = None
        for a in accounts:
            ts = a.get("last_claim_at")
            if ts and (last_claim_iso is None or ts > last_claim_iso):
                last_claim_iso = ts

        # Is loliland itself reachable via its host bot?
        host_state = ServiceState.unknown
        if self.host_systemd_unit:
            try:
                host_state = await systemd.service_state(self.host_systemd_unit)
            except Exception as exc:
                logger.warning("loliland: host service check failed: %r", exc)

        health = HealthStatus.ok
        if host_state != ServiceState.active:
            health = HealthStatus.error
        elif with_errors:
            health = HealthStatus.warning
        elif not accounts:
            health = HealthStatus.warning

        message_bits: list[str] = []
        message_bits.append(f"{len(accounts)} аккаунт(ов)")
        if with_password:
            message_bits.append(f"{with_password} с паролем")
        if with_errors:
            message_bits.append(f"{len(with_errors)} с ошибкой")
        message = " · ".join(message_bits)

        primary = [
            MetricValue(label="Аккаунтов", value=len(accounts)),
            MetricValue(label="Всего coins", value=total_coins),
            MetricValue(label="Клеймов", value=total_claims),
        ]
        secondary = [
            MetricValue(
                label="Последний клейм",
                value=_format_iso(last_claim_iso),
            ),
            MetricValue(label="Аккаунтов с паролем", value=with_password),
            MetricValue(label="Ошибки", value=len(with_errors)),
        ]

        return BotSummary(
            slug=self.slug,
            status=host_state,
            health=health,
            primary_metrics=primary,
            secondary_metrics=secondary,
            message=message,
        )

    def _read_accounts(self) -> dict[str, Any]:
        try:
            return read_json(self.accounts_file) or {}
        except Exception as exc:
            logger.warning("loliland: accounts read failed: %r", exc)
            return {}

    async def run_action(self, key: str, params: dict[str, Any]) -> ActionResult:
        if key != "claim_all_now":
            return ActionResult(ok=False, error=f"unknown action: {key}")

        started = time.monotonic()
        argv = [str(self.venv_python), "-m", self.cli_module, "claim-all"]
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": str(self.working_dir),
            "LANG": "en_US.UTF-8",
            "PYTHONPATH": str(self.working_dir),
        }

        logger.info("loliland: running %s (cwd=%s)", " ".join(argv), self.working_dir)

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(self.working_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await proc.communicate()
            except Exception:
                pass
            return ActionResult(
                ok=False,
                error="claim_all_now timed out after 180s",
                duration_sec=time.monotonic() - started,
            )

        stdout_s = stdout.decode("utf-8", errors="replace").strip()
        stderr_s = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            return ActionResult(
                ok=False,
                error=f"exit={proc.returncode}: {stderr_s[:300] or stdout_s[:300]}",
                duration_sec=time.monotonic() - started,
            )

        # Parse the single-line JSON output from loliland_cli
        try:
            parsed = json.loads(stdout_s)
        except Exception as exc:
            return ActionResult(
                ok=False,
                error=f"bad JSON from cli: {exc!r}, raw={stdout_s[:200]}",
                duration_sec=time.monotonic() - started,
            )

        ok = bool(parsed.get("ok", True))
        claimed = parsed.get("claimed", 0)
        total = parsed.get("total", 0)
        amount = parsed.get("amount", 0)
        errors = parsed.get("errors", 0)

        if claimed > 0:
            msg = f"Собрано {amount} монет с {claimed} из {total} аккаунтов"
        elif errors > 0:
            msg = f"Не удалось собрать: {errors} ошибок из {total} аккаунтов"
        else:
            msg = f"Нечего собирать — {total} аккаунтов проверено, бонусы ещё не готовы"

        # Log the result so it shows up in the Logs tab (agent journal)
        logger.info("loliland: claim result — %s (claimed=%s total=%s amount=%s errors=%s)",
                     msg, claimed, total, amount, errors)

        return ActionResult(
            ok=ok,
            message=msg,
            duration_sec=time.monotonic() - started,
        )

    async def get_logs(self, cursor: str | None = None, limit: int = 200) -> LogsResponse:
        since_sec = 0
        if cursor:
            try:
                since_sec = max(0, int(cursor))
            except ValueError:
                since_sec = 0

        # Merge logs from two sources:
        # 1. lolz-bot journal (loliland module runs inside it)
        # 2. bots-dashboard-agent journal (our adapter logs claim results)
        bot_entries = []
        if self.host_systemd_unit:
            try:
                raw = await systemd.journal_tail(
                    self.host_systemd_unit, lines=limit, since_sec=since_sec,
                )
                bot_entries = [e for e in raw if "loliland" in e.message.lower()]
                for e in bot_entries:
                    e.source = "lolz-bot"
            except Exception:
                pass

        agent_entries = []
        try:
            raw = await systemd.journal_tail(
                "bots-dashboard-agent.service", lines=limit, since_sec=since_sec,
            )
            agent_entries = [e for e in raw if "loliland" in e.message.lower()]
            for e in agent_entries:
                e.source = "agent"
        except Exception:
            pass

        merged = bot_entries + agent_entries
        merged.sort(key=lambda e: e.ts or "")
        return LogsResponse(entries=merged[-limit:], next_cursor=None, has_more=False)


def _format_iso(iso: str | None) -> str:
    if not iso:
        return "никогда"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(tz=timezone.utc) - dt
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            return "<1 ч назад"
        if hours < 24:
            return f"{hours} ч назад"
        return f"{hours // 24} дн назад"
    except Exception:
        return iso
