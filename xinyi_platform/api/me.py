import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.dependencies import get_current_user
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.models.user import User

router = APIRouter(tags=["auth"])
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
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/account", response_class=HTMLResponse)
async def account_page(
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    db_user = await session.get(User, uuid.UUID(user["id"]))
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    full_user = {
        "id": str(db_user.id),
        "username": db_user.username,
        "role": db_user.role.value,
        "display_name": db_user.display_name,
        "email": db_user.email,
        "auth_provider": db_user.auth_provider.value,
        "is_active": db_user.is_active,
    }
    return templates.TemplateResponse(
        request, "account.html",
        {**_ui_ctx(request), "current_user": full_user},
    )
