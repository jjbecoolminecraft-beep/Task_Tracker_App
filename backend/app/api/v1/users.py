"""User directory — read-only, for assignee/mention pickers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import SessionDep
from app.core.auth import CurrentUser
from app.repositories.users import UserRepository
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(session: SessionDep, _: CurrentUser) -> list[UserOut]:
    users = await UserRepository(session).list_active()
    return [UserOut.model_validate(u) for u in users]
