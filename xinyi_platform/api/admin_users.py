import re
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.api._shared import build_template_context
from xinyi_platform.auth.dependencies import get_current_user, require_admin
from xinyi_platform.db import get_session
from xinyi_platform.middleware.csrf import verify_csrf_token
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.models.user import AuthProvider, User, UserRole
from xinyi_platform.services.user_service import UsernameConflictError, UserService

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_admin)])
templates = make_templates()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(email: str) -> str | None:
    """Return normalized email or None if empty; raise ValueError if malformed."""
    if not email:
        return None
    if not _EMAIL_RE.match(email):
        raise ValueError("邮箱格式不正确")
    return email


@router.get("", response_class=HTMLResponse)
async def list_users(
    request: Request,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.created_at.desc())
        .limit(size)
        .offset((page - 1) * size)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()
    return templates.TemplateResponse(
        request, "admin/users.html",
        {**build_template_context(request), "current_user": current_user, "users": users, "page": page, "size": size},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_user_form(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "admin/user_form.html",
        {**build_template_context(request), "current_user": current_user, "user": None},
    )


@router.post("")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    email: str = Form(""),
    role: str = Form("user"),
    current_user: dict = Depends(get_current_user),
    _csrf=Depends(verify_csrf_token),
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await UserService.create_user(
            session,
            username=username,
            password=password,
            email=_validate_email(email),
            display_name=display_name or username,
            provider=AuthProvider.LOCAL,
            role=UserRole.ADMIN if role == "admin" else UserRole.USER,
        )
        await session.commit()
    except (UsernameConflictError, ValueError) as e:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            {**build_template_context(request), "current_user": current_user, "error": str(e), "user": None},
            status_code=400,
        )
    return RedirectResponse(url="/xinyi/admin/users", status_code=303)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(
    request: Request,
    user_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/user_form.html",
        {**build_template_context(request), "current_user": current_user, "user": user},
    )


@router.post("/{user_id}")
async def update_user(
    request: Request,
    user_id: uuid.UUID,
    display_name: str = Form(""),
    email: str = Form(""),
    role: str = Form("user"),
    is_active: str = Form("false"),
    current_user: dict = Depends(get_current_user),
    _csrf=Depends(verify_csrf_token),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    try:
        normalized_email = _validate_email(email)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            {**build_template_context(request), "current_user": current_user, "error": str(e), "user": user},
            status_code=400,
        )
    user.role = UserRole.ADMIN if role == "admin" else UserRole.USER
    user.is_active = is_active.lower() in ("true", "1", "on")
    user.email = normalized_email
    if display_name:
        user.display_name = display_name
    await session.commit()
    return RedirectResponse(url="/xinyi/admin/users", status_code=303)


@router.post("/{user_id}/delete")
async def delete_user(
    user_id: uuid.UUID,
    _csrf=Depends(verify_csrf_token),
    session: AsyncSession = Depends(get_session),
):
    await UserService.soft_delete(session, user_id)
    await session.commit()
    return RedirectResponse(url="/xinyi/admin/users", status_code=303)
