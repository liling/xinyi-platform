import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.config import Settings
from xinyi_platform.db import get_session_or_none
from xinyi_platform.middleware.csrf import verify_csrf_token
from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.services.oauth_service import OAuthService

router = APIRouter(tags=["auth"])


async def _get_user_id_from_cookie(request: Request) -> str | None:
    settings = Settings()
    cookie_token = request.cookies.get("xinyi_session")
    if not cookie_token:
        return None
    from jose import JWTError
    from xinyi_platform.auth.session import decode_session_token
    try:
        payload = decode_session_token(cookie_token, settings.jwt_secret)
        return payload.get("sub")
    except JWTError:
        return None


async def _get_slo_urls(session: AsyncSession) -> list[str]:
    result = await session.execute(
        select(BusinessClient).where(
            BusinessClient.logout_url.isnot(None),
            BusinessClient.status == ClientStatus.ACTIVE,
        )
    )
    return [
        f"{c.base_url}{c.logout_url}"
        for c in result.scalars().all()
        if c.logout_url and c.base_url
    ]


def _render_logout_page(return_to: str, slo_urls: list[str]) -> HTMLResponse:
    jinja = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")))
    html = jinja.get_template("logout.html").render(
        logout_urls=slo_urls,
        return_to=return_to,
    )
    return HTMLResponse(html)


@router.get("/logout", response_class=HTMLResponse)
async def logout_get(
    request: Request,
    return_to: str = Query("/xinyi/login"),
    session: AsyncSession | None = Depends(get_session_or_none),
):
    slo_urls = []
    if session is not None:
        slo_urls = await _get_slo_urls(session)
    resp = _render_logout_page(return_to, slo_urls)
    resp.delete_cookie("xinyi_session", path="/")
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    return_to: str = Form("/xinyi/login"),
    _csrf=Depends(verify_csrf_token),
    session: AsyncSession | None = Depends(get_session_or_none),
):
    user_id_str = await _get_user_id_from_cookie(request)
    slo_urls = []
    if user_id_str and session is not None:
        await OAuthService.revoke_all_for_user(session, uuid.UUID(user_id_str), reason="user_logout")
        slo_urls = await _get_slo_urls(session)
        await session.commit()

    resp = _render_logout_page(return_to, slo_urls)
    resp.delete_cookie("xinyi_session", path="/")
    return resp
