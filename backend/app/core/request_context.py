"""Per-request context, propagated through logs and audit events.

Spec §5.2: every response carries ``X-Request-Id``; §7.4: correlation IDs on
every structured log line.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_actor_id: ContextVar[str | None] = ContextVar("actor_id", default=None)


def new_request_id() -> str:
    return str(uuid.uuid4())


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def set_actor_id(value: str | None) -> None:
    _actor_id.set(value)


def get_actor_id() -> str | None:
    return _actor_id.get()
