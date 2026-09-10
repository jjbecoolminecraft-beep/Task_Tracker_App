from __future__ import annotations

from datetime import datetime

import pytest
from app.core.errors import ValidationError
from app.core.pagination import MAX_LIMIT, Cursor, clamp_limit


def test_cursor_round_trips_scalar():
    c = Cursor(sort_value=3, last_id="abc")
    assert Cursor.decode(c.encode()) == c


def test_cursor_round_trips_datetime_as_iso():
    now = datetime(2026, 9, 10, 12, 30, 0)
    token = Cursor(sort_value=now, last_id="x").encode()
    restored = Cursor.decode(token)
    assert restored.sort_value == now.isoformat()


def test_malformed_cursor_is_a_validation_error():
    with pytest.raises(ValidationError):
        Cursor.decode("not-base64!!")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 50), (1, 1), (200, 200)],
)
def test_clamp_limit_accepts_valid(value, expected):
    assert clamp_limit(value) == expected


@pytest.mark.parametrize("value", [0, -1, MAX_LIMIT + 1, 10_000])
def test_clamp_limit_rejects_out_of_range(value):
    with pytest.raises(ValidationError):
        clamp_limit(value)
