#!/bin/bash
# GreenOps Agent - Linux Installer
# Usage: sudo bash install_linux.sh [SERVER_URL]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check root
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (sudo)"
fi

SERVER_URL="${1:-http://localhost:8000}"
INSTALL_DIR="/opt/greenops-agent"
CONFIG_DIR="/etc/greenops"
LOG_DIR="/var/log/greenops"
SERVICE_USER="greenops"

echo ""
echo "================================="
echo " GreenOps Agent - Linux Installer"
echo "================================="
echo ""
info "Server URL: $SERVER_URL"

# Check Python 3.9+
if ! python3 --version &>/dev/null; then
    error "Python 3.9+ required. Install with: apt-get install python3"
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VERSION found"

# Create user
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
    info "Created service user: $SERVICE_USER"
fi

# Create directories
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"
info "Created directories"

# Copy files
cp "$(dirname "$0")/agent.py" "$INSTALL_DIR/agent.py"
cp "$(dirname "$0")/requirements.txt" "$INSTALL_DIR/requirements.txt"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Install dependencies
info "Installing Python dependencies..."
python3 -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet --break-system-packages 2>/dev/null || \
    python3 -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet

# Write config
cat > "$CONFIG_DIR/config.json" << EOF
{
  "server_url": "$SERVER_URL",
  "heartbeat_interval": 60,
  "idle_threshold": 300,
  "log_level": "INFO"
}
EOF
info "Config written to $CONFIG_DIR/config.json"

# Write systemd service
cat > /etc/systemd/system/greenops-agent.service << EOF
[Unit]
Description=GreenOps Energy Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/agent.py
Restart=on-failure
RestartSec=30
StartLimitInterval=300
StartLimitBurst=5

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$LOG_DIR /etc/greenops

# Environment
Environment="GREENOPS_SERVER_URL=$SERVER_URL"
Environment="HOME=/tmp"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=greenops-agent

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable greenops-agent
systemctl start greenops-agent

echo ""
echo "================================="
success "GreenOps Agent Installed!"
echo "================================="
echo " Server:  $SERVER_URL"
echo " Config:  $CONFIG_DIR/config.json"
echo " Logs:    journalctl -u greenops-agent -f"
echo ""
echo " Status:  systemctl status greenops-agent"
echo " Stop:    systemctl stop greenops-agent"
echo " Restart: systemctl restart greenops-agent"
echo "================================="
