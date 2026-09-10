"""Local development authentication stub (spec: docs/adr/0002).

These endpoints exist only while ``DEV_AUTH_ENABLED=true``. In production the SPA
runs the Entra ID authorization-code + PKCE flow via MSAL and this router is not
mounted.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.v1.deps import SessionDep
from app.core.auth import CurrentUser, mint_dev_token
from app.core.config import settings
from app.domain.enums import Role
from app.models.portfolio import Portfolio
from app.models.project import Project, ProjectMember
from app.models.role_grant import RoleGrant
from app.models.user import User
from app.schemas.auth import DevLoginRequest, DevUserOut, SessionInfo, SessionRole, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _guard_dev_auth() -> None:
    if not settings.dev_auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dev auth is disabled.")


@router.get("/dev-users", response_model=list[DevUserOut])
async def list_dev_users(session: SessionDep) -> list[DevUserOut]:
    """Seeded identities for the dev login screen, with a short role summary."""
    _guard_dev_auth()
    users = (
        (await session.execute(select(User).where(User.is_active.is_(True)).order_by(User.display_name)))
        .scalars()
        .all()
    )
    grants = (await session.execute(select(RoleGrant))).scalars().all()
    memberships = (await session.execute(select(ProjectMember))).scalars().all()

    by_user: dict[str, list[str]] = {}
    for g in grants:
        by_user.setdefault(str(g.user_id), []).append(g.role.replace("_", " "))
    for m in memberships:
        if m.user_id:
            by_user.setdefault(str(m.user_id), []).append(f"{m.role.replace('_', ' ')} (project)")

    out: list[DevUserOut] = []
    for u in users:
        row = DevUserOut.model_validate(u)
        row.roles_summary = sorted(set(by_user.get(str(u.id), []))) or ["no explicit roles"]
        out.append(row)
    return out


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(payload: DevLoginRequest, session: SessionDep) -> TokenResponse:
    _guard_dev_auth()
    user = await session.get(User, payload.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown dev user.")
    token = mint_dev_token(entra_object_id=user.entra_object_id, upn=user.upn, display_name=user.display_name)
    return TokenResponse(access_token=token, expires_in=settings.access_token_ttl_minutes * 60)


@router.get("/me", response_model=SessionInfo)
async def whoami(user: CurrentUser, session: SessionDep) -> SessionInfo:
    """Current identity and every role the caller holds, across all scopes."""
    info = SessionInfo.model_validate(user)

    grants = (await session.execute(select(RoleGrant).where(RoleGrant.user_id == user.id))).scalars().all()
    portfolios = {p.id: p.name for p in (await session.execute(select(Portfolio))).scalars().all()}
    for g in grants:
        info.roles.append(
            SessionRole(
                role=g.role,
                scope_type=g.scope_type,
                scope_id=g.scope_id,
                scope_label=portfolios.get(g.scope_id) if g.scope_id else None,
            )
        )

    memberships = (
        (await session.execute(select(ProjectMember).where(ProjectMember.user_id == user.id))).scalars().all()
    )
    project_names = {p.id: (p.key, p.name) for p in (await session.execute(select(Project))).scalars().all()}
    for m in memberships:
        key_name = project_names.get(m.project_id)
        info.roles.append(
            SessionRole(
                role=m.role,
                scope_type="project",
                scope_id=m.project_id,
                scope_label=f"{key_name[0]} — {key_name[1]}" if key_name else None,
            )
        )

    if not info.roles:
        info.roles.append(SessionRole(role=Role.GUEST.value, scope_type="none"))
    return info
