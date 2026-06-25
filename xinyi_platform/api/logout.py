import uuid
from pathlib import Path

from fastapi import APIRouter, Cookie, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

from xinyi_platform.config import Settings
from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.services.oauth_service import OAuthService

router = APIRouter(tags=["auth"])


async def _render_slo_page(request: Request, return_to: str) -> HTMLResponse:
    settings = Settings()
    cookie_token = request.cookies.get("xinyi_session")
    user_id = None
    if cookie_token:
        from jose import JWTError
        from xinyi_platform.auth.session import decode_access_token
        try:
            payload = decode_access_token(cookie_token, settings.jwt_secret, audience="xinyi-platform-self")
            user_id = payload.get("sub")
        except JWTError:
            pass

    logout_urls = []
    if user_id:
        from xinyi_platform.main import app_state
        factory = getattr(app_state, "session_factory", None)
        if factory is not None:
            async with factory() as session:
                await OAuthService.revoke_all_for_user(session, uuid.UUID(user_id), reason="user_logout")
                await session.commit()

                result = await session.execute(
                    select(BusinessClient).where(
                        BusinessClient.logout_url.isnot(None),
                        BusinessClient.status == ClientStatus.ACTIVE,
                    )
                )
                logout_urls = [
                    f"{c.base_url}{c.logout_url}"
                    for c in result.scalars().all()
                    if c.logout_url and c.base_url
                ]

    jinja = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")))
    html = jinja.get_template("logout.html").render(
        logout_urls=logout_urls,
        return_to=return_to,
    )
    resp = HTMLResponse(html)
    resp.delete_cookie("xinyi_session", path="/")
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    return_to: str = Form("/login"),
):
    return await _render_slo_page(request, return_to)


@router.get("/logout")
async def logout_get(
    request: Request,
    return_to: str = Query("/login"),
):
    return await _render_slo_page(request, return_to)
