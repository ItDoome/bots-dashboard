"""Agent runtime configuration."""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_ENV_PATH = Path(os.environ.get("AGENT_ENV_FILE", "/etc/bots-dashboard-agent/env"))


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        out[k.strip()] = v
    return out


_env_file = _load_env_file(DEFAULT_ENV_PATH)


def _env(key: str, default: str = "") -> str:
    return _env_file.get(key) or os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


# Agent identity — must match a key in the central app's inventory.yaml
AGENT_ID = _env("AGENT_ID", "server-a")
VERSION = _env("AGENT_VERSION", "0.1.0-dev")
BUILD_SHA = _env("AGENT_BUILD_SHA", "dev")

# Bearer token shared with the central app.
AGENT_TOKEN = _env("AGENT_TOKEN", "")

# HTTP binding — always loopback, never public.
LISTEN_HOST = _env("AGENT_HOST", "127.0.0.1")
LISTEN_PORT = _env_int("AGENT_PORT", 8765)

# Manifest path — YAML describing which adapters to load and with what config.
MANIFEST_PATH = Path(_env("AGENT_MANIFEST", "/etc/bots-dashboard-agent/manifest.yaml"))

# Helper scripts (root-owned, accessed via sudo) — see plan §Security §5.
SUDO_BIN = _env("SUDO_BIN", "/usr/bin/sudo")
HELPER_SYSTEMCTL = _env("HELPER_SYSTEMCTL", "/usr/local/bin/botsdash-systemctl")
HELPER_JOURNALCTL = _env("HELPER_JOURNALCTL", "/usr/local/bin/botsdash-journalctl")

# Timing
ACTION_DEFAULT_TIMEOUT_SEC = _env_int("ACTION_DEFAULT_TIMEOUT_SEC", 60)
ACTION_CLAIM_TIMEOUT_SEC = _env_int("ACTION_CLAIM_TIMEOUT_SEC", 180)
COUNT_CACHE_TTL_SEC = _env_int("COUNT_CACHE_TTL_SEC", 30)

# Backups for atomic file edits
BACKUP_DIR = Path(_env("AGENT_BACKUP_DIR", "/var/backups/bots-dashboard-agent"))
BACKUP_KEEP = _env_int("AGENT_BACKUP_KEEP", 20)

# Logging
LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()


def validate() -> list[str]:
    errors: list[str] = []
    if not AGENT_TOKEN:
        errors.append("AGENT_TOKEN is empty — central app cannot authenticate")
    if not MANIFEST_PATH.exists():
        errors.append(f"MANIFEST not found: {MANIFEST_PATH}")
    return errors


def snapshot() -> dict[str, object]:
    def _r(v: str) -> str:
        if not v:
            return ""
        return f"{v[:4]}...{v[-2:]}" if len(v) > 8 else "***"

    return {
        "agent_id": AGENT_ID,
        "version": VERSION,
        "build_sha": BUILD_SHA,
        "listen": f"{LISTEN_HOST}:{LISTEN_PORT}",
        "manifest": str(MANIFEST_PATH),
        "token": _r(AGENT_TOKEN),
        "backup_dir": str(BACKUP_DIR),
    }
