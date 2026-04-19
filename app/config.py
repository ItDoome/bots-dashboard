"""Runtime configuration loaded from environment.

Reads from ``$DASH_ENV_FILE`` (default ``/etc/bots-dashboard/env``) plus the
process environment. Same pattern as the existing lolz-bot ``config.py`` —
parse once at module import, expose as module-level constants.

Secrets (TG bot token, agent bearer tokens, session signing key) live here and
should never be logged or exposed via any API route.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = Path(os.environ.get("DASH_ENV_FILE", "/etc/bots-dashboard/env"))


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=value .env file. Ignores comments and blank lines."""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # Strip matching quotes
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            result[key] = val
    except Exception as exc:
        logger.warning("failed to load env file %s: %r", path, exc)
    return result


def _env(key: str, default: str = "") -> str:
    """Lookup env var: file first, then process environment, then default."""
    if key in _env_file:
        return _env_file[key]
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("env %s=%r is not an int, using default %d", key, raw, default)
        return default


def _env_csv(key: str) -> list[str]:
    raw = _env(key)
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


_env_file = _load_env_file(DEFAULT_ENV_PATH)

# ──────────────────────────────────────────────────────────────────────
# Runtime identity & paths
# ──────────────────────────────────────────────────────────────────────

APP_NAME = "bots-dashboard"
VERSION = _env("DASH_VERSION", "0.1.0-dev")
BUILD_SHA = _env("DASH_BUILD_SHA", "dev")

# Persistent state directory. Must exist and be writable by the `botsdash` user.
DATA_DIR = Path(_env("DASH_DATA_DIR", "/var/lib/bots-dashboard"))
DB_PATH = DATA_DIR / "dashboard.sqlite3"
CAPABILITIES_CACHE_PATH = DATA_DIR / "capabilities_cache.json"

# Static config directory (read-only for the app).
CONFIG_DIR = Path(_env("DASH_CONFIG_DIR", "/etc/bots-dashboard"))
INVENTORY_PATH = CONFIG_DIR / "inventory.yaml"

# ──────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────

# Telegram bot whose login widget we verify. Same bot as @lolsZauto_bot in v1.
TELEGRAM_BOT_TOKEN: str = _env("TG_BOT_TOKEN", "")

# Comma-separated list of allowed Telegram user IDs. In v1 it's just the admin.
ALLOWED_TG_IDS: list[int] = []
for raw_id in _env_csv("ALLOWED_TG_IDS"):
    try:
        ALLOWED_TG_IDS.append(int(raw_id))
    except ValueError:
        logger.warning("invalid tg id in ALLOWED_TG_IDS: %r", raw_id)

# Session settings
SESSION_COOKIE_NAME = "__Host-dash_session"
SESSION_MAX_AGE_SEC = _env_int("SESSION_MAX_AGE_SEC", 7 * 24 * 3600)
TG_AUTH_MAX_AGE_SEC = _env_int("TG_AUTH_MAX_AGE_SEC", 15 * 60)

# Public origin — used for the Origin/Referer check on mutating requests.
PUBLIC_ORIGIN = _env("PUBLIC_ORIGIN", "https://doomedash.com")
CSRF_HEADER_NAME = "x-dashboard-request"
CSRF_HEADER_VALUE = "1"

# ──────────────────────────────────────────────────────────────────────
# HTTP server
# ──────────────────────────────────────────────────────────────────────

LISTEN_HOST = _env("DASH_HOST", "127.0.0.1")
LISTEN_PORT = _env_int("DASH_PORT", 8090)

# ──────────────────────────────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────────────────────────────

# Per-host bearer token. Each agent is configured with its own shared secret.
# Hostnames match the keys used in inventory.yaml.
AGENT_TOKENS: dict[str, str] = {}
AGENT_URLS: dict[str, str] = {}
for host_key in ("server-a", "server-b"):
    url_env = f"AGENT_{host_key.upper().replace('-', '_')}_URL"
    token_env = f"AGENT_{host_key.upper().replace('-', '_')}_TOKEN"
    url = _env(url_env)
    token = _env(token_env)
    if url:
        AGENT_URLS[host_key] = url
    if token:
        AGENT_TOKENS[host_key] = token

# ──────────────────────────────────────────────────────────────────────
# Timing knobs
# ──────────────────────────────────────────────────────────────────────

OVERVIEW_CACHE_TTL_SEC = _env_int("OVERVIEW_CACHE_TTL_SEC", 5)
AGENT_HTTP_TIMEOUT_SEC = _env_int("AGENT_HTTP_TIMEOUT_SEC", 30)
CAPABILITIES_CACHE_TTL_SEC = _env_int("CAPABILITIES_CACHE_TTL_SEC", 60)

# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────

LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()


def validate_critical_config() -> list[str]:
    """Returns list of errors. Empty list = config is usable."""
    errors: list[str] = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TG_BOT_TOKEN is missing — Telegram login will fail")
    if not ALLOWED_TG_IDS:
        errors.append("ALLOWED_TG_IDS is empty — no one can log in")
    if not AGENT_URLS:
        errors.append("no AGENT_*_URL configured — dashboard has nothing to talk to")
    if not DATA_DIR.exists():
        errors.append(f"DATA_DIR does not exist: {DATA_DIR}")
    return errors


def snapshot(redact_secrets: bool = True) -> dict[str, Any]:
    """Return a dict of config values, safe to log (secrets redacted)."""
    def _redact(v: str) -> str:
        if not v:
            return ""
        if len(v) <= 8:
            return "***"
        return f"{v[:4]}...{v[-2:]}"

    return {
        "app_name": APP_NAME,
        "version": VERSION,
        "build_sha": BUILD_SHA,
        "data_dir": str(DATA_DIR),
        "db_path": str(DB_PATH),
        "config_dir": str(CONFIG_DIR),
        "public_origin": PUBLIC_ORIGIN,
        "listen": f"{LISTEN_HOST}:{LISTEN_PORT}",
        "allowed_tg_ids": ALLOWED_TG_IDS,
        "tg_bot_token": _redact(TELEGRAM_BOT_TOKEN) if redact_secrets else TELEGRAM_BOT_TOKEN,
        "agent_urls": AGENT_URLS,
        "agent_tokens": {k: _redact(v) for k, v in AGENT_TOKENS.items()} if redact_secrets else AGENT_TOKENS,
        "session_max_age_sec": SESSION_MAX_AGE_SEC,
        "tg_auth_max_age_sec": TG_AUTH_MAX_AGE_SEC,
        "overview_cache_ttl_sec": OVERVIEW_CACHE_TTL_SEC,
    }
