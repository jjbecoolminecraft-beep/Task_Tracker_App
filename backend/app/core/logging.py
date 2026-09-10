"""Structured logging with a personal-data redaction filter.

Spec §7.4 / §12: "No personal data in logs. Enforced by a redaction filter with a
test that fails if the filter is bypassed." We log stable IDs, never names, email
addresses, UPNs, or task content.

The redaction runs as a structlog processor so it applies uniformly regardless of
which call site emitted the event.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from app.core.config import settings
from app.core.request_context import get_actor_id, get_request_id

# Keys whose values are free text or direct identifiers of a person.
_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "mail",
        "upn",
        "user_principal_name",
        "display_name",
        "name",
        "full_name",
        "given_name",
        "family_name",
        "title",
        "task_title",
        "description",
        "body",
        "content",
        "comment",
        "comment_body",
        "message_body",
        "attachment_name",
        "filename",
        "password",
        "secret",
        "token",
        "authorization",
    }
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_REDACTED = "«redacted»"


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return _EMAIL_RE.sub(_REDACTED, value)
    if isinstance(value, dict):
        return {k: _scrub_mapping_entry(k, v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_scrub_value(v) for v in value)
    return value


def _scrub_mapping_entry(key: str, value: Any) -> Any:
    if key.lower() in _REDACT_KEYS:
        return _REDACTED
    return _scrub_value(value)


def redact_personal_data(
    _logger: Any, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """structlog processor: drop/scrub anything that could be personal data."""
    return {key: _scrub_mapping_entry(key, value) for key, value in event_dict.items()}


def _bind_request_context(
    _logger: Any, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    request_id = get_request_id()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    actor_id = get_actor_id()
    if actor_id:
        event_dict.setdefault("actor_id", actor_id)
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "local"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _bind_request_context,
            redact_personal_data,  # must run last, after everything else has been added
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
