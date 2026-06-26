import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.internal_auth import verify_internal_client
from xinyi_platform.auth.session import hash_refresh_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session
from xinyi_platform.models.refresh_token import RefreshToken
from xinyi_platform.services.audit_service import AuditService
from xinyi_platform.services.email_service import EmailService
from xinyi_platform.services.oauth_service import OAuthService
from xinyi_platform.services.user_service import UserService

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(verify_internal_client)])


@router.post("/users/batch-get")
async def batch_get_users(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    ids = body.get("ids", [])
    if len(ids) > 100:
        raise HTTPException(status_code=400, detail="Up to 100 ids per call")
    uuids = [uuid.UUID(s) for s in ids]
    fields = body.get("fields")
    result = await UserService.batch_get(session, uuids, fields=fields)
    return {"users": {str(k): v for k, v in result.items()}}


@router.get("/users/search")
async def search_users(
    q: str = "",
    session: AsyncSession = Depends(get_session),
):
    if not q.strip():
        return {"users": []}
    results = await UserService.search(session, q.strip(), limit=20)
    return {"users": results}


@router.get("/users/{user_id}")
async def get_user(
    user_id: uuid.UUID = Path(...),
    session: AsyncSession = Depends(get_session),
):
    user = await UserService.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id), "username": user.username,
        "display_name": user.display_name, "email": user.email,
        "role": user.role.value, "is_active": user.is_active,
    }


@router.get("/users/by-username/{username}")
async def get_user_by_username(
    username: str = Path(...),
    session: AsyncSession = Depends(get_session),
):
    user = await UserService.get_by_username(session, username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id), "username": user.username,
        "display_name": user.display_name, "email": user.email,
        "role": user.role.value, "is_active": user.is_active,
    }


@router.post("/audit", status_code=202)
async def push_audit(
    body: dict = Body(...),
    background_tasks: BackgroundTasks = ...,  # noqa: B008
):
    user_id_str = body.get("user_id")
    user_id = uuid.UUID(user_id_str) if user_id_str else None
    occurred_at_str = body.get("occurred_at")
    occurred_at = datetime.fromisoformat(occurred_at_str) if occurred_at_str else None

    detail = body.get("detail") or {}
    if occurred_at:
        detail = {**detail, "occurred_at": occurred_at.isoformat()}

    background_tasks.add_task(
        AuditService.push_safe_from_kwargs,
        user_id=user_id,
        client_id=body.get("client_id"),
        action=body["action"],
        resource_type=body["resource_type"],
        resource_id=str(body["resource_id"]),
        detail=detail,
        ip_address=body.get("ip_address"),
    )
    return {"status": "accepted"}


@router.post("/notifications/email", status_code=202)
async def send_email(body: dict = Body(...)):
    settings = Settings()
    await EmailService.send_safe(
        settings,
        to=body["to"],
        subject=body["subject"],
        body=body["body"],
        html=body.get("html"),
    )
    return {"status": "accepted"}


@router.post("/auth/check-revocation")
async def check_revocation(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    user_id = uuid.UUID(body["user_id"])
    revoked = await OAuthService.is_user_revoked(session, user_id)
    return {"revoked": revoked}


@router.post("/auth/revoke")
async def revoke_user_session(
    body: dict = Body(...),
    session: AsyncSession = Depends(get_session),
):
    user_id_raw = body.get("user_id")
    refresh_token = body.get("refresh_token")

    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt is not None:
            await OAuthService.revoke_all_for_user(session, rt.user_id, reason="user_logout")
            await session.commit()
    elif user_id_raw:
        uid = uuid.UUID(user_id_raw)
        await OAuthService.revoke_all_for_user(session, uid, reason="user_logout")
        await session.commit()

    return {"ok": True}
