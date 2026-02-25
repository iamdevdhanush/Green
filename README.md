# GreenOps — Green IT Infrastructure Monitoring

Production-ready platform to monitor organizational computers, track idle machines,
estimate energy waste, and optimize infrastructure utilization.

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env and set:
#   JWT_SECRET_KEY   — generate with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
#   POSTGRES_PASSWORD — strong random password
#   ADMIN_DEFAULT_PASSWORD — your admin dashboard password
```

### 2. Start Services

```bash
docker compose up -d
```

### 3. Open Dashboard

Navigate to **http://localhost** and log in with:
- Username: `admin`
- Password: whatever you set in `ADMIN_DEFAULT_PASSWORD`

### 4. Run Agent

```bash
cd agent
pip install -r requirements.txt

# Point at your server
export GREENOPS_SERVER_URL=http://your-server-ip:80

python agent.py
```

## Architecture

```
Agents → FastAPI Server → PostgreSQL
                ↑
            Dashboard (nginx)
```

- **Server**: FastAPI + asyncpg (PostgreSQL), Argon2id password hashing, JWT auth
- **Dashboard**: Vanilla HTML/JS served by nginx, proxied to API
- **Agent**: Python, cross-platform idle detection, retry logic

## Security

- Passwords hashed with Argon2id (time=2, mem=64MB, parallelism=4)
- JWT tokens with configurable expiry
- Agent tokens are UUID4, stored as SHA256 hash
- No hardcoded credentials — all secrets via environment variables
- Nginx rate limiting on login endpoint (10 req/min)
- Non-root container user
- Internal Docker network (DB not exposed)

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/login | — | Get JWT token |
| GET | /api/auth/verify | JWT | Verify token |
| POST | /api/agents/register | — | Register agent |
| POST | /api/agents/heartbeat | Agent token | Send heartbeat |
| GET | /api/machines | JWT | List machines |
| GET | /api/machines/{id} | JWT | Machine detail |
| GET | /api/machines/{id}/heartbeats | JWT | Heartbeat history |
| GET | /api/dashboard/stats | JWT | Aggregate stats |
| GET | /health | — | Health check |

## Environment Variables

See `.env.example` for full documentation.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | ✅ | — | JWT signing secret (min 32 chars) |
| `POSTGRES_PASSWORD` | ✅ | — | Database password |
| `ADMIN_DEFAULT_PASSWORD` | ✅ | — | Initial admin password |
| `DATABASE_URL` | auto | — | Set by docker-compose |
| `DEBUG` | ❌ | false | Enable /docs endpoint |
| `CORS_ORIGINS` | ❌ | http://localhost | Allowed origins |
| `IDLE_POWER_WATTS` | ❌ | 65 | Idle power draw (W) |
| `ELECTRICITY_COST_PER_KWH` | ❌ | 0.12 | Cost per kWh (USD) |

## Operations

```bash
# View logs
docker compose logs -f server

# DB backup
docker exec greenops-db pg_dump -U greenops greenops > backup.sql

# Health check
curl http://localhost/health
```

