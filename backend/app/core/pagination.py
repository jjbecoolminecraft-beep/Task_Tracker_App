"""Cursor (keyset) pagination (spec §5.2).

Offset pagination "degrades badly and is inconsistent under concurrent writes",
so every collection endpoint uses an opaque cursor that encodes the last row's
``(sort_value, id)``. The tuple ordering gives a stable total order even when the
sort column has ties.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core.errors import ValidationError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass(slots=True)
class Cursor:
    sort_value: Any
    last_id: str

    def encode(self) -> str:
        raw = json.dumps({"v": _jsonify(self.sort_value), "id": self.last_id}, separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Cursor:
        try:
            data = json.loads(base64.urlsafe_b64decode(token.encode()))
            return cls(sort_value=data["v"], last_id=str(data["id"]))
        except Exception as exc:  # noqa: BLE001 - any malformed cursor is a 422
            raise ValidationError("Malformed pagination cursor.") from exc


@dataclass(slots=True)
class Page:
    items: list[Any]
    next_cursor: str | None


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1 or limit > MAX_LIMIT:
        raise ValidationError(f"limit must be between 1 and {MAX_LIMIT}.")
    return limit


def _jsonify(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
