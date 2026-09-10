"""Direct unit tests of the AuthZ policy layer (spec §7.2)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import AuthorizationError
from app.domain.enums import Action, Role
from app.models.project import Project
from app.models.user import User
from app.services.authorization import AuthZ


async def _user(session, upn_prefix: str) -> User:
    return (
        await session.execute(select(User).where(User.upn.like(f"{upn_prefix}@%")))
    ).scalar_one()


async def _project(session, key: str) -> Project:
    return (await session.execute(select(Project).where(Project.key == key))).scalar_one()


async def test_system_admin_cannot_read_task_content():
    async with session_scope() as s:
        anna = await _user(s, "anna.weber")
        mktg = await _project(s, "MKTG")
        authz = AuthZ(s, anna)
        assert await authz.has_global_role(Role.SYSTEM_ADMIN) is True
        with pytest.raises(AuthorizationError):
            await authz.require(Action.PROJECT_READ, mktg)


async def test_portfolio_owner_acts_as_project_admin_within_the_portfolio():
    async with session_scope() as s:
        clara = await _user(s, "clara.schmidt")
        mktg = await _project(s, "MKTG")  # in the Corporate portfolio Clara owns
        eng = await _project(s, "ENG")  # a different portfolio
        authz = AuthZ(s, clara)
        assert await authz.effective_project_role(mktg) == Role.PROJECT_ADMIN
        assert await authz.effective_project_role(eng) is None


async def test_internal_visibility_grants_implicit_viewer():
    async with session_scope() as s:
        hugo = await _user(s, "hugo.bauer")  # no explicit roles anywhere
        ops = await _project(s, "OPS")  # visibility = internal
        mktg = await _project(s, "MKTG")  # visibility = private
        authz = AuthZ(s, hugo)
        assert await authz.effective_project_role(ops) == Role.VIEWER
        assert await authz.effective_project_role(mktg) is None
        assert ops.id in await authz.accessible_project_ids()
        assert mktg.id not in await authz.accessible_project_ids()


async def test_contributor_can_write_but_not_administer():
    async with session_scope() as s:
        elena = await _user(s, "elena.popova")  # Contributor on MKTG
        mktg = await _project(s, "MKTG")
        authz = AuthZ(s, elena)
        assert await authz.require(Action.TASK_CREATE, mktg) is not None
        with pytest.raises(AuthorizationError):
            await authz.require(Action.PROJECT_UPDATE, mktg)


async def test_auditor_reads_audit_only():
    async with session_scope() as s:
        bjoern = await _user(s, "bjoern.neumann")
        mktg = await _project(s, "MKTG")
        authz = AuthZ(s, bjoern)
        await authz.require(Action.AUDIT_READ)  # no raise
        with pytest.raises(AuthorizationError):
            await authz.require(Action.PROJECT_READ, mktg)
