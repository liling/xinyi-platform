from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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
