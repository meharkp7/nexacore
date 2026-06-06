"""
settings.py
-----------
Small runtime settings helpers for production-safe defaults.
"""

from __future__ import annotations

import os


def allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


def app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower()


def hindsight_backend() -> str:
    return os.getenv("HINDSIGHT_BACKEND", "local").strip().lower()


def integrations_mode() -> str:
    """demo = mock Jira/email; live = real API when credentials are set."""
    return os.getenv("INTEGRATIONS_MODE", "demo").strip().lower()


def auth_required() -> bool:
    return os.getenv("AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes"}


def rbac_enforced() -> bool:
    """Enforce RBAC in production/staging or when AUTH_REQUIRED is enabled."""
    if os.getenv("RBAC_ENFORCE", "").strip().lower() in {"1", "true", "yes"}:
        return True
    if auth_required():
        return True
    return app_env() not in {"development", "test"}


def ticket_backend() -> str:
    return os.getenv("TICKET_BACKEND", "jira").strip().lower()
