import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('SERVER_PORT', '8000')}"
backlog = 2048
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
proc_name = "greenops-server"
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
limit_request_line = 8190
limit_request_fields = 100
graceful_timeout = 30
forwarded_allow_ips = "*"
