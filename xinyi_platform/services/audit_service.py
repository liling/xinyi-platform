import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xinyi_platform.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


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
    async def push_safe(
        session_factory: async_sessionmaker[AsyncSession],
        *,
        user_id: uuid.UUID | None,
        client_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        detail: dict[str, Any] | None,
        ip_address: str | None,
    ) -> None:
        """Best-effort audit write. Logs failures but never raises."""
        try:
            async with session_factory() as session:
                await AuditService.push(
                    session,
                    user_id=user_id,
                    client_id=client_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    detail=detail,
                    ip_address=ip_address,
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to write audit log: action=%s resource_type=%s",
                action,
                resource_type,
            )

    @staticmethod
    async def push_safe_from_kwargs(
        *,
        user_id: uuid.UUID | None,
        client_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Best-effort audit write using the global session factory.

        Suitable for use from BackgroundTasks (no Request, no session_factory).
        """
        from xinyi_platform.db import get_session_factory

        factory = get_session_factory()
        if factory is None:
            logger.warning("Audit skipped: session factory not initialized")
            return
        await AuditService.push_safe(
            factory,
            user_id=user_id,
            client_id=client_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            detail=detail,
            ip_address=ip_address,
        )

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
