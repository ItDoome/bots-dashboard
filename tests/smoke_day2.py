from __future__ import annotations

# Day 2 smoke test — agent + central plugin layer.
#
# Spins up the AGENT in-process with a fake lolz-bot working directory (full
# of minimal JSON state files), then spins up the CENTRAL app and verifies:
#
#   - Agent: /health, /agent/capabilities, /adapters/lolz_bot/summary,
#     /adapters/lolz_bot/settings (GET + PUT), /adapters/lolz_bot/actions/*
#     (the real action path is mocked because we won't run sudo in CI)
#   - Central: /api/plugins, /api/plugins/lolz-bot/summary,
#     /api/dashboard/overview, PUT /api/plugins/lolz-bot/settings
#   - Audit rows written for every mutation
#
# All network calls from central → agent go through an in-process httpx
# MockTransport so no real sockets are opened.

import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

import asyncio
import hashlib
import hmac
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="dash_day2_"))
MOCK_BOT_TOKEN = "1234567890:AAEOabcdefghijklmnopqrstuvwxyz012345ABC"
MOCK_TG_ID = 742873645

# Fake /opt/tg_bot/ layout
_TG_BOT = _TMP / "tg_bot"
_TG_BOT.mkdir()
(_TG_BOT / "state.json").write_text(
    json.dumps({
        "autosell_enabled": True,
        "autosell_interval_minutes": 15,
        "last_checked_ts": 1775832016,
    }),
    encoding="utf-8",
)
(_TG_BOT / "watcher_config.json").write_text(
    json.dumps({
        "enabled": True,
        "enable_public_watcher": True,
        "autobuy_enabled": False,
        "autoreprice_enabled": False,
        "alerts_enabled": True,
        "autobuy_daily_budget": 5000,
        "working_limit_rpm": 120,
        "max_consecutive_403": 5,
    }),
    encoding="utf-8",
)
(_TG_BOT / "loliland_accounts.json").write_text(
    json.dumps({
        "accounts": [
            {"login": "ItDoome", "total_claimed": 688, "claim_count": 2},
            {"login": "JuniorGamerYT", "total_claimed": 98, "claim_count": 1},
        ],
    }),
    encoding="utf-8",
)
(_TG_BOT / "monopoly_snapshots.json").write_text(
    json.dumps({
        "snapshots": [
            {
                "collected_at": "2026-04-12T06:00:00+00:00",
                "my_mihoyo_active": 2141,
                "my_sold_24h": 27,
                "my_revenue_24h": 761.0,
                "my_sold_7d_avg": 15.3,
                "my_cheap_zone_share": 94.2,
                "mayo_cheap_count": 106,
            },
        ],
    }),
    encoding="utf-8",
)

# Agent manifest pointing at our fake /opt/tg_bot
(_TMP / "manifest.yaml").write_text(
    f"""
agent_id: server-a
adapters:
  - key: lolz_bot
    class: agent.adapters.lolz_bot.LolzBotAdapter
    working_dir: {_TG_BOT}
    systemd_unit: lolz-bot.service
    state_files:
      state_json: {_TG_BOT}/state.json
      watcher: {_TG_BOT}/watcher_config.json
      loliland: {_TG_BOT}/loliland_accounts.json
      monopoly: {_TG_BOT}/monopoly_snapshots.json
""",
    encoding="utf-8",
)

# Static inventory
(_TMP / "inventory.yaml").write_text(
    """
bots:
  - slug: lolz-bot
    display_name: LOLZ Valorant Resell
    icon: bot
    host: server-a
    adapter_key: lolz_bot
hosts:
  server-a:
    url: http://agent-local
""",
    encoding="utf-8",
)

# Agent env
os.environ["AGENT_ENV_FILE"] = "/nonexistent"
os.environ["AGENT_TOKEN"] = "agent-secret-token"
os.environ["AGENT_MANIFEST"] = str(_TMP / "manifest.yaml")
os.environ["AGENT_BACKUP_DIR"] = str(_TMP / "backups")
os.environ["COUNT_CACHE_TTL_SEC"] = "0"        # no caching in test

# Central env
os.environ["DASH_ENV_FILE"] = "/nonexistent"
os.environ["DASH_DATA_DIR"] = str(_TMP / "data")
(_TMP / "data").mkdir()
os.environ["DASH_CONFIG_DIR"] = str(_TMP)
os.environ["TG_BOT_TOKEN"] = MOCK_BOT_TOKEN
os.environ["ALLOWED_TG_IDS"] = str(MOCK_TG_ID)
os.environ["PUBLIC_ORIGIN"] = "http://testserver"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["OVERVIEW_CACHE_TTL_SEC"] = "0"
os.environ["AGENT_SERVER_A_URL"] = "http://agent-local"
os.environ["AGENT_SERVER_A_TOKEN"] = "agent-secret-token"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Monkey-patch systemctl helpers BEFORE agent modules import, so adapters
# that call systemd.service_state() get a deterministic fake.
from agent import systemd as _systemd  # noqa: E402
from shared.models import ServiceState  # noqa: E402


async def _fake_service_state(unit: str, *, timeout: float = 5.0) -> ServiceState:
    return ServiceState.active


async def _fake_service_restart(unit, *, timeout=None):
    return _systemd.CommandResult(rc=0, stdout=f"restarted {unit}", stderr="")


async def _fake_service_start(unit, *, timeout=None):
    return _systemd.CommandResult(rc=0, stdout=f"started {unit}", stderr="")


async def _fake_service_stop(unit, *, timeout=None):
    return _systemd.CommandResult(rc=0, stdout=f"stopped {unit}", stderr="")


async def _fake_journal_tail(unit, *, lines=200, since_sec=0, timeout=10.0):
    from shared.models import LogEntry, LogLevel
    return [
        LogEntry(
            ts="2026-04-12T01:00:00+0000",
            level=LogLevel.info,
            message=f"[fake] recent log for {unit}",
            source="journald",
        )
    ]


_systemd.service_state = _fake_service_state
_systemd.service_restart = _fake_service_restart
_systemd.service_start = _fake_service_start
_systemd.service_stop = _fake_service_stop
_systemd.journal_tail = _fake_journal_tail


# Now import and spin up the agent in-process using TestClient
from fastapi.testclient import TestClient  # noqa: E402

from agent.main import app as agent_app  # noqa: E402

# Monkey-patch httpx.AsyncClient to route agent-local → the TestClient transport
import httpx  # noqa: E402

# NOTE: TestClient's lifespan (startup/shutdown) only runs inside __enter__/__exit__.
# Without this the agent manifest is never loaded and adapters stay empty.
_agent_tc = TestClient(agent_app)
_agent_tc.__enter__()


class _TransportFromTestClient(httpx.AsyncBaseTransport):
    """Bridge httpx.AsyncClient requests into an in-process TestClient."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Strip base url. TestClient expects a plain path.
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query.decode('utf-8')}"
        method = request.method
        headers = dict(request.headers)
        body = request.content
        # Emulate via sync TestClient wrapped through to_thread
        def _do():
            return _agent_tc.request(method, path, headers=headers, content=body)
        resp = await asyncio.to_thread(_do)
        return httpx.Response(
            status_code=resp.status_code,
            headers=list(resp.headers.items()),
            content=resp.content,
            request=request,
        )


_original_init = httpx.AsyncClient.__init__


def _patched_init(self, *args, **kwargs):
    base_url = kwargs.get("base_url") or ""
    if str(base_url) == "http://agent-local":
        kwargs["transport"] = _TransportFromTestClient()
    _original_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_init  # type: ignore[method-assign]


# Bring up central
from app.main import app as central_app  # noqa: E402
from app import config as central_config  # noqa: E402

# Override inventory path to our temp file. Must be done BEFORE lifespan runs.
central_config.INVENTORY_PATH = _TMP / "inventory.yaml"

central_tc = TestClient(central_app, follow_redirects=False)
central_tc.__enter__()


def build_tg_payload(tg_id: int, auth_date: int | None = None, bot_token: str | None = None) -> dict:
    if auth_date is None:
        auth_date = int(time.time())
    if bot_token is None:
        bot_token = MOCK_BOT_TOKEN
    data = {
        "id": str(tg_id),
        "first_name": "Test",
        "username": "testuser",
        "auth_date": str(auth_date),
    }
    data_check = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    data["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return data


CSRF = {"X-Dashboard-Request": "1", "Origin": "http://testserver"}


_FAILED = 0


def ok(label: str, cond: bool, details: str = ""):
    global _FAILED
    mark = "PASS" if cond else "FAIL"
    line = f"  [{mark}] {label}"
    if details:
        line += f" -- {details}"
    print(line)
    if not cond:
        _FAILED += 1


def _login() -> dict[str, str]:
    good = build_tg_payload(MOCK_TG_ID)
    r = central_tc.get("/api/auth/telegram", params=good)
    assert r.status_code == 302, r.text
    cookie = r.cookies.get(central_config.SESSION_COOKIE_NAME)
    assert cookie
    return {"Cookie": f"{central_config.SESSION_COOKIE_NAME}={cookie}"}


def main() -> int:
    print(f"Temp: {_TMP}")

    print("\n=== agent direct ===")
    r = _agent_tc.get("/health")
    ok("agent /health -> 200", r.status_code == 200,
       details=f"body={r.json()}")

    r = _agent_tc.get(
        "/agent/capabilities",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent /agent/capabilities -> 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        ok("agent has lolz_bot adapter",
           any(a["key"] == "lolz_bot" for a in body.get("adapters", [])))

    r = _agent_tc.get(
        "/adapters/lolz_bot/summary",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent /adapters/lolz_bot/summary -> 200", r.status_code == 200,
       details=f"got {r.status_code}")
    if r.status_code == 200:
        s = r.json()
        ok("summary status=active", s.get("status") == "active")
        ok("summary health=ok", s.get("health") == "ok")
        ok("primary metrics present", len(s.get("primary_metrics") or []) >= 2)

    # Missing bearer -> 401
    r = _agent_tc.get("/adapters/lolz_bot/summary")
    ok("agent summary without bearer -> 401", r.status_code == 401)

    # GET settings
    r = _agent_tc.get(
        "/adapters/lolz_bot/settings",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent settings GET -> 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        vals = body.get("values", {}).get("values", {})
        ok("settings reflect state.json",
           vals.get("state.autosell_enabled") is True,
           details=f"autosell_enabled={vals.get('state.autosell_enabled')}")

    # PUT settings — flip autosell off via agent direct
    r = _agent_tc.put(
        "/adapters/lolz_bot/settings",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={"state.autosell_enabled": False},
    )
    ok("agent settings PUT -> 200", r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")
    state_after = json.loads((_TG_BOT / "state.json").read_text(encoding="utf-8"))
    ok("state.json autosell_enabled now False",
       state_after.get("autosell_enabled") is False)
    # Put it back for the central-side test below
    r = _agent_tc.put(
        "/adapters/lolz_bot/settings",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={"state.autosell_enabled": True},
    )

    # Non-whitelisted key should 400
    r = _agent_tc.put(
        "/adapters/lolz_bot/settings",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={"state.danger": "x"},
    )
    ok("agent settings PUT with non-whitelist key -> 400",
       r.status_code == 400)

    # Action: restart_service (mocked systemctl)
    r = _agent_tc.post(
        "/adapters/lolz_bot/actions/restart_service",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={},
    )
    ok("agent action restart_service -> 200",
       r.status_code == 200 and r.json().get("ok") is True,
       details=f"got {r.status_code}: {r.text[:200]}")

    # Unknown action -> 200 with ok=false
    r = _agent_tc.post(
        "/adapters/lolz_bot/actions/bogus",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={},
    )
    ok("agent unknown action -> ok=false",
       r.status_code == 200 and r.json().get("ok") is False)

    print("\n=== central + agent end-to-end ===")
    auth = _login()

    r = central_tc.get("/api/plugins", headers=auth)
    ok("central /api/plugins -> 200", r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        body = r.json()
        plugins = body.get("plugins") or []
        slugs = [p["slug"] for p in plugins]
        ok("central sees lolz-bot", "lolz-bot" in slugs,
           details=f"slugs={slugs}")
        lolz_card = next((p for p in plugins if p["slug"] == "lolz-bot"), {})
        ok("lolz-bot marked available", lolz_card.get("available") is True,
           details=f"last_error={lolz_card.get('last_error')}")

    r = central_tc.get("/api/plugins/lolz-bot/summary", headers=auth)
    ok("central /api/plugins/lolz-bot/summary -> 200",
       r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")

    r = central_tc.get("/api/dashboard/overview", headers=auth)
    ok("central /api/dashboard/overview -> 200",
       r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        body = r.json()
        totals = body.get("totals") or {}
        ok("overview totals.total_bots == 1",
           totals.get("total_bots") == 1,
           details=f"totals={totals}")
        ok("overview has lolz-bot card available",
           any(c["slug"] == "lolz-bot" and c.get("available") for c in body.get("bots") or []))

    r = central_tc.get("/api/plugins/lolz-bot/settings", headers=auth)
    ok("central /api/plugins/lolz-bot/settings -> 200",
       r.status_code == 200,
       details=f"got {r.status_code}")

    # Mutation through central — must require CSRF header
    r = central_tc.put(
        "/api/plugins/lolz-bot/settings",
        headers=auth,
        json={"state.autosell_interval_minutes": 30},
    )
    ok("central settings PUT without CSRF header -> 403",
       r.status_code == 403,
       details=f"got {r.status_code}")

    r = central_tc.put(
        "/api/plugins/lolz-bot/settings",
        headers={**auth, **CSRF, "Content-Type": "application/json"},
        json={"state.autosell_interval_minutes": 30},
    )
    ok("central settings PUT with CSRF -> 200",
       r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")
    state_after = json.loads((_TG_BOT / "state.json").read_text(encoding="utf-8"))
    ok("state.json autosell_interval_minutes == 30",
       state_after.get("autosell_interval_minutes") == 30)

    # Action via central — should be audited
    r = central_tc.post(
        "/api/plugins/lolz-bot/actions/restart_service",
        headers={**auth, **CSRF, "Content-Type": "application/json"},
        json={},
    )
    ok("central action restart_service -> 200",
       r.status_code == 200 and r.json().get("ok") is True,
       details=f"got {r.status_code}: {r.text[:200]}")

    # Audit log should have entries
    r = central_tc.get("/api/audit?page=1&page_size=50", headers=auth)
    ok("central /api/audit -> 200", r.status_code == 200)
    if r.status_code == 200:
        entries = r.json().get("entries") or []
        actions_seen = {e["action"] for e in entries}
        ok("audit has login", "login" in actions_seen)
        ok("audit has update_settings", "update_settings" in actions_seen)
        ok("audit has restart_service", "restart_service" in actions_seen)

    print(f"\n=== done ({_FAILED} failures) ===")
    # Cleanup
    try:
        central_tc.__exit__(None, None, None)
    except Exception:
        pass
    try:
        _agent_tc.__exit__(None, None, None)
    except Exception:
        pass
    shutil.rmtree(_TMP, ignore_errors=True)
    return 0 if _FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
