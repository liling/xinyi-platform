import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.api._shared import build_template_context
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.middleware.rate_limit import password_reset_limiter
from xinyi_platform.models.email_verification import EmailVerification
from xinyi_platform.models.user import User
from xinyi_platform.services.email_service import EmailService
from xinyi_platform.services.user_service import UserService

router = APIRouter(prefix="/password", tags=["auth"])
templates = make_templates()

RESET_TTL_MINUTES = 30
RESET_MAX_ATTEMPTS = 5


@router.get("/forgot", response_class=HTMLResponse)
async def forgot_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html", build_template_context(request))


@router.post("/forgot")
async def forgot_submit(
    request: Request,
    email: str = Form(...),
    _limiter=Depends(password_reset_limiter),
    session: AsyncSession = Depends(get_session),
):
    settings = Settings()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        code = f"{secrets.randbelow(1000000):06d}"
        verification = EmailVerification(
            email=email, code=code, purpose="reset_password",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES),
        )
        session.add(verification)
        await session.commit()
        EmailService.send_safe(
            settings,
            to=[email],
            subject="密码重置",
            body=f"您的密码重置码是:{code},30 分钟内有效。",
        )
    return templates.TemplateResponse(
        request, "forgot_password.html",
        {**build_template_context(request), "info": "如果邮箱存在,重置码已发送"},
    )


@router.get("/reset", response_class=HTMLResponse)
async def reset_page(request: Request, email: str = "", code: str = ""):
    return templates.TemplateResponse(
        request, "reset_password.html",
        {**build_template_context(request), "email": email, "code": code},
    )


@router.post("/reset")
async def reset_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(EmailVerification).where(
            EmailVerification.email == email,
            EmailVerification.code == code,
            EmailVerification.purpose == "reset_password",
            EmailVerification.verified.is_(False),
        )
    )
    verification = result.scalar_one_or_none()
    if verification is None:
        return templates.TemplateResponse(
            request, "reset_password.html",
            {**build_template_context(request), "email": email, "error": "验证码无效"}, status_code=400,
        )

    if verification.expires_at < datetime.now(timezone.utc):
        return templates.TemplateResponse(
            request, "reset_password.html",
            {**build_template_context(request), "email": email, "error": "验证码已过期"}, status_code=400,
        )

    verification.attempts += 1
    if verification.attempts > RESET_MAX_ATTEMPTS:
        return templates.TemplateResponse(
            request, "reset_password.html",
            {**build_template_context(request), "email": email, "error": "尝试次数过多"}, status_code=400,
        )

    user_result = await session.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if user is None:
        return templates.TemplateResponse(
            request, "reset_password.html",
            {**build_template_context(request), "email": email, "error": "用户不存在"}, status_code=400,
        )

    try:
        await UserService.change_password(session, user.id, new_password)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "reset_password.html",
            {**build_template_context(request), "email": email, "error": str(e)}, status_code=400,
        )

    verification.verified = True
    await session.commit()
    return RedirectResponse(url="/login?reset=1", status_code=303)
