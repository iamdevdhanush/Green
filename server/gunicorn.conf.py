##############################################################################
# GreenOps — gunicorn.conf.py
#
# Key setting: preload_app = True
#
# Why this fixes the multi-worker admin creation race condition:
# ─────────────────────────────────────────────────────────────
# Without preload_app (the default), Gunicorn starts N worker processes and
# each worker independently imports the FastAPI app and runs the lifespan
# startup function. With 4 workers, ensure_admin_exists() runs 4 times
# simultaneously. Even with an IntegrityError catch, you get 4 DB round-trips,
# 3 rollbacks, and non-deterministic startup ordering.
#
# With preload_app = True:
# 1. Master process imports app and runs lifespan startup ONCE.
# 2. Workers are forked from the master after startup completes.
# 3. ensure_admin_exists() is called exactly once, deterministically.
# 4. Workers inherit the initialized state from the master.
#
# Note: preload_app = True means workers share the master's file descriptors.
# SQLAlchemy async engine creates new connections per-worker correctly because
# asyncpg connections are not inheritable across fork boundaries — each worker
# gets a fresh connection pool on startup. This is safe.
##############################################################################

import os

# ── Binding ─────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('SERVER_PORT', '8000')}"
backlog = 2048

# ── Workers ─────────────────────────────────────────────────────────────────
# Formula: 2 × vCPU + 1, capped at 8 for memory safety on shared VPS.
# Override via WORKERS env var at runtime.
workers = int(os.getenv("WORKERS", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
threads = 1                 # UvicornWorker is async; threads not needed

# ── THE RACE CONDITION FIX ──────────────────────────────────────────────────
# preload_app = True causes the master process to import and initialize the
# app (including lifespan startup) ONCE before forking workers.
# This is the primary fix for duplicate admin creation and DB race conditions.
preload_app = True

# ── Timeouts ────────────────────────────────────────────────────────────────
timeout = 60                # worker silent timeout — kill if no response
graceful_timeout = 30       # time to finish in-flight requests on SIGTERM
keepalive = 5               # seconds to keep idle connections alive

# ── Request limits (prevent memory leaks in long-running workers) ────────────
max_requests = 1000         # restart worker after N requests
max_requests_jitter = 100   # randomize to avoid thundering herd restarts

# ── Process naming ──────────────────────────────────────────────────────────
proc_name = "greenops-server"

# ── Logging ─────────────────────────────────────────────────────────────────
accesslog = "-"             # stdout (captured by Docker)
errorlog = "-"              # stderr (captured by Docker)
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# ── Security ─────────────────────────────────────────────────────────────────
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ── Trusted proxy IPs ────────────────────────────────────────────────────────
# "*" trusts all X-Forwarded-For headers. This is safe because our nginx
# container is the only entry point and rewrites this header correctly.
# In a multi-hop load balancer setup, specify the load balancer IP instead.
forwarded_allow_ips = "*"
