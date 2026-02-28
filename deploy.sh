#!/usr/bin/env bash
set -euo pipefail

# Senryaku deploy script — Ubuntu + Caddy
# Usage: ./deploy.sh [--domain example.com]

APP_NAME="senryaku"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${APP_DIR}/venv"
DATA_DIR="${APP_DIR}/data"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
CADDY_SNIPPET="/etc/caddy/conf.d/${APP_NAME}.caddy"
PORT=8000
DOMAIN=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "==> Deploying Senryaku from ${APP_DIR}"

# 1. Create venv and install dependencies
echo "==> Setting up Python venv..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}"

# 2. Create data directory
mkdir -p "${DATA_DIR}"

# 3. Create .env from example if not present
if [ ! -f "${APP_DIR}/.env" ]; then
    if [ -f "${APP_DIR}/.env.example" ]; then
        cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
        echo "==> Created .env from .env.example — edit it with your settings"
    fi
fi

# 4. Run Alembic migrations
echo "==> Running database migrations..."
cd "${APP_DIR}"
"${VENV_DIR}/bin/alembic" upgrade head

# 5. Create systemd service
echo "==> Creating systemd service..."
sudo tee "${SERVICE_FILE}" > /dev/null <<UNIT
[Unit]
Description=Senryaku — Personal Operations Server
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${VENV_DIR}/bin/uvicorn senryaku.main:app --host 127.0.0.1 --port ${PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable "${APP_NAME}"

# 6. Configure Caddy reverse proxy (if domain provided)
if [ -n "${DOMAIN}" ]; then
    echo "==> Configuring Caddy for ${DOMAIN}..."
    sudo mkdir -p /etc/caddy/conf.d
    sudo tee "${CADDY_SNIPPET}" > /dev/null <<CADDY
${DOMAIN} {
    reverse_proxy 127.0.0.1:${PORT}
}
CADDY

    # Check if Caddyfile imports conf.d
    if ! grep -q "import /etc/caddy/conf.d/" /etc/caddy/Caddyfile 2>/dev/null; then
        echo "import /etc/caddy/conf.d/*.caddy" | sudo tee -a /etc/caddy/Caddyfile > /dev/null
    fi
    sudo systemctl reload caddy 2>/dev/null || echo "  Note: Caddy not running. Start it with: sudo systemctl start caddy"
fi

# 7. Start/restart service
echo "==> Starting ${APP_NAME}..."
sudo systemctl restart "${APP_NAME}"

echo ""
echo "==> Deployment complete!"
echo "    Service: sudo systemctl status ${APP_NAME}"
echo "    Logs:    sudo journalctl -u ${APP_NAME} -f"
if [ -n "${DOMAIN}" ]; then
    echo "    URL:     https://${DOMAIN}"
else
    echo "    URL:     http://localhost:${PORT}"
fi
