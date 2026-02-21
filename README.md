# GreenOps — Enterprise Infrastructure Energy Intelligence

> Stop wasting energy. Stop wasting money. Know exactly where your CO₂ comes from.

GreenOps is a production-ready SaaS platform that automatically monitors your infrastructure, tracks idle energy waste, calculates real CO₂ emissions and cost impact, and enables secure remote shutdown of idle machines — all in a beautifully designed real-time dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GREENOPS PLATFORM                        │
├──────────────┬──────────────────────────┬────────────────────────┤
│   Frontend   │         Backend          │       Agents           │
│              │                          │                        │
│  React/TS    │   FastAPI (Python)       │  Python daemon on      │
│  Vite        │   PostgreSQL             │  monitored servers     │
│  Tailwind    │   Redis (cache/queue)    │                        │
│  Recharts    │   Celery workers         │  Heartbeat every 60s   │
│  Framer      │   JWT + RBAC             │  Idle detection        │
│  WebSocket   │   Prometheus metrics     │  Remote shutdown       │
│  Port: 5173  │   Port: 8000             │  validation            │
└──────────────┴──────────────────────────┴────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+

### 1. Setup

```bash
git clone <repo>
cd greenops
chmod +x setup.sh
./setup.sh
```

### 2. Start Services

**Terminal 1 — API:**
```bash
./start-backend.sh
```

**Terminal 2 — Background Workers:**
```bash
./start-celery.sh
```

**Terminal 3 — Frontend:**
```bash
./start-frontend.sh
```

### 3. First Login

Open `http://localhost:5173`

The **first registered user automatically becomes an Admin**.

---

## Environment Variables

See `backend/.env.example` for all configuration options.

Key settings:
| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://greenops:greenops_dev@localhost:5432/greenops` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key (auto-generated) | — |
| `IDLE_KWH_PER_HOUR` | kWh per idle server hour | `0.12` |
| `CO2_KG_PER_KWH` | CO₂ intensity factor | `0.386` |
| `COST_PER_KWH` | Electricity rate USD | `0.12` |

---

## Agent Installation

Install the GreenOps Agent on servers you want to monitor:

```bash
cd agent/
pip install -r requirements.txt

# Register and run continuously
python greenops_agent.py --server http://your-greenops-host:8000

# Register only (get API key)
python greenops_agent.py --server http://your-host:8000 --register-only
```

### Systemd Service

```bash
# Install as system service
sudo cp agent/greenops-agent.service /etc/systemd/system/
sudo systemctl enable --now greenops-agent
```

---

## API Reference

Interactive docs at: `http://localhost:8000/api/docs`

### Authentication
```
POST /api/v1/auth/register    Create user account
POST /api/v1/auth/login       Get JWT tokens
POST /api/v1/auth/refresh     Refresh access token
GET  /api/v1/auth/me          Current user
```

### Agent API (API Key auth via X-API-Key header)
```
POST /api/v1/agents/register       Register new machine
POST /api/v1/agents/heartbeat      Report telemetry
GET  /api/v1/agents/commands/poll  Check for commands
POST /api/v1/agents/commands/result Report command execution
```

### Machines
```
GET    /api/v1/machines              List machines (paginated)
GET    /api/v1/machines/{id}         Machine details
GET    /api/v1/machines/{id}/history Energy history
DELETE /api/v1/machines/{id}         Deactivate machine
```

### Analytics
```
GET /api/v1/analytics/overview             Platform stats
GET /api/v1/analytics/energy/timeseries    kWh time series
GET /api/v1/analytics/co2/trend            CO₂ daily trend
GET /api/v1/analytics/cost/projection      Cost projection
GET /api/v1/analytics/monthly              Monthly aggregates
GET /api/v1/analytics/audit                Audit log
```

### Commands (Admin only)
```
POST /api/v1/commands/shutdown     Issue shutdown command
GET  /api/v1/commands/shutdown/{id} List machine commands
```

---

## Security Features

| Feature | Implementation |
|---------|---------------|
| Password hashing | bcrypt (cost factor 12) |
| JWT tokens | Access (30m) + Refresh (7d) |
| API keys | `grn_` prefixed, 48-char random |
| RBAC | Admin / Manager / Viewer roles |
| Rate limiting | slowapi + Redis |
| MAC uniqueness | DB unique constraint |
| Shutdown auth | Idle re-validation on agent |
| Command TTL | 2-minute auto-expiry |
| Audit trail | Every action logged |
| SQL injection | SQLAlchemy ORM (parameterized) |
| CORS | Configured allowlist |

---

## Folder Structure

```
greenops/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # Route handlers
│   │   ├── core/               # Config, DB, security, Redis
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   ├── workers/            # Celery tasks
│   │   ├── middleware/         # Rate limiting
│   │   └── main.py             # FastAPI app entry
│   ├── alembic/                # DB migrations
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── components/         # Reusable UI & layout
│       ├── pages/              # Route pages
│       ├── services/           # Axios API client
│       ├── store/              # Zustand state
│       └── types/              # TypeScript types
│
├── agent/
│   ├── greenops_agent.py       # Agent daemon
│   └── greenops-agent.service  # systemd unit
│
└── setup.sh                    # One-command setup
```

---

## Energy Calculations

```
idle_hours    = idle_minutes / 60
energy_kwh    = idle_hours × 0.12 kWh/hr
co2_kg        = energy_kwh × 0.386 kg/kWh (US grid average)
cost_usd      = energy_kwh × $0.12/kWh
```

All constants are configurable via environment variables.

---

## Background Workers

Celery Beat runs two periodic tasks:

| Task | Schedule | Purpose |
|------|----------|---------|
| `aggregate_monthly_task` | 1st of month, 00:05 UTC | Aggregate metrics into `monthly_analytics` |
| `mark_offline_machines_task` | Every 5 minutes | Mark machines with no heartbeat > 5m as offline |

---

## Prometheus Metrics

Available at `GET /metrics` in Prometheus format. Includes:
- HTTP request duration histograms
- Request counts by endpoint and status
- In-progress requests

---

## License

Proprietary — GreenOps Enterprise Edition
