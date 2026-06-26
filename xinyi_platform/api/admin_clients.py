from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.api._shared import build_template_context
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


def _serialize_client(c: BusinessClient) -> dict:
    return {
        "client_id": c.client_id,
        "name": c.name,
        "description": c.description,
        "redirect_uris": c.redirect_uris,
        "logout_url": c.logout_url,
        "base_url": c.base_url,
        "home_path": c.home_path,
        "status": c.status.value,
    }


@router.get("", response_class=HTMLResponse)
async def list_clients(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(BusinessClient).order_by(BusinessClient.created_at.desc()))
    clients = [_serialize_client(c) for c in result.scalars().all()]
    return templates.TemplateResponse(
        request, "admin/clients.html",
        {**build_template_context(request), "current_user": current_user, "clients": clients},
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
            logout_url=body.get("logout_url"),
        )
        if body.get("base_url"):
            client.base_url = body["base_url"]
        if body.get("home_path"):
            client.home_path = body["home_path"]
        if body.get("description"):
            client.description = body["description"]
        await session.commit()
    except ClientConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": str(client.id),
        "client_id": client.client_id,
        "client_secret": raw_secret,
        "name": client.name,
        "redirect_uris": client.redirect_uris,
        "logout_url": client.logout_url,
        "base_url": getattr(client, "base_url", None),
        "home_path": getattr(client, "home_path", None),
        "description": getattr(client, "description", None),
    }


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(BusinessClient).where(BusinessClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if "logout_url" in body:
        client.logout_url = body["logout_url"]
    if "name" in body:
        client.name = body["name"]
    if "redirect_uris" in body:
        client.redirect_uris = body["redirect_uris"]
    if "base_url" in body:
        client.base_url = body["base_url"]
    if "home_path" in body:
        client.home_path = body["home_path"]
    if "description" in body:
        client.description = body["description"]
    await session.commit()
    return {
        "id": str(client.id),
        "client_id": client.client_id,
        "name": client.name,
        "redirect_uris": client.redirect_uris,
        "logout_url": client.logout_url,
        "base_url": client.base_url,
        "home_path": client.home_path,
        "description": client.description,
    }


@router.post("/{client_id}/disable")
async def disable_client(
    client_id: str,
    session: AsyncSession = Depends(get_session),
):
    await BusinessClientService.set_status(session, client_id, ClientStatus.DISABLED)
    await session.commit()
    return RedirectResponse(url="/xinyi/admin/clients", status_code=303)


@router.post("/{client_id}/enable")
async def enable_client(
    client_id: str,
    session: AsyncSession = Depends(get_session),
):
    await BusinessClientService.set_status(session, client_id, ClientStatus.ACTIVE)
    await session.commit()
    return RedirectResponse(url="/xinyi/admin/clients", status_code=303)
