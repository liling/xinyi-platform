from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.api._shared import build_template_context
from xinyi_platform.auth.password import verify_password
from xinyi_platform.auth.request_util import get_client_ip
from xinyi_platform.auth.session import SELF_AUDIENCE, create_access_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.middleware.rate_limit import login_limiter
from xinyi_platform.models.login_history import LoginHistory
from xinyi_platform.models.user import User
from xinyi_platform.services.oauth_service import OAuthService

router = APIRouter(tags=["auth"])

templates = make_templates()


def _set_session_cookie(response, token: str, settings: Settings) -> None:
    response.set_cookie(
        "xinyi_session",
        token,
        httponly=True,
        max_age=settings.session_expire_hours * 3600,
        path="/",
        samesite="lax",
        secure=settings.session_secure,
    )


async def _record_failed_login(session: AsyncSession, request: Request, user: User | None, reason: str):
    """记录失败的登录尝试到 LoginHistory"""
    session.add(LoginHistory(
        user_id=user.id if user else None,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        success=False,
        failure_reason=reason,
    ))
    await session.commit()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, return_to: str | None = Query(default=None)):
    return templates.TemplateResponse(
        request, "login.html",
        {**build_template_context(request), "return_to": return_to or "/xinyi/account"},
    )


@router.post("/login")
async def login_json(
    request: Request,
    body: dict,
    _limiter=Depends(login_limiter),
    session: AsyncSession = Depends(get_session),
):
    settings = Settings()
    provider = body.get("provider", "local")
    if provider != "local":
        raise HTTPException(status_code=400, detail="Use /cas/login for CAS")
    username = body.get("username")
    password = body.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.password_hash or not verify_password(password, user.password_hash):
        reason = "user_not_found" if user is None else ("user_disabled" if not user.is_active else "invalid_credentials")
        await _record_failed_login(session, request, user, reason)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.last_login_at = datetime.now(timezone.utc)
    session.add(LoginHistory(
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        success=True,
    ))
    await OAuthService.clear_revocation(session, user.id)
    await session.commit()

    token = create_access_token(
        sub=str(user.id), username=user.username,
        role=user.role.value, client_id=SELF_AUDIENCE,
        secret=settings.jwt_secret, ttl_seconds=settings.session_expire_hours * 3600,
    )
    resp = JSONResponse(content={
        "token": token,
        "user": {
            "id": str(user.id), "username": user.username,
            "display_name": user.display_name, "auth_provider": user.auth_provider.value,
        },
    })
    _set_session_cookie(resp, token, settings)
    return resp


@router.post("/login/form")
async def login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    return_to: str = Form("/xinyi/account"),
    _limiter=Depends(login_limiter),
    session: AsyncSession = Depends(get_session),
):
    settings = Settings()
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.password_hash or not verify_password(password, user.password_hash):
        reason = "user_not_found" if user is None else ("user_disabled" if not user.is_active else "invalid_credentials")
        await _record_failed_login(session, request, user, reason)
        return templates.TemplateResponse(
            request, "login.html",
            {**build_template_context(request), "error": "用户名或密码错误", "return_to": return_to},
            status_code=200,
        )

    user.last_login_at = datetime.now(timezone.utc)
    session.add(LoginHistory(
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        success=True,
    ))
    await OAuthService.clear_revocation(session, user.id)
    await session.commit()

    token = create_access_token(
        sub=str(user.id), username=user.username,
        role=user.role.value, client_id=SELF_AUDIENCE,
        secret=settings.jwt_secret, ttl_seconds=settings.session_expire_hours * 3600,
    )
    resp = RedirectResponse(url=return_to, status_code=303)
    _set_session_cookie(resp, token, settings)
    return resp
