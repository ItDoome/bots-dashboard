#!/usr/bin/env bash
# Deploy the bots-dashboard agent on a host (server A or server B).
#
# Run AS ROOT. Needs to be run on BOTH servers. Picks manifest by env var
# AGENT_ID (default: server-a). Server-specific manifests live in
# deploy/manifest.${AGENT_ID}.yaml.
#
# Safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT_ID="${AGENT_ID:-server-a}"

log() { echo "[deploy-agent:$AGENT_ID] $*"; }

# ─────────────────────────────────────────────────────────────
# Users and directories
# ─────────────────────────────────────────────────────────────

log "creating botsagent user (if missing)"
if ! id botsagent >/dev/null 2>&1; then
    useradd --system --shell /usr/sbin/nologin \
            --home-dir /var/lib/bots-dashboard-agent \
            --create-home botsagent
fi

log "ensuring directories exist"
install -d -o botsagent -g botsagent -m 0750 /var/lib/bots-dashboard-agent
install -d -o botsagent -g botsagent -m 0750 /var/backups/bots-dashboard-agent
install -d -o root      -g botsagent -m 0750 /etc/bots-dashboard-agent

# ─────────────────────────────────────────────────────────────
# Python virtualenv (shared with central on server A)
# ─────────────────────────────────────────────────────────────

if [[ ! -d "$REPO_ROOT/.venv" ]]; then
    log "creating venv at $REPO_ROOT/.venv"
    python3.12 -m venv "$REPO_ROOT/.venv"
    "$REPO_ROOT/.venv/bin/pip" install --upgrade pip wheel
    "$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/requirements.txt"
fi

# ─────────────────────────────────────────────────────────────
# Install root-owned helper scripts + sudoers snippet
# ─────────────────────────────────────────────────────────────

log "installing root-owned helper scripts"
install -o root -g root -m 0755 "$REPO_ROOT/deploy/helpers/botsdash-systemctl"  /usr/local/bin/botsdash-systemctl
install -o root -g root -m 0755 "$REPO_ROOT/deploy/helpers/botsdash-journalctl" /usr/local/bin/botsdash-journalctl

log "installing sudoers snippet (validating with visudo)"
visudo -cf "$REPO_ROOT/deploy/sudoers.botsagent"
install -o root -g root -m 0440 "$REPO_ROOT/deploy/sudoers.botsagent" /etc/sudoers.d/botsagent

# ─────────────────────────────────────────────────────────────
# Manifest and env file
# ─────────────────────────────────────────────────────────────

MANIFEST_SRC="$REPO_ROOT/deploy/manifest.${AGENT_ID}.yaml"
if [[ ! -f "$MANIFEST_SRC" ]]; then
    log "ERROR: manifest $MANIFEST_SRC not found"
    exit 1
fi
log "installing manifest for $AGENT_ID"
install -o root -g botsagent -m 0640 "$MANIFEST_SRC" /etc/bots-dashboard-agent/manifest.yaml

if [[ ! -f /etc/bots-dashboard-agent/env ]]; then
    log "creating /etc/bots-dashboard-agent/env template — FILL IN SECRETS"
    install -o root -g botsagent -m 0640 /dev/null /etc/bots-dashboard-agent/env
    cat > /etc/bots-dashboard-agent/env <<EOF
AGENT_ID=$AGENT_ID
AGENT_TOKEN=REPLACE_ME_WITH_32_RANDOM_BYTES_BASE64
AGENT_HOST=127.0.0.1
AGENT_PORT=8765
AGENT_MANIFEST=/etc/bots-dashboard-agent/manifest.yaml
AGENT_BACKUP_DIR=/var/backups/bots-dashboard-agent
LOG_LEVEL=INFO
WEB_CONCURRENCY=1
EOF
fi

# ─────────────────────────────────────────────────────────────
# systemd unit
# ─────────────────────────────────────────────────────────────

log "installing systemd unit"
install -o root -g root -m 0644 "$REPO_ROOT/deploy/bots-dashboard-agent.service" /etc/systemd/system/bots-dashboard-agent.service
systemctl daemon-reload

# ─────────────────────────────────────────────────────────────
# Read access for botsagent to bot files
# ─────────────────────────────────────────────────────────────

log "ensuring botsagent can read the bot files"
case "$AGENT_ID" in
    server-a)
        # Give group access to /opt/tg_bot/*.json
        if [[ -d /opt/tg_bot ]]; then
            chmod g+rx /opt/tg_bot
            chmod g+r /opt/tg_bot/*.json 2>/dev/null || true
            # Add botsagent to the lolz-bot group (whatever it's called)
            if getent group tg_bot >/dev/null; then
                usermod -a -G tg_bot botsagent
            fi
        fi
        ;;
    server-b)
        if [[ -d /opt/rebot/current ]]; then
            chmod g+rx /opt/rebot/current
            chmod g+r /opt/rebot/current/bot.sqlite3 2>/dev/null || true
            if getent group rebot >/dev/null; then
                usermod -a -G rebot botsagent
            fi
        fi
        # Set up the tunnel user on server B
        if ! id tunnel >/dev/null 2>&1; then
            log "creating tunnel user (for SSH from server A)"
            useradd --system --shell /usr/sbin/nologin \
                    --home-dir /home/tunnel --create-home tunnel
            install -d -o tunnel -g tunnel -m 0700 /home/tunnel/.ssh
            touch /home/tunnel/.ssh/authorized_keys
            chown tunnel:tunnel /home/tunnel/.ssh/authorized_keys
            chmod 0600 /home/tunnel/.ssh/authorized_keys
            log "ADD the server-A tunnel public key to /home/tunnel/.ssh/authorized_keys"
            log "Format: restrict,permitopen=\"127.0.0.1:8765\" ssh-ed25519 AAAA..."
        fi
        ;;
    *)
        log "WARN: unknown AGENT_ID $AGENT_ID, skipping file permissions"
        ;;
esac

log ""
log "done. Next steps:"
log "  1. Fill /etc/bots-dashboard-agent/env (AGENT_TOKEN)"
log "  2. systemctl enable --now bots-dashboard-agent"
log "  3. curl http://127.0.0.1:8765/health"
