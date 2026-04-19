from __future__ import annotations

# End-to-end smoke test for Day 1 auth layer.
# Spins up FastAPI against an isolated SQLite in a temp dir, feeds mock env,
# and exercises /health, /me, CSRF, Telegram login happy+failure paths, and
# the audit table.

import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

import hashlib
import hmac
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Isolate run: temp data dir + fake env BEFORE importing app
_TMP = Path(tempfile.mkdtemp(prefix="dash_smoke_"))
MOCK_BOT_TOKEN = "1234567890:AAEOabcdefghijklmnopqrstuvwxyz012345ABC"
MOCK_TG_ID = 742873645

os.environ["DASH_ENV_FILE"] = "/nonexistent"   # force env-only loading
os.environ["DASH_DATA_DIR"] = str(_TMP)
os.environ["DASH_CONFIG_DIR"] = str(_TMP)
os.environ["TG_BOT_TOKEN"] = MOCK_BOT_TOKEN
os.environ["ALLOWED_TG_IDS"] = str(MOCK_TG_ID)
os.environ["PUBLIC_ORIGIN"] = "http://testserver"
os.environ["LOG_LEVEL"] = "WARNING"

# Make project importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient   # noqa: E402

from app.main import app   # noqa: E402
from app import config   # noqa: E402


CSRF = {"X-Dashboard-Request": "1", "Origin": "http://testserver"}


def build_tg_payload(tg_id: int, auth_date: int | None = None, bot_token: str | None = None) -> dict:
    """Create a valid HMAC-signed Telegram Login Widget payload."""
    if auth_date is None:
        auth_date = int(time.time())
    if bot_token is None:
        bot_token = MOCK_BOT_TOKEN

    data = {
        "id": str(tg_id),
        "first_name": "Test",
        "username": "testuser",
        "photo_url": "https://example.org/x.jpg",
        "auth_date": str(auth_date),
    }
    data_check = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    data["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return data


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


def main() -> int:
    global _FAILED
    print(f"Temp data dir: {_TMP}")

    client = TestClient(app, follow_redirects=False)

    print("\n=== sanity ===")
    r = client.get("/api/health")
    ok("GET /api/health -> 200", r.status_code == 200 and r.json().get("ok") is True)

    r = client.get("/api/version")
    ok("GET /api/version -> 200", r.status_code == 200 and "version" in r.json())

    print("\n=== unauthenticated routes ===")
    r = client.get("/api/me")
    ok("GET /api/me (no cookie) -> 401", r.status_code == 401)

    r = client.post("/api/auth/logout", headers=CSRF)
    ok("POST /api/auth/logout (no cookie) -> 401", r.status_code == 401)

    print("\n=== CSRF defense ===")
    r = client.post("/api/auth/logout")
    ok("POST /api/auth/logout (no CSRF header) -> 403", r.status_code == 403,
       details=f"got {r.status_code}")

    r = client.post("/api/auth/logout", headers={"X-Dashboard-Request": "1"})
    ok("POST /api/auth/logout (no Origin) -> 403", r.status_code == 403,
       details=f"got {r.status_code}")

    print("\n=== Telegram auth -- invalid paths ===")
    payload = build_tg_payload(MOCK_TG_ID)
    bad = dict(payload)
    bad["hash"] = "0" * 64
    r = client.get("/api/auth/telegram", params=bad)
    ok("bad hash -> 400", r.status_code == 400)

    old = build_tg_payload(MOCK_TG_ID, auth_date=int(time.time()) - 3600)
    r = client.get("/api/auth/telegram", params=old)
    ok("expired auth_date -> 400", r.status_code == 400)

    wrong_id_payload = build_tg_payload(123456)
    r = client.get("/api/auth/telegram", params=wrong_id_payload)
    ok("not-in-allowlist -> 403", r.status_code == 403)

    print("\n=== Telegram auth -- happy path ===")
    good = build_tg_payload(MOCK_TG_ID)
    r = client.get("/api/auth/telegram", params=good)
    ok("valid payload -> 302", r.status_code == 302,
       details=f"location={r.headers.get('location')}")
    ok("redirect target is /dashboard", r.headers.get("location") == "/dashboard")

    cookie = r.cookies.get(config.SESSION_COOKIE_NAME)
    ok("session cookie set", bool(cookie))

    auth_headers = {"Cookie": f"{config.SESSION_COOKIE_NAME}={cookie}"}

    r = client.get("/api/me", headers=auth_headers)
    ok("GET /api/me (with cookie) -> 200", r.status_code == 200,
       details=f"got {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        ok("/api/me tg_id matches", body.get("tg_id") == MOCK_TG_ID)
        ok("/api/me username matches", body.get("username") == "testuser")

    print("\n=== logout ===")
    r = client.post("/api/auth/logout", headers={**CSRF, **auth_headers})
    ok("POST /api/auth/logout (authenticated) -> 200", r.status_code == 200,
       details=f"got {r.status_code}")

    r = client.get("/api/me", headers=auth_headers)
    ok("GET /api/me (after logout) -> 401", r.status_code == 401,
       details=f"got {r.status_code}")

    print("\n=== audit log ===")
    from app import audit
    entries = audit.list_entries(page=1, page_size=50).entries
    login_rows = [e for e in entries if e.action == "login"]
    logout_rows = [e for e in entries if e.action == "logout"]
    login_failed_rows = [e for e in entries if e.action == "login_failed"]
    login_rejected_rows = [e for e in entries if e.action == "login_rejected"]

    ok("audit has login row", len(login_rows) >= 1,
       details=f"{len(login_rows)} rows")
    ok("audit has logout row", len(logout_rows) >= 1,
       details=f"{len(logout_rows)} rows")
    ok("audit has login_failed rows", len(login_failed_rows) >= 2,
       details=f"{len(login_failed_rows)} rows (bad hash + expired)")
    ok("audit has login_rejected rows", len(login_rejected_rows) >= 1,
       details=f"{len(login_rejected_rows)} rows")

    print(f"\n=== done ({_FAILED} failures) ===")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 0 if _FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
