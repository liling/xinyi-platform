import uuid
from typing import Any

from fastapi import Request


async def record_audit(
    request: Request,
    *,
    user_id: uuid.UUID | None,
    client_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Best-effort audit push. Caller owns session lifecycle."""
    from xinyi_platform.services.audit_service import AuditService
    session_factory = request.app.state.session_factory
    ip = request.client.host if request.client else None
    async with session_factory() as session:
        await AuditService.push(
            session,
            user_id=user_id,
            client_id=client_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip,
        )
        await session.commit()
