#!/usr/bin/env bash
# Deploy the bots-dashboard central app to server A (144.31.136.67).
#
# Assumes the repo is already rsync'd to /opt/bots-dashboard/ on the box
# and that this script is being run AS ROOT on server A.
#
# Safe to re-run — idempotent. Won't delete existing sessions or audit.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { echo "[deploy-central] $*"; }

# ─────────────────────────────────────────────────────────────
# Users and directories
# ─────────────────────────────────────────────────────────────

log "creating botsdash user (if missing)"
if ! id botsdash >/dev/null 2>&1; then
    useradd --system --shell /usr/sbin/nologin --home-dir /var/lib/bots-dashboard --create-home botsdash
fi

log "ensuring /var/lib/bots-dashboard and /etc/bots-dashboard exist"
install -d -o botsdash -g botsdash -m 0750 /var/lib/bots-dashboard
install -d -o root -g botsdash -m 0750 /etc/bots-dashboard

log "ensuring /var/log/bots-dashboard exists"
install -d -o botsdash -g botsdash -m 0755 /var/log/bots-dashboard

# ─────────────────────────────────────────────────────────────
# Python virtualenv
# ─────────────────────────────────────────────────────────────

if [[ ! -d "$REPO_ROOT/.venv" ]]; then
    log "creating venv at $REPO_ROOT/.venv"
    python3.12 -m venv "$REPO_ROOT/.venv"
fi

log "installing python dependencies"
"$REPO_ROOT/.venv/bin/pip" install --upgrade pip wheel
"$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/requirements.txt"

chown -R botsdash:botsdash "$REPO_ROOT/.venv"

# ─────────────────────────────────────────────────────────────
# Config files
# ─────────────────────────────────────────────────────────────

if [[ ! -f /etc/bots-dashboard/env ]]; then
    log "creating /etc/bots-dashboard/env template — FILL IN SECRETS"
    install -o root -g botsdash -m 0640 /dev/null /etc/bots-dashboard/env
    cat > /etc/bots-dashboard/env <<'EOF'
# Bot token for @lolsZauto_bot — copy from /opt/tg_bot/.env
TG_BOT_TOKEN=

# Who is allowed to log in (comma-separated Telegram IDs)
ALLOWED_TG_IDS=742873645

# Canonical origin — must match the Origin: header from the browser
PUBLIC_ORIGIN=https://doomedash.com

# Where data lives
DASH_DATA_DIR=/var/lib/bots-dashboard
DASH_CONFIG_DIR=/etc/bots-dashboard

# Agent access (loopback on A, SSH-tunneled loopback for B)
AGENT_SERVER_A_URL=http://127.0.0.1:8765
AGENT_SERVER_A_TOKEN=REPLACE_ME
AGENT_SERVER_B_URL=http://127.0.0.1:18765
AGENT_SERVER_B_TOKEN=REPLACE_ME

LOG_LEVEL=INFO
EOF
fi

log "installing inventory.yaml (idempotent)"
install -o root -g botsdash -m 0640 "$REPO_ROOT/deploy/inventory.yaml" /etc/bots-dashboard/inventory.yaml

# ─────────────────────────────────────────────────────────────
# SSH tunnel key + known_hosts
# ─────────────────────────────────────────────────────────────

if [[ ! -f /etc/bots-dashboard/tunnel_key ]]; then
    log "generating SSH tunnel key — add public half to server-B's authorized_keys"
    install -o botsdash -g botsdash -m 0600 /dev/null /etc/bots-dashboard/tunnel_key
    sudo -u botsdash ssh-keygen \
        -t ed25519 \
        -f /etc/bots-dashboard/tunnel_key \
        -N "" \
        -C "botsdash-tunnel@$(hostname)"
    log "tunnel public key:"
    cat /etc/bots-dashboard/tunnel_key.pub
    log ""
    log "On server B, add this line to /home/tunnel/.ssh/authorized_keys:"
    log "  restrict,permitopen=\"127.0.0.1:8765\" $(cat /etc/bots-dashboard/tunnel_key.pub)"
fi

if [[ ! -f /etc/bots-dashboard/known_hosts ]]; then
    log "pinning server-B host key into known_hosts"
    ssh-keyscan -t ed25519 144.31.136.4 > /etc/bots-dashboard/known_hosts 2>/dev/null || \
        log "WARN: ssh-keyscan failed — server B unreachable right now, fill known_hosts manually"
    chown root:botsdash /etc/bots-dashboard/known_hosts
    chmod 0640 /etc/bots-dashboard/known_hosts
fi

# ─────────────────────────────────────────────────────────────
# systemd units
# ─────────────────────────────────────────────────────────────

log "installing systemd units"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/bots-dashboard.service"         /etc/systemd/system/bots-dashboard.service
install -o root -g root -m 0644 "$REPO_ROOT/deploy/bots-dashboard-tunnel.service"  /etc/systemd/system/bots-dashboard-tunnel.service

systemctl daemon-reload

# ─────────────────────────────────────────────────────────────
# nginx + static bundle
# ─────────────────────────────────────────────────────────────

log "ensuring /var/www/bots-dashboard exists"
install -d -o botsdash -g www-data -m 0755 /var/www/bots-dashboard

if [[ -d "$REPO_ROOT/web/dist" ]]; then
    log "publishing /var/www/bots-dashboard from web/dist"
    rsync -a --delete "$REPO_ROOT/web/dist/" /var/www/bots-dashboard/
    chown -R botsdash:www-data /var/www/bots-dashboard
    find /var/www/bots-dashboard -type f -exec chmod 0644 {} \;
    find /var/www/bots-dashboard -type d -exec chmod 0755 {} \;
else
    log "WARN: web/dist not present — build the frontend locally and rsync the repo first"
fi

log "installing nginx site"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/nginx.doomedash.conf" /etc/nginx/sites-available/doomedash.com
ln -sf /etc/nginx/sites-available/doomedash.com /etc/nginx/sites-enabled/doomedash.com

log "testing nginx config"
nginx -t

log "reloading nginx"
systemctl reload nginx

log ""
log "done. Next steps:"
log "  1. Fill /etc/bots-dashboard/env (TG_BOT_TOKEN, AGENT_SERVER_*)"
log "  2. Run: certbot --nginx -d doomedash.com -d www.doomedash.com"
log "  3. systemctl enable --now bots-dashboard bots-dashboard-tunnel"
log "  4. Open https://doomedash.com/ to test"
