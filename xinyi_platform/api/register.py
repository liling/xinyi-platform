from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.api._shared import build_template_context
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.middleware.rate_limit import register_limiter
from xinyi_platform.models.user import AuthProvider
from xinyi_platform.services.user_service import UsernameConflictError, UserService

router = APIRouter(tags=["auth"])
templates = make_templates()


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", build_template_context(request))


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    display_name: str = Form(...),
    _limiter=Depends(register_limiter),
    session: AsyncSession = Depends(get_session),
):
    try:
        await UserService.create_user(
            session,
            username=username,
            password=password,
            email=email,
            display_name=display_name,
            provider=AuthProvider.LOCAL,
        )
        await session.commit()
    except UsernameConflictError:
        return templates.TemplateResponse(
            request, "register.html",
            {**build_template_context(request), "error": "用户名已存在"}, status_code=200,
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request, "register.html",
            {**build_template_context(request), "error": str(e)}, status_code=200,
        )
    return RedirectResponse(url="/login?registered=1", status_code=303)
