# GreenOps v2.0 — Green IT Infrastructure Monitoring Platform

Production-ready SaaS platform for monitoring organizational computers, tracking idle machines, estimating energy waste, and optimizing infrastructure utilization.

## What's New in v2.0

- **Argon2id** password hashing (replaces plain/weak hashing)
- **Access + Refresh token** JWT system (replaces single insecure token)
- **Rate limiting** with per-IP brute-force protection (10 login attempts / 5 min)
- **Account lockout** after repeated failures
- **Secure agent tokens** (SHA-256 hashed, revocable)
- **RBAC** (admin/viewer roles)
- **Input validation** on all endpoints (Pydantic v2)
- **Security headers** middleware (XSS, CSRF, clickjacking protection)
- **Structured logging** with request IDs
- **Production Docker** multi-stage build (non-root, minimal image)
- **Nginx reverse proxy** with rate limiting, gzip, secure headers
- **Environment-based config** with startup validation
- **Health check** endpoint
- **Cross-platform agent** (Windows 10+, Linux, macOS)
- **Offline queue** for agent heartbeats
- **Modern dashboard** with real-time charts

---

## Quick Start (< 5 minutes)

### 1. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set these:
# - POSTGRES_PASSWORD
# - JWT_SECRET_KEY  (generate: python3 -c "import secrets; print(secrets.token_urlsafe(48))")
# - INITIAL_ADMIN_PASSWORD
```

### 2. Start Server

```bash
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f server
```

### 3. Open Dashboard

Visit **http://localhost** and sign in with your admin credentials.

### 4. Run Agent

**Windows:**
```cmd
cd agent
pip install -r requirements.txt
set GREENOPS_SERVER_URL=http://your-server
python agent.py
```

Or use the installer (run as Administrator):
```cmd
install_windows.bat
```

**Linux:**
```bash
# Quick run
GREENOPS_SERVER_URL=http://your-server python3 agent/agent.py

# Install as systemd service
sudo bash agent/install_linux.sh http://your-server
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│                    React Dashboard                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (Port 80/443)                      │
│         Rate limiting · Gzip · Secure headers               │
└──────────────┬────────────────────────┬─────────────────────┘
               │ /api/*                 │ /
               ▼                        ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  FastAPI + Gunicorn  │    │  Static files (React build)  │
│  (Port 8000)         │    │  served directly by Nginx    │
│  4 Uvicorn workers   │    └──────────────────────────────┘
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  PostgreSQL 16       │
│  (Internal network)  │
└──────────────────────┘

Agents (Windows/Linux/macOS)
└── POST /api/agents/register   (get token)
└── POST /api/agents/heartbeat  (every 60s)
```

---

## API Reference

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Login → access + refresh tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET | `/api/auth/verify` | Verify access token |
| GET | `/api/auth/me` | Get current user info |

### Agents (token auth)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agents/register` | Register/re-register machine |
| POST | `/api/agents/heartbeat` | Submit heartbeat |
| GET | `/api/agents/health` | Agent connectivity check |

### Machines (JWT auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/machines` | List machines (filterable) |
| GET | `/api/machines/{id}` | Machine details |
| PATCH | `/api/machines/{id}` | Update machine |
| DELETE | `/api/machines/{id}` | Delete machine |
| GET | `/api/machines/{id}/heartbeats` | Heartbeat history |
| POST | `/api/machines/{id}/revoke-token` | Revoke agent token |

### Dashboard (JWT auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/stats` | Aggregate statistics |
| GET | `/api/dashboard/energy-trend?days=7` | Energy trend |
| GET | `/api/dashboard/top-idle` | Top idle machines |
| GET | `/api/dashboard/recent-activity` | Recent heartbeats |

---

## Security

### Password Hashing
- Algorithm: **Argon2id** (OWASP recommended)
- Parameters: time_cost=3, memory_cost=64MiB, parallelism=4
- Automatic rehash on login if parameters are upgraded

### Token Security
- **Access tokens**: JWT HS256, 60-minute expiry
- **Refresh tokens**: random 48-byte URL-safe token, SHA-256 hashed, 30-day expiry, rotated on use
- **Agent tokens**: `agt_` prefixed, SHA-256 hashed, revocable

### Brute Force Protection
- 10 failed logins → account locked for 15 minutes
- Rate limit: 10 login requests / 5 minutes per IP
- General API: 100 requests / 60 seconds per IP

### Production Checklist

- [ ] Strong `POSTGRES_PASSWORD` (min 20 chars)
- [ ] Strong `JWT_SECRET_KEY` (min 48 chars, generated randomly)
- [ ] Strong `INITIAL_ADMIN_PASSWORD` (min 12 chars)
- [ ] Change default admin password after first login
- [ ] Set correct `CORS_ORIGINS` for your domain
- [ ] Enable HTTPS (uncomment nginx SSL config)
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Enable firewall (only expose ports 80/443)
- [ ] Set `ENV=production`
- [ ] Set `DEBUG=false`

---

## Agent Configuration

Priority order: environment variables > config file > defaults

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GREENOPS_SERVER_URL` | `http://localhost:8000` | Server URL |
| `GREENOPS_HEARTBEAT_INTERVAL` | `60` | Seconds between heartbeats |
| `GREENOPS_IDLE_THRESHOLD` | `300` | Seconds of inactivity = idle |
| `GREENOPS_LOG_LEVEL` | `INFO` | Log verbosity |
| `GREENOPS_AGENT_TOKEN` | — | Persist token across restarts |
| `GREENOPS_MACHINE_ID` | — | Persist machine ID |

### Config File

- **Windows**: `C:\ProgramData\GreenOps\config.json`
- **Linux/macOS**: `~/.greenops/config.json`

```json
{
  "server_url": "http://your-server",
  "heartbeat_interval": 60,
  "idle_threshold": 300,
  "log_level": "INFO"
}
```

---

## Operations

### Backups
```bash
# Create backup
docker exec greenops-db pg_dump -U greenops greenops | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
docker exec -i greenops-db psql -U greenops greenops < backup.sql
```

### Logs
```bash
# All services
docker-compose logs -f

# Server only
docker-compose logs -f server

# Agent (Linux systemd)
journalctl -u greenops-agent -f

# Agent (Windows)
type C:\ProgramData\GreenOps\agent.log
```

### Scaling
```bash
# Scale API workers (horizontal)
docker-compose up -d --scale server=3
```

---

## Development

```bash
# Backend
cd server
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd dashboard
npm install
npm start  # http://localhost:3000
```

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Server CPU | 2 cores | 4+ cores |
| Server RAM | 2 GB | 4+ GB |
| Server Disk | 20 GB | 50+ GB |
| Server OS | Linux (Docker) | Ubuntu 22.04 LTS |
| Agent Python | 3.9+ | 3.11+ |
| Agent OS | Windows 10, Linux kernel 4.x | Windows 11, Ubuntu 22.04 |
| Agent RAM | 30 MB | — |

---

*Built for reliability. Designed for scale. Ready for production.*
