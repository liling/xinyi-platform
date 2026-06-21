from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.dependencies import require_admin
from xinyi_platform.db import get_session
from xinyi_platform.services.audit_service import AuditService

router = APIRouter(prefix="/admin/audit-logs", tags=["admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="xinyi_platform/templates")


@router.get("", response_class=HTMLResponse)
async def list_audit_logs(
    request: Request,
    client_id: str | None = Query(None),
    user_id: UUID | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    logs = await AuditService.query(
        session,
        client_id=client_id,
        user_id=user_id,
        since=since,
        until=until,
        limit=size,
        offset=(page - 1) * size,
    )
    return templates.TemplateResponse(
        request, "admin/audit_logs.html",
        {"logs": logs, "client_id": client_id, "page": page, "size": size},
    )
