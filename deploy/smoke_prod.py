"""End-to-end production smoke test run *on* server A.

Exercises the full central app via localhost:8090 using a real
HMAC-signed Telegram login payload. Verifies:
  - GET /api/auth/telegram -> 302 + session cookie
  - GET /api/me            -> 200 with correct tg_id
  - GET /api/plugins       -> all three bots available
  - GET /api/dashboard/overview
  - GET /api/plugins/lolz-bot/summary    (server A adapter)
  - GET /api/plugins/loliland/summary    (server A adapter)
  - GET /api/plugins/rebot/summary       (server B adapter through SSH tunnel)

Requires TELEGRAM_BOT_TOKEN + tg_id on the command line:
    python smoke_prod.py <bot_token> <tg_id>
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("DASH_BASE", "http://127.0.0.1:8090")


def build_tg_payload(tg_id: int, bot_token: str) -> dict:
    data = {
        "id": str(tg_id),
        "first_name": "ItDoome",
        "username": "ItDoome",
        "auth_date": str(int(time.time())),
    }
    data_check = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    data["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return data


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def http(method: str, path: str, cookie: str | None = None, headers: dict | None = None) -> tuple[int, dict, str]:
    h = {"User-Agent": UA, "Accept": "application/json, text/html", **dict(headers or {})}
    if cookie:
        h["Cookie"] = cookie
    req = urllib.request.Request(f"{BASE}{path}", method=method, headers=h)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as e:
        resp = e
    body = resp.read().decode("utf-8", errors="replace")
    return resp.status, dict(resp.headers), body


def http_login(tg_id: int, bot_token: str) -> str:
    payload = build_tg_payload(tg_id, bot_token)
    qs = urllib.parse.urlencode(payload)
    req = urllib.request.Request(
        f"{BASE}/api/auth/telegram?{qs}",
        method="GET",
        headers={"User-Agent": UA, "Accept": "text/html,*/*"},
    )
    # We don't follow the 302 — we want the cookie off the initial response
    class NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedir())
    try:
        resp = opener.open(req, timeout=15)
    except urllib.error.HTTPError as e:
        resp = e
    status = resp.status
    headers = resp.headers
    if status != 302:
        body = resp.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"/api/auth/telegram expected 302, got {status}: {body[:200]}")
    set_cookie = headers.get("Set-Cookie") or ""
    for piece in set_cookie.split(","):
        piece = piece.strip()
        if piece.startswith("__Host-dash_session="):
            return piece.split(";")[0]
    raise RuntimeError(f"no session cookie in response: {set_cookie[:300]}")


FAILED = 0


def ok(label: str, cond: bool, details: str = "") -> None:
    global FAILED
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {details}" if details else ""))
    if not cond:
        FAILED += 1


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: smoke_prod.py <bot_token> <tg_id>")
        return 2
    bot_token = sys.argv[1]
    tg_id = int(sys.argv[2])

    print(f"=== login ===")
    cookie = http_login(tg_id, bot_token)
    ok("login -> 302 with session cookie", cookie.startswith("__Host-dash_session="),
       details=f"cookie_prefix={cookie[:40]}...")

    print("\n=== /api/me ===")
    status, _h, body = http("GET", "/api/me", cookie=cookie)
    ok("/api/me -> 200", status == 200, details=f"body={body[:100]}")
    if status == 200:
        me = json.loads(body)
        ok("me.tg_id matches", me.get("tg_id") == tg_id,
           details=f"me.tg_id={me.get('tg_id')}")

    print("\n=== /api/plugins ===")
    status, _h, body = http("GET", "/api/plugins", cookie=cookie)
    ok("/api/plugins -> 200", status == 200)
    if status == 200:
        plugins = json.loads(body).get("plugins", [])
        slugs = {p["slug"] for p in plugins}
        ok("all 3 plugins listed",
           {"lolz-bot", "loliland", "rebot"}.issubset(slugs),
           details=f"slugs={sorted(slugs)}")
        for p in plugins:
            ok(f"  {p['slug']}.available",
               p.get("available") is True,
               details=f"last_error={p.get('last_error')}")

    print("\n=== /api/dashboard/overview ===")
    status, _h, body = http("GET", "/api/dashboard/overview", cookie=cookie)
    ok("/api/dashboard/overview -> 200", status == 200)
    if status == 200:
        doc = json.loads(body)
        totals = doc.get("totals") or {}
        ok("totals.total_bots == 3", totals.get("total_bots") == 3,
           details=f"totals={totals}")
        for bot in doc.get("bots") or []:
            slug = bot.get("slug")
            avail = bot.get("available")
            summary = bot.get("summary") or {}
            ok(f"  overview/{slug} available={avail}", avail is True)
            if summary:
                ok(f"    {slug}.status",
                   summary.get("status") in ("active", "inactive", "failed", "unknown", "activating", "deactivating"),
                   details=f"status={summary.get('status')} health={summary.get('health')}")

    print("\n=== per-bot summary ===")
    for slug in ("lolz-bot", "loliland", "rebot"):
        status, _h, body = http("GET", f"/api/plugins/{slug}/summary", cookie=cookie)
        ok(f"/api/plugins/{slug}/summary -> 200", status == 200,
           details=f"body={body[:200]}")

    print("\n=== settings ===")
    status, _h, body = http("GET", "/api/plugins/lolz-bot/settings", cookie=cookie)
    ok("/api/plugins/lolz-bot/settings -> 200", status == 200,
       details=f"body_len={len(body)}")
    if status == 200:
        doc = json.loads(body)
        sections = doc.get("schema", {}).get("sections", [])
        ok("lolz-bot has editable sections", len(sections) >= 1,
           details=f"count={len(sections)}")

    print(f"\n=== done ({FAILED} failures) ===")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
