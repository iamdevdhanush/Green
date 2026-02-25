# Gunicorn configuration for GreenOps Server
# Used when starting: gunicorn -c gunicorn.conf.py main:app

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('SERVER_PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv("WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# Process name
proc_name = "greenops-server"

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# Graceful shutdown
graceful_timeout = 30

# Forwarded IP
forwarded_allow_ips = "*"
proxy_protocol = False
proxy_allow_from = "*"
