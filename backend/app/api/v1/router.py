"""Aggregate v1 API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import audit, auth, projects, tasks, users
from app.core.config import settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(users.router)
api_router.include_router(audit.router)

if settings.dev_auth_enabled:
    api_router.include_router(auth.router)
