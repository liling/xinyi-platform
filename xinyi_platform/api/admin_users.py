import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.dependencies import get_current_user, require_admin
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.models.user import AuthProvider, User, UserRole
from xinyi_platform.services.user_service import UsernameConflictError, UserService

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_admin)])
templates = make_templates()


def _ui_ctx(request):
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "products": ui["products"],
        "platform_url": ui["platform_url"],
        "manager_url": ui["manager_url"],
        "service_prefix": ui.get("service_prefix", ""),
    }


@router.get("", response_class=HTMLResponse)
async def list_users(
    request: Request,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(User).order_by(User.created_at.desc()).limit(size).offset((page - 1) * size)
    result = await session.execute(stmt)
    users = result.scalars().all()
    return templates.TemplateResponse(
        request, "admin/users.html",
        {**_ui_ctx(request), "current_user": current_user, "users": users, "page": page, "size": size},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_user_form(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "admin/user_form.html",
        {**_ui_ctx(request), "current_user": current_user, "user": None},
    )


@router.post("")
async def create_user(
    request: Request,
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await UserService.create_user(
            session,
            username=body["username"],
            password=body["password"],
            email=body.get("email"),
            display_name=body.get("display_name", body["username"]),
            provider=AuthProvider.LOCAL,
            role=UserRole.ADMIN if body.get("role") == "admin" else UserRole.USER,
        )
        await session.commit()
    except UsernameConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": str(user.id), "username": user.username}


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
        {**_ui_ctx(request), "current_user": current_user, "user": user},
    )


@router.post("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    if "role" in body:
        user.role = UserRole.ADMIN if body["role"] == "admin" else UserRole.USER
    if "is_active" in body:
        user.is_active = bool(body["is_active"])
    if "display_name" in body:
        user.display_name = body["display_name"]
    await session.commit()
    return {"ok": True}


@router.post("/{user_id}/delete")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await UserService.soft_delete(session, user_id)
    await session.commit()
    return {"ok": True}
