import logging
import uuid
from typing import Any

from fastapi import BackgroundTasks, Request

from xinyi_platform.db import get_session_factory
from xinyi_platform.services.audit_service import AuditService

logger = logging.getLogger(__name__)


async def record_audit(
    request: Request,
    *,
    user_id: uuid.UUID | None,
    client_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any] | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Best-effort audit push.

    If background_tasks is provided, the write is scheduled to happen
    asynchronously after the response is sent. Otherwise it runs inline.
    Either way, push failures are logged and never propagated.
    """
    ip = request.client.host if request.client else None
    kwargs = {
        "user_id": user_id,
        "client_id": client_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
        "detail": detail,
        "ip_address": ip,
    }

    if background_tasks is not None:
        background_tasks.add_task(
            AuditService.push_safe_from_kwargs,
            **kwargs,
        )
        return

    factory = get_session_factory()
    if factory is None:
        logger.warning("Audit skipped: session factory not initialized")
        return
    await AuditService.push_safe(factory, **kwargs)
