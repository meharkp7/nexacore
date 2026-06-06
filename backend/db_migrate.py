"""
db_migrate.py
-------------
Run Alembic migrations when DATABASE_URL points at Postgres.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Apply pending Alembic migrations for Postgres deployments."""
    if not os.getenv("DATABASE_URL", "").strip():
        return

    try:
        from alembic import command
        from alembic.config import Config

        alembic_ini = Path(__file__).resolve().parent / "alembic.ini"
        config = Config(str(alembic_ini))
        command.upgrade(config, "head")
        logger.info("Database migrations applied successfully")
    except Exception:
        logger.exception("Failed to run database migrations")
        raise
