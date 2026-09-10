"""CSV / JSON export and CSV import for a project's tasks (spec F-12)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.api.v1.deps import AuthZDep, SessionDep
from app.core.auth import CurrentUser
from app.core.errors import ValidationError
from app.schemas.import_export import ImportResult
from app.services.import_export import ImportExportService

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["import-export"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB


def _service(session: SessionDep, authz: AuthZDep) -> ImportExportService:
    return ImportExportService(session, authz)


ServiceDep = Annotated[ImportExportService, Depends(_service)]


@router.get("/export")
async def export_tasks(
    project_id: uuid.UUID,
    service: ServiceDep,
    user: CurrentUser,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
) -> Response:
    content, media_type, filename = await service.export(project_id, fmt=format, actor=user)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportResult)
async def import_tasks(
    project_id: uuid.UUID,
    service: ServiceDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="UTF-8 CSV with a `title` column")],
) -> ImportResult:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationError("File exceeds the 2 MB import limit.")
    return await service.import_csv(project_id, content=raw, actor=user)
