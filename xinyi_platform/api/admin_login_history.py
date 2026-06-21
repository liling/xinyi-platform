from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.dependencies import require_admin
from xinyi_platform.db import get_session
from xinyi_platform.models.login_history import LoginHistory

router = APIRouter(prefix="/admin/login-history", tags=["admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="xinyi_platform/templates")


@router.get("", response_class=HTMLResponse)
async def list_login_history(
    request: Request,
    user_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(LoginHistory).order_by(LoginHistory.login_time.desc())
    if user_id is not None:
        stmt = stmt.where(LoginHistory.user_id == user_id)
    stmt = stmt.limit(size).offset((page - 1) * size)
    result = await session.execute(stmt)
    records = result.scalars().all()
    return templates.TemplateResponse(
        request, "admin/login_history.html",
        {"records": records, "user_id": user_id, "page": page, "size": size},
    )
