from __future__ import annotations

# Day 4 smoke test — loliland + rebot adapters end-to-end.
#
# Verifies:
#   - Agent loads all three adapters (lolz_bot + loliland + rebot) from a
#     synthetic manifest pointing at temp directories
#   - loliland adapter reads loliland_accounts.json and reports per-account
#     aggregates + host service state
#   - loliland.claim_all_now action runs the lolz-bot CLI via a mocked
#     asyncio.create_subprocess_exec that returns deterministic JSON
#   - rebot adapter reads a real SQLite database with the expected tables
#     and produces non-null counts
#   - rebot.restart_bot / restart_crawler actions go through the mocked
#     systemctl stack
#   - Central app /api/plugins exposes all three plugins with capabilities
#     including full ActionDescriptor lists (Day 4 models change)
#   - Central /api/dashboard/overview fans out to all three without one
#     slow/erroring adapter blocking the others
#
# Everything runs in-process with httpx.MockTransport.

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
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="dash_day4_"))
MOCK_BOT_TOKEN = "1234567890:AAEOabcdefghijklmnopqrstuvwxyz012345ABC"
MOCK_TG_ID = 742873645

# ──────────────────────────────────────────────────────────────────────
# Fake /opt/tg_bot/ layout (server-a)
# ──────────────────────────────────────────────────────────────────────

_TG_BOT = _TMP / "tg_bot"
_TG_BOT.mkdir()
(_TG_BOT / "state.json").write_text(
    json.dumps({
        "autosell_enabled": True,
        "autosell_interval_minutes": 15,
    }),
    encoding="utf-8",
)
(_TG_BOT / "watcher_config.json").write_text(
    json.dumps({"enabled": True, "autobuy_enabled": False}),
    encoding="utf-8",
)
(_TG_BOT / "loliland_accounts.json").write_text(
    json.dumps({
        "accounts": [
            {
                "login": "ItDoome",
                "total_claimed": 688,
                "claim_count": 2,
                "password": "sekret",
                "last_claim_at": "2026-04-11T21:00:00+00:00",
            },
            {
                "login": "JuniorGamerYT",
                "total_claimed": 98,
                "claim_count": 1,
                "password": "sekret2",
                "last_claim_at": "2026-04-10T09:30:00+00:00",
                "last_error": "token refresh failed",
            },
        ],
    }),
    encoding="utf-8",
)
(_TG_BOT / "monopoly_snapshots.json").write_text(
    json.dumps({"snapshots": [{
        "collected_at": "2026-04-12T06:00:00+00:00",
        "my_mihoyo_active": 2141,
        "my_sold_24h": 27,
        "my_cheap_zone_share": 94.2,
    }]}),
    encoding="utf-8",
)
# A fake venv python so the loliland adapter's argv isn't empty
_FAKE_VENV_BIN = _TMP / "fake_venv_bin"
_FAKE_VENV_BIN.mkdir()
_FAKE_PY = _FAKE_VENV_BIN / "python"
_FAKE_PY.write_text("# stub, subprocess is mocked\n", encoding="utf-8")

# ──────────────────────────────────────────────────────────────────────
# Fake /opt/rebot/current/ layout (server-b) — real SQLite DB
# ──────────────────────────────────────────────────────────────────────

_REBOT_DIR = _TMP / "rebot_current"
_REBOT_DIR.mkdir()
_REBOT_DB = _REBOT_DIR / "bot.sqlite3"
_conn = sqlite3.connect(_REBOT_DB)
_conn.executescript(
    """
    CREATE TABLE linked_profiles (
        id INTEGER PRIMARY KEY,
        tg_id INTEGER,
        remanga_id INTEGER,
        linked_at INTEGER
    );
    CREATE TABLE tg_user_settings (
        tg_id INTEGER PRIMARY KEY,
        locale TEXT,
        notifications_enabled INTEGER
    );
    CREATE TABLE bank_cards (
        id INTEGER PRIMARY KEY,
        tg_id INTEGER,
        card_code TEXT,
        created_at INTEGER
    );
    CREATE TABLE bank_deposit_requests (
        id INTEGER PRIMARY KEY,
        tg_id INTEGER,
        amount INTEGER,
        status TEXT,
        created_at INTEGER
    );
    CREATE TABLE new_card_subscriptions (
        id INTEGER PRIMARY KEY,
        tg_id INTEGER,
        enabled INTEGER,
        created_at INTEGER
    );
    CREATE TABLE new_card_deliveries (
        id INTEGER PRIMARY KEY,
        tg_id INTEGER,
        card_id INTEGER,
        created_at INTEGER
    );
    CREATE TABLE user_event_logs (
        id INTEGER PRIMARY KEY,
        tg_id INTEGER,
        event TEXT,
        created_at INTEGER
    );
    """
)
_now = int(time.time())
_conn.executemany(
    "INSERT INTO linked_profiles (tg_id, remanga_id, linked_at) VALUES (?, ?, ?);",
    [(1001, 9001, _now - 86400), (1002, 9002, _now - 3600), (1003, 9003, _now - 60)],
)
_conn.executemany(
    "INSERT INTO tg_user_settings (tg_id, locale, notifications_enabled) VALUES (?, ?, ?);",
    [(1001, "ru", 1), (1002, "en", 1), (1003, "ru", 0), (1004, "ru", 1)],
)
_conn.executemany(
    "INSERT INTO bank_cards (tg_id, card_code, created_at) VALUES (?, ?, ?);",
    [(1001, "A-01", _now), (1002, "A-02", _now)],
)
_conn.executemany(
    "INSERT INTO bank_deposit_requests (tg_id, amount, status, created_at) VALUES (?, ?, ?, ?);",
    [
        (1001, 500, "pending", _now - 600),
        (1002, 300, "completed", _now - 3600),
        (1003, 200, "pending", _now - 60),
    ],
)
_conn.executemany(
    "INSERT INTO new_card_subscriptions (tg_id, enabled, created_at) VALUES (?, ?, ?);",
    [(1001, 1, _now), (1002, 1, _now), (1003, 0, _now)],
)
_conn.executemany(
    "INSERT INTO new_card_deliveries (tg_id, card_id, created_at) VALUES (?, ?, ?);",
    [
        (1001, 1, _now - 100),       # last 24h
        (1001, 2, _now - 3600),      # last 24h
        (1002, 3, _now - 86400 * 3), # older than 24h
    ],
)
_conn.executemany(
    "INSERT INTO user_event_logs (tg_id, event, created_at) VALUES (?, ?, ?);",
    [
        (1001, "login", _now - 60),
        (1001, "card_open", _now - 120),
        (1002, "login", _now - 3600 * 2),
        (1003, "login", _now - 86400 * 2),   # too old
    ],
)
_conn.commit()
_conn.close()

# ──────────────────────────────────────────────────────────────────────
# Agent manifest — all three adapters (lolz_bot + loliland on server-a-ish
# + rebot in the SAME agent for test purposes; in prod they live on
# different hosts).
# ──────────────────────────────────────────────────────────────────────

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

  - key: loliland
    class: agent.adapters.loliland.LolilandAdapter
    working_dir: {_TG_BOT}
    accounts_file: {_TG_BOT}/loliland_accounts.json
    venv_python: {_FAKE_PY}
    cli_module: watcher_system.loliland_cli
    host_systemd_unit: lolz-bot.service

  - key: rebot
    class: agent.adapters.rebot.RebotAdapter
    working_dir: {_REBOT_DIR}
    db_path: {_REBOT_DB}
    bot_unit: rebot-bot.service
    crawler_unit: rebot-crawler.service
""",
    encoding="utf-8",
)

(_TMP / "inventory.yaml").write_text(
    """
bots:
  - slug: lolz-bot
    display_name: LOLZ Valorant Resell
    icon: bot
    host: server-a
    adapter_key: lolz_bot
  - slug: loliland
    display_name: Loliland Bonus Claimer
    icon: coins
    host: server-a
    adapter_key: loliland
  - slug: rebot
    display_name: reBot ReManga
    icon: gamepad-2
    host: server-a
    adapter_key: rebot
hosts:
  server-a:
    url: http://agent-local
""",
    encoding="utf-8",
)

# ──────────────────────────────────────────────────────────────────────
# Environment — agent + central
# ──────────────────────────────────────────────────────────────────────

os.environ["AGENT_ENV_FILE"] = "/nonexistent"
os.environ["AGENT_TOKEN"] = "agent-secret-token"
os.environ["AGENT_MANIFEST"] = str(_TMP / "manifest.yaml")
os.environ["AGENT_BACKUP_DIR"] = str(_TMP / "backups")
os.environ["COUNT_CACHE_TTL_SEC"] = "0"

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

# Mock systemctl/journalctl BEFORE adapter imports
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


# Mock asyncio.create_subprocess_exec used by loliland claim_all_now
import agent.adapters.loliland as _loliland_mod  # noqa: E402


class _FakeProc:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self._out = stdout
        self._err = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._out, self._err

    def kill(self):
        pass


async def _fake_create_subprocess_exec(*argv, **kwargs):
    # Pretend the loliland CLI ran and claimed 2/2 accounts, +150 coins.
    payload = json.dumps({
        "ok": True,
        "claimed": 2,
        "total": 2,
        "errors": 0,
        "amount": 150,
    })
    return _FakeProc(stdout=payload.encode("utf-8"))


# Patch in the loliland adapter module's namespace.
_original_cse = asyncio.create_subprocess_exec
asyncio.create_subprocess_exec = _fake_create_subprocess_exec  # type: ignore[assignment]


from fastapi.testclient import TestClient  # noqa: E402

from agent.main import app as agent_app  # noqa: E402

import httpx  # noqa: E402

_agent_tc = TestClient(agent_app)
_agent_tc.__enter__()


class _TransportFromTestClient(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query.decode('utf-8')}"
        method = request.method
        headers = dict(request.headers)
        body = request.content

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


from app.main import app as central_app  # noqa: E402
from app import config as central_config  # noqa: E402

central_config.INVENTORY_PATH = _TMP / "inventory.yaml"

central_tc = TestClient(central_app, follow_redirects=False)
central_tc.__enter__()


def build_tg_payload(tg_id: int) -> dict:
    auth_date = int(time.time())
    data = {
        "id": str(tg_id),
        "first_name": "Test",
        "username": "testuser",
        "auth_date": str(auth_date),
    }
    data_check = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(MOCK_BOT_TOKEN.encode()).digest()
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

    print("\n=== agent direct: capabilities ===")
    r = _agent_tc.get(
        "/agent/capabilities",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent /agent/capabilities -> 200", r.status_code == 200)
    caps_body = r.json() if r.status_code == 200 else {}
    adapter_keys = {a["key"] for a in caps_body.get("adapters", [])}
    ok("agent has lolz_bot adapter", "lolz_bot" in adapter_keys)
    ok("agent has loliland adapter", "loliland" in adapter_keys)
    ok("agent has rebot adapter", "rebot" in adapter_keys)

    # Capabilities must include full ActionDescriptor list now
    for a in caps_body.get("adapters", []):
        if a["key"] == "loliland":
            ok("loliland capabilities has actions list",
               len(a.get("actions") or []) >= 1,
               details=f"keys={a.get('action_keys')}")
            claim_desc = next(
                (x for x in a.get("actions") or [] if x["key"] == "claim_all_now"),
                None,
            )
            ok("loliland has claim_all_now descriptor", claim_desc is not None)
            if claim_desc:
                ok("claim_all_now has a label", bool(claim_desc.get("label")))
        if a["key"] == "rebot":
            descs = a.get("actions") or []
            keys = {d["key"] for d in descs}
            ok("rebot has restart_bot + restart_crawler",
               {"restart_bot", "restart_crawler"}.issubset(keys),
               details=f"keys={sorted(keys)}")

    print("\n=== loliland adapter ===")
    r = _agent_tc.get(
        "/adapters/loliland/summary",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent /adapters/loliland/summary -> 200", r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        s = r.json()
        ok("loliland summary status=active", s.get("status") == "active")
        primary = s.get("primary_metrics") or []
        labels = {m["label"] for m in primary}
        ok("loliland primary metrics include Аккаунтов / coins",
           "Аккаунтов" in labels and "Всего coins" in labels,
           details=f"labels={labels}")
        # 688 + 98 = 786
        coins_metric = next(
            (m for m in primary if m["label"] == "Всего coins"), None,
        )
        ok("loliland total coins = 786",
           coins_metric and coins_metric.get("value") == 786,
           details=f"got {coins_metric}")
        # 2 + 1 = 3 claims
        claims_metric = next(
            (m for m in primary if m["label"] == "Клеймов"), None,
        )
        ok("loliland total claims = 3",
           claims_metric and claims_metric.get("value") == 3)
        # One account has last_error → health should be warning (host service active)
        ok("loliland health=warning (1 account has error)",
           s.get("health") == "warning",
           details=f"got {s.get('health')}")

    # Action via agent
    r = _agent_tc.post(
        "/adapters/loliland/actions/claim_all_now",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={},
    )
    ok("agent loliland claim_all_now -> 200",
       r.status_code == 200 and r.json().get("ok") is True,
       details=f"got {r.status_code}: {r.text[:300]}")
    if r.status_code == 200:
        body = r.json()
        ok("claim_all_now message mentions 2/2",
           "2/2" in (body.get("message") or ""),
           details=f"msg={body.get('message')}")
        # Output is the raw CLI JSON
        ok("claim_all_now output parses as JSON",
           bool(body.get("output")) and "claimed" in (body.get("output") or ""))

    # Unknown action -> ok=false
    r = _agent_tc.post(
        "/adapters/loliland/actions/bogus",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={},
    )
    ok("loliland unknown action -> ok=false",
       r.status_code == 200 and r.json().get("ok") is False)

    print("\n=== rebot adapter ===")
    r = _agent_tc.get(
        "/adapters/rebot/summary",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent /adapters/rebot/summary -> 200", r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:300]}")
    if r.status_code == 200:
        s = r.json()
        ok("rebot summary status=active", s.get("status") == "active")
        ok("rebot summary health=ok", s.get("health") == "ok",
           details=f"got {s.get('health')}")
        primary = s.get("primary_metrics") or []
        labels = {m["label"] for m in primary}
        ok("rebot primary has user/profile/card metrics",
           "Пользователей" in labels
           and "Привязанных ReManga" in labels
           and "Подписок на карты" in labels)

        users_metric = next(
            (m for m in primary if m["label"] == "Пользователей"), None,
        )
        ok("rebot user count = 4",
           users_metric and users_metric.get("value") == 4,
           details=f"got {users_metric}")
        profiles_metric = next(
            (m for m in primary if m["label"] == "Привязанных ReManga"), None,
        )
        ok("rebot linked_profiles count = 3",
           profiles_metric and profiles_metric.get("value") == 3)
        subs_metric = next(
            (m for m in primary if m["label"] == "Подписок на карты"), None,
        )
        ok("rebot active subs count = 2 (enabled=1)",
           subs_metric and subs_metric.get("value") == 2,
           details=f"got {subs_metric}")

        secondary = s.get("secondary_metrics") or []
        sec_labels = {m["label"]: m["value"] for m in secondary}
        ok("rebot deliveries_24h = 2",
           sec_labels.get("Доставок 24ч") == 2,
           details=f"got {sec_labels.get('Доставок 24ч')}")
        ok("rebot events_24h = 3",
           sec_labels.get("События 24ч") == 3,
           details=f"got {sec_labels.get('События 24ч')}")
        ok("rebot deposit_pending = 2",
           sec_labels.get("Депозиты в ожидании") == 2,
           details=f"got {sec_labels.get('Депозиты в ожидании')}")

    # Actions via agent — restart_bot, restart_crawler
    r = _agent_tc.post(
        "/adapters/rebot/actions/restart_bot",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={},
    )
    ok("agent rebot restart_bot -> ok=true",
       r.status_code == 200 and r.json().get("ok") is True,
       details=f"got {r.status_code}: {r.text[:200]}")

    r = _agent_tc.post(
        "/adapters/rebot/actions/restart_crawler",
        headers={"Authorization": "Bearer agent-secret-token"},
        json={},
    )
    ok("agent rebot restart_crawler -> ok=true",
       r.status_code == 200 and r.json().get("ok") is True)

    # Logs — should merge bot + crawler
    r = _agent_tc.get(
        "/adapters/rebot/logs?limit=100",
        headers={"Authorization": "Bearer agent-secret-token"},
    )
    ok("agent rebot logs -> 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        entries = body.get("entries") or []
        sources = {e.get("source") for e in entries}
        ok("rebot logs include bot + crawler sources",
           "rebot-bot" in sources and "rebot-crawler" in sources,
           details=f"sources={sources}")

    print("\n=== central end-to-end ===")
    auth = _login()

    r = central_tc.get("/api/plugins", headers=auth)
    ok("central /api/plugins -> 200", r.status_code == 200)
    plugins = []
    if r.status_code == 200:
        plugins = r.json().get("plugins") or []
        slugs = {p["slug"] for p in plugins}
        ok("central sees all 3 plugins",
           {"lolz-bot", "loliland", "rebot"}.issubset(slugs),
           details=f"slugs={sorted(slugs)}")
        for p in plugins:
            ok(f"plugin {p['slug']} is available",
               p.get("available") is True,
               details=f"last_error={p.get('last_error')}")
            caps = p.get("capabilities") or {}
            if p["slug"] in ("loliland", "rebot"):
                ok(f"plugin {p['slug']} capabilities has full actions list",
                   len(caps.get("actions") or []) >= 1,
                   details=f"keys={caps.get('action_keys')}")

    r = central_tc.get("/api/plugins/loliland/summary", headers=auth)
    ok("central /api/plugins/loliland/summary -> 200",
       r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")

    r = central_tc.get("/api/plugins/rebot/summary", headers=auth)
    ok("central /api/plugins/rebot/summary -> 200",
       r.status_code == 200,
       details=f"got {r.status_code}: {r.text[:200]}")

    r = central_tc.get("/api/dashboard/overview", headers=auth)
    ok("central /api/dashboard/overview -> 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        totals = body.get("totals") or {}
        ok("overview totals.total_bots == 3",
           totals.get("total_bots") == 3,
           details=f"totals={totals}")
        cards = body.get("bots") or []
        avail = {c["slug"]: c.get("available") for c in cards}
        ok("all 3 cards available on overview",
           avail.get("lolz-bot") and avail.get("loliland") and avail.get("rebot"),
           details=f"avail={avail}")

    # Action via central — loliland claim_all_now should be audited
    r = central_tc.post(
        "/api/plugins/loliland/actions/claim_all_now",
        headers={**auth, **CSRF, "Content-Type": "application/json"},
        json={},
    )
    ok("central loliland claim_all_now -> 200",
       r.status_code == 200 and r.json().get("ok") is True,
       details=f"got {r.status_code}: {r.text[:300]}")

    r = central_tc.post(
        "/api/plugins/rebot/actions/restart_crawler",
        headers={**auth, **CSRF, "Content-Type": "application/json"},
        json={},
    )
    ok("central rebot restart_crawler -> 200",
       r.status_code == 200 and r.json().get("ok") is True)

    # rebot settings should return 405 (no supports_settings)
    r = central_tc.put(
        "/api/plugins/rebot/settings",
        headers={**auth, **CSRF, "Content-Type": "application/json"},
        json={"anything": 1},
    )
    ok("central rebot settings PUT -> 405 (not supported)",
       r.status_code == 405,
       details=f"got {r.status_code}: {r.text[:200]}")

    # loliland settings GET should return empty schema
    r = central_tc.get("/api/plugins/loliland/settings", headers=auth)
    ok("central loliland settings GET -> 200", r.status_code == 200)
    if r.status_code == 200:
        body = r.json()
        sections = body.get("schema", {}).get("sections") or []
        ok("loliland has no editable sections", len(sections) == 0,
           details=f"sections={sections}")

    # Audit log should have entries for everything we did
    r = central_tc.get("/api/audit?page=1&page_size=50", headers=auth)
    ok("central /api/audit -> 200", r.status_code == 200)
    if r.status_code == 200:
        entries = r.json().get("entries") or []
        actions_seen = {(e.get("plugin_slug"), e.get("action")) for e in entries}
        ok("audit has loliland claim_all_now",
           ("loliland", "claim_all_now") in actions_seen,
           details=f"actions={actions_seen}")
        ok("audit has rebot restart_crawler",
           ("rebot", "restart_crawler") in actions_seen)

    print(f"\n=== done ({_FAILED} failures) ===")

    try:
        central_tc.__exit__(None, None, None)
    except Exception:
        pass
    try:
        _agent_tc.__exit__(None, None, None)
    except Exception:
        pass
    asyncio.create_subprocess_exec = _original_cse  # type: ignore[assignment]
    shutil.rmtree(_TMP, ignore_errors=True)
    return 0 if _FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
