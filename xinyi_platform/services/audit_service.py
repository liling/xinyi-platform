import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    async def push(
        session: AsyncSession,
        *,
        user_id: uuid.UUID | None,
        client_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        detail: dict[str, Any] | None,
        ip_address: str | None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            client_id=client_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            detail=detail,
            ip_address=ip_address,
        )
        session.add(log)
        await session.flush()
        return log

    @staticmethod
    async def query(
        session: AsyncSession,
        *,
        client_id: str | None = None,
        user_id: uuid.UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if client_id is not None:
            stmt = stmt.where(AuditLog.client_id == client_id)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if since is not None:
            stmt = stmt.where(AuditLog.created_at >= since)
        if until is not None:
            stmt = stmt.where(AuditLog.created_at <= until)
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())
