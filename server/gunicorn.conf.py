##############################################################################
# GreenOps — gunicorn.conf.py
#
# Key setting: preload_app = True
#
# Why preload_app fixes the multi-worker admin creation race condition:
# ─────────────────────────────────────────────────────────────────────
# Without preload_app (the default), each of N workers independently imports
# the FastAPI app and runs the lifespan startup. With 4 workers,
# ensure_admin_exists() would race 4 times. The pg_advisory_xact_lock
# serialises them, but it still adds unnecessary DB round-trips.
#
# With preload_app = True:
# 1. Master process imports app and runs lifespan startup ONCE.
# 2. Workers are forked from the master after startup completes.
# 3. ensure_admin_exists() is called exactly once, deterministically.
# 4. Workers inherit the initialized state from the master.
#
# Worker failure model (now that sys.exit is removed from lifespan):
# ──────────────────────────────────────────────────────────────────
# If a worker's lifespan raises an exception, Gunicorn marks that worker
# as failed and restarts it. worker_max_restarts caps the total restarts
# to prevent infinite crash loops on permanent failures (bad config, etc).
# After max restarts, the worker is not restarted and the master continues
# serving with the remaining healthy workers.
##############################################################################

import os

# ── Binding ─────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('SERVER_PORT', '8000')}"
backlog = 2048

# ── Workers ─────────────────────────────────────────────────────────────────
workers = int(os.getenv("WORKERS", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
threads = 1  # UvicornWorker is async; threads not needed

# ── THE RACE CONDITION FIX ──────────────────────────────────────────────────
# preload_app = True causes the master process to import and initialize the
# app (including lifespan startup) ONCE before forking workers.
preload_app = True

# ── Timeouts ────────────────────────────────────────────────────────────────
timeout = 60
graceful_timeout = 30
keepalive = 5

# ── Request limits ───────────────────────────────────────────────────────────
max_requests = 1000
max_requests_jitter = 100

# ── Worker restart limits ────────────────────────────────────────────────────
# Prevent infinite crash loops if a worker fails on startup repeatedly.
# After this many restarts, the worker slot is abandoned (master keeps running).
worker_max_restarts = 5

# ── Process naming ──────────────────────────────────────────────────────────
proc_name = "greenops-server"

# ── Logging ─────────────────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# ── Security ─────────────────────────────────────────────────────────────────
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ── Trusted proxy IPs ────────────────────────────────────────────────────────
forwarded_allow_ips = "*"
