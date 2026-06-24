import uuid
from urllib.parse import urlencode, quote

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.session import decode_access_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.services.oauth_service import OAuthService

router = APIRouter(prefix="/oauth", tags=["oauth"])

SELF_AUDIENCE = "xinyi-platform-self"


async def get_business_client_by_id(session: AsyncSession, client_id: str) -> BusinessClient | None:
    result = await session.execute(
        select(BusinessClient).where(BusinessClient.client_id == client_id)
    )
    return result.scalar_one_or_none()


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    state: str = Query(""),
    return_to: str = Query(""),
    session: AsyncSession = Depends(get_session),
):
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only response_type=code supported")

    client = await get_business_client_by_id(session, client_id)
    if client is None or client.status != ClientStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Invalid client_id")

    if redirect_uri not in (client.redirect_uris or []):
        raise HTTPException(status_code=400, detail="redirect_uri not allowed")

    settings = Settings()
    cookie_token = request.cookies.get("xinyi_session")
    if not cookie_token:
        come_back = request.url.path + "?" + request.url.query
        login_url = f"/xinyi/login?return_to={quote(come_back)}"
        return RedirectResponse(url=login_url, status_code=303)

    from jose import JWTError
    try:
        payload = decode_access_token(cookie_token, settings.jwt_secret, audience=SELF_AUDIENCE)
    except JWTError:
        return RedirectResponse(url="/xinyi/login", status_code=303)

    user_id = uuid.UUID(payload["sub"])
    code = await OAuthService.generate_code(
        session,
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scope=None,
        ttl_seconds=settings.oauth_code_ttl_seconds,
    )
    await session.commit()

    params = {"code": code}
    if state:
        params["state"] = state
    if return_to:
        params["return_to"] = return_to
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{urlencode(params)}", status_code=303)


@router.post("/token")
async def token(
    request: Request,
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    settings = Settings()
    grant_type = body.get("grant_type")

    if grant_type == "authorization_code":
        result = await OAuthService.exchange_code(
            session,
            code=body["code"],
            client_id=body["client_id"],
            client_secret=body["client_secret"],
            redirect_uri=body["redirect_uri"],
            settings=settings,
        )
    elif grant_type == "refresh_token":
        result = await OAuthService.refresh(
            session,
            refresh_token_raw=body["refresh_token"],
            client_id=body["client_id"],
            client_secret=body["client_secret"],
            settings=settings,
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    if result is None:
        raise HTTPException(status_code=401, detail="Invalid grant")

    await session.commit()
    return {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "token_type": "Bearer",
        "expires_in": result.expires_in,
        "user": result.user_info,
    }


@router.post("/revoke")
async def revoke(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    token = body.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    await OAuthService.revoke_refresh_token(session, token)
    await session.commit()
    return {"ok": True}
