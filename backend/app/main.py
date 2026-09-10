"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import engine
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware

configure_logging()
log = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("startup", env=settings.app_env, dev_auth=settings.dev_auth_enabled)
    yield
    await engine.dispose()
    log.info("shutdown")


app = FastAPI(
    title="Enterprise Project & Task Tracker API",
    version="0.1.0",
    description="Internal task tracker — see docs/spec.md. OpenAPI 3.1 generated from FastAPI.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # bearer tokens, never cookies (spec §7.3 CSRF)
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "If-Match", "X-Request-Id"],
    expose_headers=["ETag", "X-Request-Id"],
)

install_error_handlers(app)

# Routers are imported after logging/error setup so their module-level code sees
# a configured environment.
from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)


@app.get("/healthz", tags=["meta"], include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["meta"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "task-tracker-api", "docs": "/api/v1/docs"}
