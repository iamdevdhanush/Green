#!/usr/bin/env bash
# ┌─────────────────────────────────────────────────────────────────────┐
# │  GreenOps — Complete Setup Script                                   │
# │  Enterprise Infrastructure Energy Intelligence Platform             │
# └─────────────────────────────────────────────────────────────────────┘
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

info()   { echo -e "${GREEN}[✓]${RESET} $1"; }
warn()   { echo -e "${YELLOW}[!]${RESET} $1"; }
error()  { echo -e "${RED}[✗]${RESET} $1"; exit 1; }
header() { echo -e "\n${BOLD}${BLUE}━━━ $1 ━━━${RESET}\n"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║           G R E E N O P S                 ║"
echo "  ║    Enterprise Energy Intelligence          ║"
echo "  ║         Setup & Installation               ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Prerequisites ──────────────────────────────────────────────────────────────
header "Checking Prerequisites"

command -v python3 &>/dev/null || error "Python 3.11+ is required. Install from python.org"
command -v pip3   &>/dev/null || error "pip3 is required"
command -v node   &>/dev/null || error "Node.js 18+ is required. Install from nodejs.org"
command -v npm    &>/dev/null || error "npm is required"

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
NODE_VER=$(node --version)
info "Python $PY_VER found"
info "Node.js $NODE_VER found"

if ! command -v psql &>/dev/null; then
    warn "PostgreSQL not in PATH. Install: https://www.postgresql.org/download/"
fi
if ! command -v redis-cli &>/dev/null; then
    warn "Redis not in PATH. Install: https://redis.io/download"
fi

# ── Backend Setup ──────────────────────────────────────────────────────────────
header "Backend Setup"

cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    info "Virtual environment created at backend/venv"
fi

# Activate venv
source venv/bin/activate
info "Virtual environment activated"

info "Installing Python dependencies (this may take a minute)..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
info "All Python dependencies installed"

# Create .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/CHANGE_THIS_TO_A_SECURE_RANDOM_64_CHAR_STRING/$SECRET/" .env
    else
        sed -i "s/CHANGE_THIS_TO_A_SECURE_RANDOM_64_CHAR_STRING/$SECRET/" .env
    fi
    info "Created backend/.env with auto-generated SECRET_KEY"
    warn "Edit backend/.env to set your DATABASE_URL and REDIS_URL if needed"
else
    info "backend/.env already exists"
fi

deactivate 2>/dev/null || true

# ── Database Setup ──────────────────────────────────────────────────────────────
header "Database Setup"

echo -e "${BLUE}To set up PostgreSQL manually, run these commands:${RESET}"
echo ""
echo "  sudo -u postgres psql << 'EOF'"
echo "  CREATE USER greenops WITH PASSWORD 'greenops_dev';"
echo "  CREATE DATABASE greenops OWNER greenops;"
echo "  GRANT ALL PRIVILEGES ON DATABASE greenops TO greenops;"
echo "  EOF"
echo ""
echo -e "${BLUE}Default connection: postgresql://greenops:greenops_dev@localhost:5432/greenops${RESET}"
echo ""

read -rp "Press ENTER after database is ready (or Ctrl+C to exit and set up manually)..."

# Run migrations
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
info "Running database migrations..."
alembic upgrade head && info "Migrations applied successfully"
deactivate 2>/dev/null || true

# ── Frontend Setup ──────────────────────────────────────────────────────────────
header "Frontend Setup"

cd "$SCRIPT_DIR/frontend"
info "Installing Node.js dependencies..."
npm install --silent
info "Frontend dependencies installed"

# ── Create startup scripts ──────────────────────────────────────────────────────
header "Creating Startup Scripts"

cd "$SCRIPT_DIR"

cat > start-backend.sh << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
source venv/bin/activate
echo "Starting GreenOps API on http://localhost:8000"
echo "API docs available at http://localhost:8000/api/docs"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start-backend.sh

cat > start-celery.sh << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
source venv/bin/activate
echo "Starting Celery worker + beat scheduler"
celery -A app.workers.celery_app worker -B --loglevel=info
EOF
chmod +x start-celery.sh

cat > start-frontend.sh << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")/frontend"
echo "Starting GreenOps frontend on http://localhost:5173"
npm run dev
EOF
chmod +x start-frontend.sh

cat > start-all.sh << 'EOF'
#!/usr/bin/env bash
# Starts all services (requires tmux or run in separate terminals)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v tmux &>/dev/null; then
    SESSION="greenops"
    tmux new-session -d -s $SESSION -n "api"
    tmux send-keys -t $SESSION:api "$SCRIPT_DIR/start-backend.sh" Enter
    tmux new-window -t $SESSION -n "celery"
    tmux send-keys -t $SESSION:celery "$SCRIPT_DIR/start-celery.sh" Enter
    tmux new-window -t $SESSION -n "frontend"
    tmux send-keys -t $SESSION:frontend "$SCRIPT_DIR/start-frontend.sh" Enter
    tmux new-window -t $SESSION -n "shell"
    echo "GreenOps started in tmux session '$SESSION'"
    echo "Attach: tmux attach -t $SESSION"
    tmux attach -t $SESSION
else
    echo "Run each in a separate terminal:"
    echo "  Terminal 1: ./start-backend.sh"
    echo "  Terminal 2: ./start-celery.sh"
    echo "  Terminal 3: ./start-frontend.sh"
fi
EOF
chmod +x start-all.sh

info "Startup scripts created"

# ── Done ────────────────────────────────────────────────────────────────────────
header "Setup Complete"

echo -e "${GREEN}${BOLD}GreenOps is ready!${RESET}"
echo ""
echo -e "${BOLD}Quick Start:${RESET}"
echo "  1. Ensure PostgreSQL and Redis are running"
echo "  2. ./start-backend.sh      → API on http://localhost:8000"
echo "  3. ./start-frontend.sh     → UI on http://localhost:5173"
echo "  4. ./start-celery.sh       → Background workers"
echo "  5. Open http://localhost:5173 and register your first admin account"
echo ""
echo -e "${BOLD}Agent Installation (on monitored servers):${RESET}"
echo "  cd agent/"
echo "  pip install -r requirements.txt"
echo "  python greenops_agent.py --server http://your-api-host:8000"
echo ""
echo -e "${BOLD}API Documentation:${RESET} http://localhost:8000/api/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
