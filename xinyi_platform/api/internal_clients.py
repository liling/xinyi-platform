import bcrypt

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.internal_auth import verify_internal_client, verify_registration_token
from xinyi_platform.config import get_settings
from xinyi_platform.db import get_session
from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.services.business_client_service import BusinessClientService
from xinyi_platform.ui_common.service_discovery import derive_client_secret

router = APIRouter(prefix="/internal/clients", tags=["internal"])


@router.post("/register")
async def register_client(
    body: dict = Body(...),
    _token: str = Depends(verify_registration_token),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    client_id = body["client_id"]

    secret = derive_client_secret(settings.registration_token, client_id)
    secret_hash = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")

    client = await BusinessClientService.register_or_update(
        session,
        client_id=client_id,
        name=body.get("name", client_id),
        client_secret_hash=secret_hash,
        redirect_uris=body.get("redirect_uris", []),
        logout_url=body.get("logout_url"),
        base_url=body.get("base_url"),
        home_path=body.get("home_path"),
        description=body.get("description"),
    )
    await session.commit()

    return {"status": "registered", "client_id": client.client_id}


@router.get("/active")
async def list_active_clients(
    _client: BusinessClient = Depends(verify_internal_client),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(BusinessClient).where(
            BusinessClient.status == ClientStatus.ACTIVE,
            BusinessClient.base_url.isnot(None),
        ).order_by(BusinessClient.name)
    )
    clients = result.scalars().all()

    return {
        "clients": [
            {
                "client_id": c.client_id,
                "name": c.name,
                "base_url": c.base_url,
                "home_path": c.home_path or "",
                "description": c.description or "",
                "logo_url": c.logo_url,
                "kind": "business",
            }
            for c in clients
        ]
    }
