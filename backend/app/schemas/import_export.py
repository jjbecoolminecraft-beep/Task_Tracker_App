from __future__ import annotations

from pydantic import BaseModel


class ImportRowError(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    created: int
    refs: list[str] = []
    skipped: list[ImportRowError] = []
