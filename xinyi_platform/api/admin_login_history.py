from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.api._shared import build_template_context
from xinyi_platform.auth.dependencies import get_current_user, require_admin
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.models.login_history import LoginHistory
from xinyi_platform.models.user import User

router = APIRouter(prefix="/admin/login-history", tags=["admin"], dependencies=[Depends(require_admin)])
templates = make_templates()


@router.get("", response_class=HTMLResponse)
async def list_login_history(
    request: Request,
    current_user: dict = Depends(get_current_user),
    user_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(LoginHistory, User)
        .outerjoin(User, LoginHistory.user_id == User.id)
        .order_by(LoginHistory.login_time.desc())
    )
    if user_id is not None:
        stmt = stmt.where(LoginHistory.user_id == user_id)
    stmt = stmt.limit(size).offset((page - 1) * size)
    result = await session.execute(stmt)
    rows = result.all()
    return templates.TemplateResponse(
        request, "admin/login_history.html",
        {**build_template_context(request), "current_user": current_user, "rows": rows, "user_id": user_id, "page": page, "size": size},
    )
