from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.cas import CASClient
from xinyi_platform.auth.request_util import get_client_ip
from xinyi_platform.auth.session import create_session_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.models.login_history import LoginHistory
from xinyi_platform.models.user import AuthProvider, User
from xinyi_platform.services.oauth_service import OAuthService

router = APIRouter(prefix="/cas", tags=["auth"])


def _make_cas_client(settings: Settings) -> CASClient:
    return CASClient(settings.cas_server_url, settings.cas_service_url)


@router.get("/login")
async def cas_login():
    settings = Settings()
    if not settings.cas_server_url or not settings.cas_service_url:
        raise HTTPException(status_code=500, detail="CAS not configured")
    client = _make_cas_client(settings)
    return RedirectResponse(url=client.get_login_url())


@router.get("/callback")
async def cas_callback(
    ticket: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    settings = Settings()
    if not settings.cas_server_url or not settings.cas_service_url:
        raise HTTPException(status_code=500, detail="CAS not configured")
    client = _make_cas_client(settings)
    username = await client.verify_ticket(ticket)
    if not username:
        raise HTTPException(status_code=401, detail="CAS authentication failed")

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            username=username, display_name=username,
            auth_provider=AuthProvider.CAS,
        )
        session.add(user)
        await session.flush()
    user.last_login_at = datetime.now(timezone.utc)
    session.add(LoginHistory(
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        success=True,
    ))
    await OAuthService.clear_revocation(session, user.id)
    await session.commit()

    token = create_session_token(
        sub=str(user.id), username=user.username,
        role=user.role.value,
        secret=settings.jwt_secret, ttl_seconds=settings.session_expire_hours * 3600,
    )
    resp = RedirectResponse(url="/account", status_code=303)
    resp.set_cookie(
        "xinyi_session", token,
        httponly=True, max_age=settings.session_expire_hours * 3600,
        path="/", samesite="lax", secure=settings.session_secure,
    )
    return resp
