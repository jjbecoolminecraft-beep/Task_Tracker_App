"""Test fixtures.

A throwaway ``tracker_test`` database is created once per session and migrated
with Alembic (so the search-vector and append-only triggers are exercised, not
just ``create_all``). Each test gets a freshly re-seeded database.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
ADMIN_DSN = os.environ.get(
    "TEST_ADMIN_DSN", "postgresql://tracker:tracker@localhost:5432/postgres"
)
TEST_DB = "tracker_test"
TEST_URL = f"postgresql+asyncpg://tracker:tracker@localhost:5432/{TEST_DB}"

# Must be set before any app module imports so the cached Settings pick it up.
os.environ["DATABASE_URL"] = TEST_URL
os.environ["APP_ENV"] = "test"
os.environ["DEV_AUTH_ENABLED"] = "true"
os.environ["DEV_AUTH_SECRET"] = "test-secret-key-at-least-32-bytes-long-000"

import asyncpg  # noqa: E402
import httpx  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


def _recreate_database() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(ADMIN_DSN)
        try:
            await conn.execute(
                f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'
            )
            await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    _recreate_database()
    env = {**os.environ, "DATABASE_URL": TEST_URL}
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    yield


@pytest.fixture(autouse=True)
async def _seed() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.exec_driver_sql("TRUNCATE audit_events RESTART IDENTITY")
        await conn.exec_driver_sql(
            "TRUNCATE task_shares, task_labels, comments, tasks, workflow_states, "
            "labels, project_members, role_grants, projects, portfolios, users "
            "RESTART IDENTITY CASCADE"
        )
    await seed()
    yield


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def dev_users(client: httpx.AsyncClient) -> dict[str, dict]:
    resp = await client.get("/api/v1/auth/dev-users")
    return {u["display_name"]: u for u in resp.json()}


@pytest.fixture
async def as_user(client: httpx.AsyncClient, dev_users: dict[str, dict]):
    """Return a callable: name -> httpx.AsyncClient with that user's bearer token."""
    opened: list[httpx.AsyncClient] = []

    async def _login(display_name: str) -> httpx.AsyncClient:
        user = dev_users[display_name]
        resp = await client.post("/api/v1/auth/dev-login", json={"user_id": user["id"]})
        token = resp.json()["access_token"]
        c = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        )
        opened.append(c)
        return c

    yield _login
    for c in opened:
        await c.aclose()


@pytest.fixture
async def world(as_user) -> dict[str, str]:
    """Seeded ids the tests reference, resolved through the API as a broad reader."""
    clara = await as_user("Clara Schmidt")  # Portfolio Owner → sees MKTG + OPS
    elena = await as_user("Elena Popova")  # Project Admin ENG

    projects = {p["key"]: p for p in (await clara.get("/api/v1/projects")).json()}
    eng = next(p for p in (await elena.get("/api/v1/projects")).json() if p["key"] == "ENG")

    mktg_tasks = (await clara.get(f"/api/v1/projects/{projects['MKTG']['id']}/tasks?limit=50")).json()
    eng_tasks = (await elena.get(f"/api/v1/projects/{eng['id']}/tasks?limit=50")).json()
    mktg_states = (await clara.get(f"/api/v1/projects/{projects['MKTG']['id']}/workflow-states")).json()

    shared_title = "Customer testimonial video edit"
    return {
        "mktg_id": projects["MKTG"]["id"],
        "ops_id": projects["OPS"]["id"],
        "eng_id": eng["id"],
        "corporate_portfolio_id": projects["MKTG"]["portfolio_id"],
        "mktg_task_id": next(t["id"] for t in mktg_tasks["items"] if t["title"] != shared_title),
        "mktg_shared_task_id": next(t["id"] for t in mktg_tasks["items"] if t["title"] == shared_title),
        "eng_task_id": eng_tasks["items"][0]["id"],
        "mktg_done_state_id": next(s["id"] for s in mktg_states if s["category"] == "done"),
    }
