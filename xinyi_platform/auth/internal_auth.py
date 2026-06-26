import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.config import get_settings
from xinyi_platform.db import get_session
from xinyi_platform.models.business_client import BusinessClient
from xinyi_platform.services.business_client_service import BusinessClientService


async def verify_internal_client(
    x_client_id: str = Header(..., alias="X-Client-Id"),
    x_client_secret: str = Header(..., alias="X-Client-Secret"),
    session: AsyncSession = Depends(get_session),
) -> BusinessClient:
    client = await BusinessClientService.verify_secret(session, x_client_id, x_client_secret)
    if client is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client credentials")
    return client


async def verify_registration_token(
    x_registration_token: str = Header(..., alias="X-Registration-Token"),
) -> str:
    settings = get_settings()
    if not settings.registration_token:
        raise HTTPException(status_code=500, detail="Registration token not configured")
    if not secrets.compare_digest(x_registration_token, settings.registration_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid registration token")
    return x_registration_token
