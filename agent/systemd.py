"""Async subprocess wrappers for systemctl / journalctl via the root helpers.

Every call goes through sudo + a root-owned whitelist-validating helper
script (see plan §Security §5). The wrappers here ONLY choose the verb and
unit — the helper rejects anything outside its allowlist.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from agent import config
from shared.models import LogEntry, LogLevel, ServiceState

logger = logging.getLogger(__name__)


class SystemctlError(Exception):
    pass


@dataclass
class CommandResult:
    rc: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.rc == 0


async def _run(argv: list[str], timeout: float) -> CommandResult:
    """Run a subprocess with a hard timeout. Captures stdout and stderr."""
    logger.debug("subprocess: %s (timeout=%.1fs)", " ".join(argv), timeout)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("subprocess timed out after %.1fs: %s", timeout, " ".join(argv))
        try:
            proc.kill()
            await asyncio.wait_for(proc.communicate(), timeout=3)
        except Exception:
            pass
        raise
    return CommandResult(
        rc=proc.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


# ──────────────────────────────────────────────────────────────────────
# systemctl helpers
# ──────────────────────────────────────────────────────────────────────


_SYSTEMD_STATES = {
    "active": ServiceState.active,
    "inactive": ServiceState.inactive,
    "activating": ServiceState.activating,
    "deactivating": ServiceState.deactivating,
    "failed": ServiceState.failed,
}


async def service_state(unit: str, *, timeout: float = 5.0) -> ServiceState:
    argv = [config.SUDO_BIN, "-n", config.HELPER_SYSTEMCTL, "is-active", unit]
    try:
        result = await _run(argv, timeout=timeout)
    except asyncio.TimeoutError:
        return ServiceState.unknown

    out = result.stdout.strip()
    state = _SYSTEMD_STATES.get(out, ServiceState.unknown)
    if state == ServiceState.unknown and out:
        logger.debug("unknown systemd state for %s: %r", unit, out)
    return state


async def service_restart(unit: str, *, timeout: float | None = None) -> CommandResult:
    if timeout is None:
        timeout = config.ACTION_DEFAULT_TIMEOUT_SEC
    argv = [config.SUDO_BIN, "-n", config.HELPER_SYSTEMCTL, "restart", unit]
    result = await _run(argv, timeout=timeout)
    if not result.ok:
        raise SystemctlError(
            f"systemctl restart {unit} failed (rc={result.rc}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


async def service_start(unit: str, *, timeout: float | None = None) -> CommandResult:
    if timeout is None:
        timeout = config.ACTION_DEFAULT_TIMEOUT_SEC
    argv = [config.SUDO_BIN, "-n", config.HELPER_SYSTEMCTL, "start", unit]
    result = await _run(argv, timeout=timeout)
    if not result.ok:
        raise SystemctlError(
            f"systemctl start {unit} failed (rc={result.rc}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


async def service_stop(unit: str, *, timeout: float | None = None) -> CommandResult:
    if timeout is None:
        timeout = config.ACTION_DEFAULT_TIMEOUT_SEC
    argv = [config.SUDO_BIN, "-n", config.HELPER_SYSTEMCTL, "stop", unit]
    result = await _run(argv, timeout=timeout)
    if not result.ok:
        raise SystemctlError(
            f"systemctl stop {unit} failed (rc={result.rc}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


# ──────────────────────────────────────────────────────────────────────
# journalctl — tail logs for a specific unit
# ──────────────────────────────────────────────────────────────────────

_LEVEL_HINTS = (
    ("error", LogLevel.error),
    ("critical", LogLevel.critical),
    ("fatal", LogLevel.critical),
    ("warn", LogLevel.warning),
    ("info", LogLevel.info),
    ("debug", LogLevel.debug),
)


def _guess_level(message: str) -> LogLevel:
    low = message.lower()
    for hint, level in _LEVEL_HINTS:
        if hint in low:
            return level
    return LogLevel.info


async def journal_tail(
    unit: str,
    *,
    lines: int = 200,
    since_sec: int = 0,
    timeout: float = 10.0,
) -> list[LogEntry]:
    """Return recent journalctl entries for a unit as ``LogEntry`` list.

    The helper returns lines in ``short-iso`` format:
        ``2026-04-12T01:23:45+0000 hostname unit[pid]: message``
    """
    lines = max(1, min(1000, int(lines)))
    since_sec = max(0, int(since_sec))
    argv = [
        config.SUDO_BIN, "-n",
        config.HELPER_JOURNALCTL,
        unit, str(lines), str(since_sec),
    ]
    result = await _run(argv, timeout=timeout)
    if not result.ok:
        raise SystemctlError(
            f"journalctl for {unit} failed (rc={result.rc}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    entries: list[LogEntry] = []
    for raw in result.stdout.splitlines():
        raw = raw.rstrip()
        if not raw:
            continue
        # Parse "YYYY-MM-DDTHH:MM:SS+TZ hostname unit[pid]: msg"
        try:
            ts, rest = raw.split(" ", 1)
            _host, rest = rest.split(" ", 1)
            _prefix, _, msg = rest.partition(": ")
        except ValueError:
            ts = ""
            msg = raw
        entries.append(
            LogEntry(
                ts=ts,
                level=_guess_level(msg),
                message=msg,
                source="journald",
            )
        )
    return entries
