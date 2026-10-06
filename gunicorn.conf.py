"""Gunicorn settings for the production ASGI server.

Gunicorn manages the worker processes and each worker serves
`api.asgi:application` through uvicorn (`uvicorn-worker`). Every production
command (Dockerfile, Compose, Dockerfile.single, PaaS, k3s) runs
`gunicorn api.asgi:application` from /app, and Gunicorn loads this file from
the working directory. Tune with environment variables, not CLI flags, so every
target keeps the same settings.

Each worker owns one psycopg connection pool, so the peak number of database
connections is GUNICORN_WORKERS x DB_POOL_MAX_SIZE. Do not enable
`preload_app`: the pool must be created after the fork, in each worker.
"""

import os
from pathlib import Path

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
worker_class = "uvicorn_worker.UvicornWorker"
# Heartbeat files on tmpfs, as the Gunicorn docs advise for containers: a
# disk-backed /tmp can block workers. /dev/shm exists in Linux containers, not
# on macOS. Gunicorn creates and unlinks the files itself (no shared names).
_SHM = "/dev/shm"  # nosec B108
worker_tmp_dir = _SHM if Path(_SHM).is_dir() else None
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
# Recycle workers to bound memory growth.
max_requests = 1000
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
capture_output = True
enable_stdio_inheritance = True
