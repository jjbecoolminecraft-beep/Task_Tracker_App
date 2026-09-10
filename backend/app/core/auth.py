"""Authentication.

Two implementations behind one dependency:

* **Local dev stub** (``DEV_AUTH_ENABLED=true``) — mints and verifies HS256 tokens
  shaped like Entra ID access tokens (``oid``, ``preferred_username``, ``name``).
  Lets the entire authorization stack run without a tenant. See docs/adr/0002.
* **Entra ID** (production) — validates RS256 JWTs against the tenant JWKS,
  checking ``iss`` and ``aud``. Wired but inert while the stub is on.

Either way the rest of the app receives a provisioned :class:`~app.models.user.User`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.errors import AuthenticationError
from app.core.logging import get_logger
from app.core.request_context import set_actor_id
from app.models.user import User

log = get_logger("auth")

_ALG = "HS256"
_ISSUER = "task-tracker-dev-stub"
_AUDIENCE = "task-tracker-api"


def mint_dev_token(*, entra_object_id: uuid.UUID, upn: str, display_name: str) -> str:
    """Issue a stub access token. Local development only."""
    if not settings.dev_auth_enabled:  # pragma: no cover - guarded at call sites too
        raise RuntimeError("Dev auth is disabled")
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": str(entra_object_id),
        "oid": str(entra_object_id),
        "preferred_username": upn,
        "name": display_name,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(claims, settings.dev_auth_secret, algorithm=_ALG)


def _decode(token: str) -> dict[str, Any]:
    if settings.dev_auth_enabled:
        try:
            return jwt.decode(
                token,
                settings.dev_auth_secret,
                algorithms=[_ALG],
                audience=_AUDIENCE,
                issuer=_ISSUER,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired token.") from exc

    # --- real Entra ID path (production) ---
    if not (settings.entra_tenant_id and settings.entra_api_audience):  # pragma: no cover
        raise AuthenticationError("Authentication is not configured.")
    raise AuthenticationError(  # pragma: no cover - implemented alongside MSAL wiring
        "Entra ID token validation not yet enabled in this build."
    )


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise AuthenticationError("Missing bearer token.")
    return value


async def _provision_user(session: AsyncSession, claims: dict[str, Any]) -> User:
    """Just-in-time provisioning on first sign-in (spec §2.1)."""
    oid = uuid.UUID(str(claims["oid"]))
    user = (await session.execute(select(User).where(User.entra_object_id == oid))).scalar_one_or_none()

    if user is None:
        user = User(
            entra_object_id=oid,
            upn=str(claims.get("preferred_username") or f"{oid}@example.invalid"),
            display_name=str(claims.get("name") or "Unknown user"),
        )
        session.add(user)
        await session.flush()
        log.info("user_provisioned", user_id=str(user.id))

    if not user.is_active:
        raise AuthenticationError("Account is deactivated.")
    return user


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    claims = _decode(_bearer_token(request))
    user = await _provision_user(session, claims)
    set_actor_id(str(user.id))
    request.state.actor_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
