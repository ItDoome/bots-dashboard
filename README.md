# bots-dashboard — doomedash.com

Central web panel for managing the user's Telegram bot fleet.
Hosted at [doomedash.com](https://doomedash.com) (server A).

## Topology

```
browser
  │  https://doomedash.com
  ▼
nginx on 144.31.136.67
  ├── / → /var/www/bots-dashboard/ (static SPA)
  └── /api/* → 127.0.0.1:8090 (uvicorn, single worker)
                    │
                    ├── 127.0.0.1:8765   → agent server-A (loopback)
                    └── 127.0.0.1:18765  → SSH tunnel → agent server-B:8765
```

Bots:
- **lolz-bot** (server A) — Valorant/miHoYo marketplace automation
- **loliland** (server A) — bonus claimer living inside lolz-bot's venv
- **rebot** (server B) — ReManga card gamification, read + restart only
- **manga editor** — planned

## Critical invariants

1. **Single-worker only.** Central and agent both run with `--workers 1`. The
   per-action `asyncio.Lock` and the in-memory overview cache assume one
   process. Scaling out silently breaks action mutex. The systemd units
   pin `--workers 1` and `WEB_CONCURRENCY=1`; startup logs a hard error
   otherwise.
2. **Central never touches files/systemd/DB directly.** All mutations go
   through an HTTP call to an agent, which does the actual work.
3. **Agents never run as root.** They call root-owned helper scripts
   (`/usr/local/bin/botsdash-systemctl`, `…-journalctl`) via sudo NOPASSWD.
   The helpers whitelist both the verb and the unit — no sudoers arg
   matching.
4. **Session cookie is hashed in the DB.** Name is `__Host-dash_session`
   (forces Secure + Path=/ + no Domain). Stored as `sha256(token)` so a
   DB leak doesn't yield session tokens.
5. **CSRF triple-check.** `SameSite=Lax` + `Origin` header check +
   `X-Dashboard-Request: 1` custom header. Mutating GETs are forbidden;
   the TG login callback is the only GET that has side-effects, and
   nginx has `access_log off` on it so query params don't hit disk.
6. **SSH tunnel uses `restrict,permitopen`**, never `command="/bin/false"`
   (which breaks port forwarding). Plus `nologin` shell. Plus pinned
   known_hosts. Plus ExitOnForwardFailure so a broken link doesn't
   silently turn into "agent offline".

## Layout

```
shared/models.py            — Pydantic DTOs shared by central + agent
app/                        — central FastAPI app (sessions, audit, plugins)
agent/                      — per-host agent (adapters + systemd helpers)
web/                        — React + Vite SPA
deploy/                     — systemd, nginx, sudoers, helper scripts, inventory
tests/smoke_day1.py         — auth + CSRF + audit (20 assertions)
tests/smoke_day2.py         — agent + central end-to-end for lolz-bot (27 assertions)
tests/smoke_day4.py         — loliland + rebot adapters (44 assertions)
```

## Build and deploy

### 1. Build the frontend locally (Windows dev machine)

```bash
cd web
npm ci
npm run build        # produces web/dist/
```

`web/dist/` is then rsync'd to server A as part of the repo upload.

### 2. Upload the repo to server A

```bash
# from Windows dev machine
rsync -avz --exclude .venv --exclude node_modules \
    ./bots-dashboard/ \
    root@144.31.136.67:/opt/bots-dashboard/
```

### 3. Server A: run the deploy scripts

```bash
ssh root@144.31.136.67

cd /opt/bots-dashboard
AGENT_ID=server-a bash deploy/deploy-agent.sh
bash deploy/deploy-central.sh

# Fill in secrets
editor /etc/bots-dashboard/env
editor /etc/bots-dashboard-agent/env

# Enable services
systemctl enable --now bots-dashboard-agent
systemctl enable --now bots-dashboard
systemctl enable --now bots-dashboard-tunnel

# Provision TLS
certbot --nginx -d doomedash.com -d www.doomedash.com
```

### 4. Server B: deploy the agent

```bash
rsync -avz --exclude .venv --exclude node_modules \
    ./bots-dashboard/ \
    root@144.31.136.4:/opt/bots-dashboard/

ssh root@144.31.136.4
cd /opt/bots-dashboard
AGENT_ID=server-b bash deploy/deploy-agent.sh

editor /etc/bots-dashboard-agent/env   # same AGENT_TOKEN as on central

# Paste the server-A tunnel pubkey as:
#   restrict,permitopen="127.0.0.1:8765" ssh-ed25519 AAAA...
# into /home/tunnel/.ssh/authorized_keys
editor /home/tunnel/.ssh/authorized_keys

systemctl enable --now bots-dashboard-agent
```

### 5. @BotFather domain binding

In Telegram DM with @BotFather:

```
/setdomain
→ @lolsZauto_bot
→ doomedash.com
```

This is what makes the TG Login Widget emit redirects to `/api/auth/telegram`
on our domain.

## QA checklist (end-to-end)

- [ ] Browser: `https://doomedash.com/` loads landing page
- [ ] Click "Sign in with Telegram" → modal → confirm in TG → `/dashboard`
- [ ] `/dashboard` shows 3 BotCards (lolz-bot, loliland, rebot)
- [ ] lolz-bot card metrics: miHoYo active, sales 24h, Loliland coins
- [ ] Open `/bots/lolz-bot` → Overview tab shows metrics grid
- [ ] Settings tab → flip `autosell_enabled` → Save → 200 → audit row
- [ ] Actions tab → "Restart lolz-bot" → confirm → 200 → audit row
- [ ] Click restart twice fast → second request gets 409 (mutex)
- [ ] Logs tab → journalctl entries stream in, polling when tab visible
- [ ] `/bots/loliland` → Actions → "Клеймить сейчас" → 200 (or fail with redacted error)
- [ ] `/bots/rebot` → Actions → "Перезапустить rebot-bot" → 200 → audit
- [ ] `/audit` → paginated table shows all actions with redacted params
- [ ] `curl https://doomedash.com/api/me` without cookie → 401
- [ ] `curl -X POST https://doomedash.com/api/plugins/lolz-bot/actions/restart_service`
      without `X-Dashboard-Request` header → 403
- [ ] `sudo -l -U botsagent` on server A → only the two helper scripts
- [ ] `lsof -i :8765` on server A and server B → only loopback
- [ ] `curl http://144.31.136.4:8765/health` from outside → connection refused
- [ ] Kill server-B agent → rebot card shows "offline" warning, others still work
- [ ] `journalctl -u nginx -S -1h | grep auth/telegram` → should be empty
      (access_log off on that location)
- [ ] Inspect audit rows → never contain raw tokens/passwords/cookies

## Rollback

```bash
systemctl disable --now bots-dashboard bots-dashboard-agent bots-dashboard-tunnel
rm /etc/nginx/sites-enabled/doomedash.com
nginx -s reload
```

The running bots (lolz-bot on A, rebot on B) are NOT touched by this.
Only change to their code is the optional `flock` wrapper in
`/opt/tg_bot/config.py save_state()` — one 5-line block that can be
reverted by a single commit.

## Smoke tests

Run from the top-level repo with the dashboard's own venv:

```bash
.venv/Scripts/python.exe tests/smoke_day1.py   # auth + CSRF + audit
.venv/Scripts/python.exe tests/smoke_day2.py   # lolz-bot end-to-end
.venv/Scripts/python.exe tests/smoke_day4.py   # loliland + rebot end-to-end
```

All three should exit with `0 failures`.
