"""
gunicorn.conf.py
----------------
Production WSGI config for Render and other container hosts.
Run Alembic once in the master process before workers fork.
"""

import os

from backend.db_migrate import run_migrations

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5


def on_starting(_server) -> None:
    """Master-only hook: migrate before any worker imports the app DB."""
    run_migrations()
