from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from xinyi_platform.auth.dependencies import get_current_user
from xinyi_platform.jinja_env import make_templates

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
async def account_page(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(
        request, "account.html",
        {**_ui_ctx(request), "current_user": user},
    )
