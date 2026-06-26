# Implementation Plan: P1 Architecture Decoupling

- **Author:** OpenCode agent
- **Date:** 2026-06-26
- **Status:** Draft
- **Scope:** xinyi-platform

## Goal

Decouple `app_state` from `db.py` and `auth/audit.py`, make audit logging failure-tolerant and non-blocking via FastAPI `BackgroundTasks`, and separate migration from runtime in the Dockerfile.

## Constraints

- No new infrastructure (Redis, queues, DI containers).
- Keep the change minimal but do not compress necessary rewrites.
- All existing tests (148) must pass after each step.
- No regressions in `/xinyi/health`, login flow, logout flow, or internal audit endpoint.

## Files

| File | What changes |
|------|--------------|
| `xinyi_platform/db.py` | Remove `main.app_state` import; add module-level `_session_factory` and `set_session_factory()`; `get_session()` and `get_session_or_none()` use local factory. |
| `xinyi_platform/main.py` | Lifespan calls `set_session_factory()` after creating the factory; keep `app_state.session_factory` as a temporary bridge. |
| `xinyi_platform/auth/audit.py` | Stop reading `request.app.state.session_factory`; accept an injected `session_factory`; add `record_audit_safe()` helper that swallows DB failures; optionally accept `BackgroundTasks` for async writes. |
| `xinyi_platform/services/audit_service.py` | Add `push_safe()` that opens its own session and never raises. |
| `xinyi_platform/api/internal.py` | `/internal/audit` returns 202 immediately and schedules `AuditService.push_safe()` via `BackgroundTasks`. |
| `xinyi_platform/api/logout.py` | Stop importing `main.app_state`; it already uses `get_session_or_none`. |
| `Dockerfile` | Remove `alembic upgrade head` from `CMD`; use `uvicorn` only. |
| `docker-compose.migrate.yml` | New file: one-off migration service using the same image. |
| `README.md` | Document migration deployment step and the optional init-container flow. |
| `tests/auth/test_audit.py` | Update existing tests or add new ones for `record_audit_safe()` and `BackgroundTasks` behavior. |
| `tests/api/test_internal_audit_api.py` | Update tests to expect `BackgroundTasks` scheduling instead of direct `AuditService.push`. |

## Plan

### Task 1: Decouple session factory from `app_state`

**Goal:** Remove `from xinyi_platform.main import app_state` from `xinyi_platform/db.py`.

**Steps:**

1. Open `xinyi_platform/db.py`.
2. Add module-level state after imports:

```python
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    global _session_factory
    _session_factory = factory
```

3. Rewrite `get_session()` and `get_session_or_none()` to use `_session_factory`:

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Override via dependency_overrides in tests."""
    if _session_factory is None:
        raise RuntimeError("Database session factory has not been initialized")
    async with _session_factory() as session:
        yield session


async def get_session_or_none() -> AsyncIterator[AsyncSession | None]:
    """Like get_session but returns None when the DB is not available."""
    if _session_factory is None:
        yield None
        return
    try:
        async with _session_factory() as session:
            yield session
    except Exception:
        yield None
```

4. Open `xinyi_platform/main.py`.
5. In the `lifespan` function, after `app_state.session_factory = create_session_factory(app_state.engine)`, add:

```python
from xinyi_platform.db import set_session_factory
set_session_factory(app_state.session_factory)
```

(Place the import at the top of the function or at module level; module-level is fine since `db.py` no longer imports `main.py`.)

6. Run tests:

```bash
uv run pytest tests/test_smoke.py tests/api/test_internal_audit_api.py -v
```

**Expected output:**

```
tests/test_smoke.py::test_health PASSED
tests/api/test_internal_audit_api.py::test_push_event_accepted PASSED
tests/api/test_internal_audit_api.py::test_push_event_user_null_ok PASSED
```

**Self-review checkpoint:**

- [ ] `db.py` no longer imports anything from `main.py`.
- [ ] `main.py` calls `set_session_factory()` exactly once during lifespan startup.
- [ ] Smoke tests and audit API tests pass.

---

### Task 2: Make audit service failure-tolerant

**Goal:** Audit writes must not propagate exceptions to request handlers.

**Steps:**

1. Open `xinyi_platform/services/audit_service.py`.
2. Add a logger import and a `push_safe()` method:

```python
import logging

logger = logging.getLogger(__name__)
```

3. Add `push_safe` inside `AuditService`:

```python
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
            logger.exception("Failed to write audit log: action=%s resource_type=%s", action, resource_type)
```

4. Add the import for `async_sessionmaker` at the top:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
```

5. Run tests:

```bash
uv run pytest tests/api/test_internal_audit_api.py -v
```

**Expected output:**

```
tests/api/test_internal_audit_api.py::test_push_event_accepted PASSED
tests/api/test_internal_audit_api.py::test_push_event_user_null_ok PASSED
```

**Self-review checkpoint:**

- [ ] `AuditService.push_safe` accepts a `session_factory` callable, not an open session.
- [ ] All exceptions are caught and logged.
- [ ] No return value is required.

---

### Task 3: Make `record_audit` async and failure-tolerant

**Goal:** Update `xinyi_platform/auth/audit.py` to use the decoupled session factory and support background tasks.

**Steps:**

1. Open `xinyi_platform/auth/audit.py`.
2. Rewrite the file as follows:

```python
import logging
import uuid
from collections.abc import Awaitable
from typing import Any, Callable

from fastapi import BackgroundTasks, Request

from xinyi_platform.db import _session_factory

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

    If background_tasks is provided, the write is scheduled asynchronously.
    Otherwise the write is performed inline (still best-effort).
    """
    from xinyi_platform.services.audit_service import AuditService

    session_factory = _session_factory
    if session_factory is None:
        logger.warning("Audit skipped: session factory not initialized")
        return

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
        background_tasks.add_task(AuditService.push_safe, session_factory, **kwargs)
        return

    await AuditService.push_safe(session_factory, **kwargs)
```

3. If any callers of `record_audit` currently pass positional arguments, update them to pass keyword arguments. Search with:

```bash
rg "record_audit" --type py
```

4. Run tests for audit callers:

```bash
uv run pytest tests/auth/ -v
```

**Expected output:** All audit tests pass.

**Self-review checkpoint:**

- [ ] `auth/audit.py` no longer imports from `main.py`.
- [ ] It uses `_session_factory` from `xinyi_platform.db`.
- [ ] Background task scheduling returns immediately.
- [ ] Inline path is still failure-tolerant.

---

### Task 4: Convert `/internal/audit` to background tasks

**Goal:** The internal audit endpoint should return 202 without waiting for the DB write.

**Steps:**

1. Open `xinyi_platform/api/internal.py`.
2. Change the import from `fastapi import APIRouter, Body, Depends, HTTPException, Path` to include `BackgroundTasks`:

```python
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path
```

3. Rewrite `/internal/audit`:

```python
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

    from xinyi_platform.auth.audit import record_audit_safe_kwargs

    background_tasks.add_task(
        record_audit_safe_kwargs,
        user_id=user_id,
        client_id=body.get("client_id"),
        action=body["action"],
        resource_type=body["resource_type"],
        resource_id=str(body["resource_id"]),
        detail=detail,
        ip_address=body.get("ip_address"),
    )
    return {"status": "accepted"}
```

Wait — the above introduces `record_audit_safe_kwargs`. Two cleaner options:

**Option A (recommended):** Use `AuditService.push_safe` directly with `_session_factory`. But importing `_session_factory` into `internal.py` leaks module-level state.

**Option B:** Create a public helper `audit.record_audit_safe_kwargs()` that encapsulates `_session_factory`.

Let's use Option B. Add to `xinyi_platform/auth/audit.py`:

```python
async def record_audit_safe_kwargs(
    *,
    user_id: uuid.UUID | None,
    client_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Best-effort audit write from a background task (no request object)."""
    from xinyi_platform.services.audit_service import AuditService

    session_factory = _session_factory
    if session_factory is None:
        logger.warning("Audit skipped: session factory not initialized")
        return

    await AuditService.push_safe(
        session_factory,
        user_id=user_id,
        client_id=client_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        detail=detail,
        ip_address=ip_address,
    )
```

Then in `internal.py`:

```python
from xinyi_platform.auth.audit import record_audit_safe_kwargs
```

and use `background_tasks.add_task(record_audit_safe_kwargs, ...)`. Note that `add_task` accepts keyword arguments for the task function, so this is valid.

4. Update `tests/api/test_internal_audit_api.py`:

The current tests patch `AuditService.push`. With background tasks, the request returns before `push_safe` is executed. In a sync `TestClient`, background tasks are run after the response is generated. We can either:

- Patch `record_audit_safe_kwargs` and assert it was called once.
- Patch `AuditService.push_safe` and assert it was called once.

Choose patching `record_audit_safe_kwargs` because it is the entry point.

Update `test_push_event_accepted`:

```python
with patch(
    "xinyi_platform.api.internal.record_audit_safe_kwargs",
    new_callable=AsyncMock,
) as mock_record:
```

and add assertion `mock_record.assert_called_once()`.

Update `test_push_event_user_null_ok` similarly.

5. Run tests:

```bash
uv run pytest tests/api/test_internal_audit_api.py -v
```

**Expected output:**

```
tests/api/test_internal_audit_api.py::test_push_event_accepted PASSED
tests/api/test_internal_audit_api.py::test_push_event_user_null_ok PASSED
```

**Self-review checkpoint:**

- [ ] `/internal/audit` no longer depends on `get_session`.
- [ ] It returns 202 immediately.
- [ ] `record_audit_safe_kwargs` is scheduled as a background task.
- [ ] Tests patch the new entry point.

---

### Task 5: Remove runtime migration from Dockerfile

**Goal:** Prevent race conditions when multiple containers start simultaneously.

**Steps:**

1. Open `Dockerfile`.
2. Change the last line from:

```dockerfile
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn xinyi_platform.main:app --host 0.0.0.0 --port 8000"]
```

To:

```dockerfile
CMD ["uv", "run", "uvicorn", "xinyi_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. Create `docker-compose.migrate.yml`:

```yaml
services:
  migrate:
    build: .
    command: ["uv", "run", "alembic", "upgrade", "head"]
    environment:
      XINYI_PLATFORM_DATABASE_URL: ${XINYI_PLATFORM_DATABASE_URL}
      XINYI_PLATFORM_JWT_SECRET: ${XINYI_PLATFORM_JWT_SECRET}
      XINYI_PLATFORM_ADMIN_PASSWORD: ${XINYI_PLATFORM_ADMIN_PASSWORD}
    # Optional: run once and exit
    restart: "no"
```

4. Verify the Dockerfile builds:

```bash
docker build -t xinyi-platform:test .
```

**Expected output:** Image builds successfully.

5. Verify the migrate compose file is syntactically valid:

```bash
docker compose -f docker-compose.migrate.yml config
```

**Expected output:** Compose configuration printed without errors.

**Self-review checkpoint:**

- [ ] Dockerfile `CMD` only runs `uvicorn`.
- [ ] `docker-compose.migrate.yml` exists and uses the same image.
- [ ] Both `docker build` and `docker compose config` succeed.

---

### Task 6: Update README

**Goal:** Document the new migration deployment pattern.

**Steps:**

1. Open `README.md`.
2. After the Quick Start section, add a new section:

```markdown
## Deployment

### Database Migrations

Do not run migrations inside the application container startup. Instead, apply them as a one-off init-container or standalone job before rolling out the app:

```bash
# Local / compose
docker compose -f docker-compose.migrate.yml run --rm migrate

# Kubernetes example
kubectl create job xinyi-migrate --from=cronjob/xinyi-migrate
```

The application Dockerfile only starts the HTTP server. Running `alembic upgrade head` at container startup causes races when multiple pods start together.
```

3. Run the README through a markdown linter if available, otherwise verify rendering:

```bash
uv run pytest tests/test_smoke.py -v
```

**Self-review checkpoint:**

- [ ] README explains why migrations are separated.
- [ ] README provides concrete commands for local and Kubernetes usage.

---

### Task 7: Add audit failure-tolerance tests

**Goal:** Prove that audit failures do not break request handling.

**Steps:**

1. Create or open `tests/auth/test_audit.py`.
2. Add tests:

```python
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from xinyi_platform.auth.audit import record_audit, record_audit_safe_kwargs


@pytest.mark.asyncio
async def test_record_audit_swallows_push_failure():
    request = type("Request", (), {
        "client": type("Client", (), {"host": "127.0.0.1"})(),
        "app": type("App", (), {"state": type("State", (), {})()})(),
    })()

    with patch("xinyi_platform.auth.audit._session_factory", new=AsyncMock()) as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        await record_audit(
            request,
            user_id=uuid.uuid4(),
            client_id="hm",
            action="test.action",
            resource_type="test",
            resource_id="123",
        )


@pytest.mark.asyncio
async def test_record_audit_safe_kwargs_skips_when_factory_missing():
    with patch("xinyi_platform.auth.audit._session_factory", None):
        await record_audit_safe_kwargs(
            user_id=uuid.uuid4(),
            client_id="hm",
            action="test.action",
            resource_type="test",
            resource_id="123",
        )
```

3. Run tests:

```bash
uv run pytest tests/auth/test_audit.py -v
```

**Expected output:**

```
tests/auth/test_audit.py::test_record_audit_swallows_push_failure PASSED
tests/auth/test_audit.py::test_record_audit_safe_kwargs_skips_when_factory_missing PASSED
```

**Self-review checkpoint:**

- [ ] Test confirms `record_audit` does not raise when the DB is unavailable.
- [ ] Test confirms `record_audit_safe_kwargs` returns early when factory is missing.

---

### Task 8: Full regression test and cleanup

**Goal:** Ensure all changes work together and remove any unused imports.

**Steps:**

1. Run the full test suite:

```bash
uv run pytest -q
```

**Expected output:**

```
148 passed
```

2. Run type checks:

```bash
uv run mypy xinyi_platform
```

**Expected output:** `Success: no issues found in ... files`.

3. Run linting:

```bash
uv run ruff check xinyi_platform tests
```

**Expected output:** No errors.

4. Search for remaining `app_state` imports in non-test code:

```bash
rg "from xinyi_platform.main import app_state" --type py
```

**Expected output:** No matches (or only matches in `main.py` itself and tests).

5. Search for remaining `request.app.state.session_factory` usage:

```bash
rg "request\.app\.state\.session_factory" --type py
```

**Expected output:** No matches.

**Self-review checkpoint:**

- [ ] Full test suite passes.
- [ ] Type checker passes.
- [ ] Linter passes.
- [ ] No stray `app_state` usage outside `main.py`.

---

## Verification Commands

```bash
# Quick feedback loop
uv run pytest tests/test_smoke.py tests/api/test_internal_audit_api.py tests/auth/test_audit.py -v

# Full verification
uv run pytest -q
uv run mypy xinyi_platform
uv run ruff check xinyi_platform tests

# Docker verification
docker build -t xinyi-platform:test .
docker compose -f docker-compose.migrate.yml config
```

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Background task fails silently | `AuditService.push_safe` logs exceptions; consider a future metric/alert on log volume. |
| Init-container migration is forgotten | README now documents the pattern; future CI/CD should run migrate before deploy. |
| `_session_factory` module state is hard to test | Tests can patch `xinyi_platform.auth.audit._session_factory` directly. |
| Existing callers of `record_audit` not updated | Search with `rg` in Task 3; all callers must pass keyword args. |

## Out of Scope

- Replacing module-level `_session_factory` with a proper DI container.
- Adding Redis/queue for audit writes.
- Refactoring unrelated `app_state` usages (engine, scheduler, settings).
