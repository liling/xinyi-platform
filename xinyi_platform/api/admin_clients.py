from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.dependencies import get_current_user, require_admin
from xinyi_platform.db import get_session
from xinyi_platform.jinja_env import make_templates
from xinyi_platform.models.business_client import BusinessClient, ClientStatus
from xinyi_platform.services.business_client_service import (
    BusinessClientService,
    ClientConflictError,
)

router = APIRouter(prefix="/admin/clients", tags=["admin"], dependencies=[Depends(require_admin)])
templates = make_templates()


def _ui_ctx(request):
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "products": ui["products"],
        "platform_url": ui["platform_url"],
        "manager_url": ui["manager_url"],
    }


@router.get("", response_class=HTMLResponse)
async def list_clients(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(BusinessClient).order_by(BusinessClient.created_at.desc()))
    clients = result.scalars().all()
    return templates.TemplateResponse(
        request, "admin/clients.html",
        {**_ui_ctx(request), "current_user": current_user, "clients": clients},
    )


@router.post("")
async def register_client(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        client, raw_secret = await BusinessClientService.register(
            session,
            client_id=body["client_id"],
            name=body["name"],
            redirect_uris=body.get("redirect_uris", []),
        )
        await session.commit()
    except ClientConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": str(client.id),
        "client_id": client.client_id,
        "client_secret": raw_secret,
        "name": client.name,
        "redirect_uris": client.redirect_uris,
    }


@router.post("/{client_id}/disable")
async def disable_client(
    client_id: str,
    session: AsyncSession = Depends(get_session),
):
    await BusinessClientService.set_status(session, client_id, ClientStatus.DISABLED)
    await session.commit()
    return {"ok": True}


@router.post("/{client_id}/enable")
async def enable_client(
    client_id: str,
    session: AsyncSession = Depends(get_session),
):
    await BusinessClientService.set_status(session, client_id, ClientStatus.ACTIVE)
    await session.commit()
    return {"ok": True}
