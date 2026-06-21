from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from xinyi_platform.auth.dependencies import get_current_user

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="xinyi_platform/templates")


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(request, "account.html", {"current_user": user})
