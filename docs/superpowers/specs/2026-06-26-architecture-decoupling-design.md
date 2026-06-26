# Architecture Decoupling Design

**Date:** 2026-06-26  
**Scope:** P1 architecture improvements — `app_state` decoupling, async audit logging, Dockerfile migration separation  
**Status:** Approved for implementation

## Context

The P0 security and design fixes have landed. This spec addresses the next tier of P1 architectural issues:

1. Global `app_state` creates implicit circular imports and makes unit testing hard.
2. Audit logging writes synchronously on the request path, blocking responses on DB failures.
3. The Dockerfile runs database migrations at container startup, causing race conditions when multiple pods start simultaneously.

## Goals

- Remove all `from xinyi_platform.main import app_state` imports.
- Make session factory access explicit and test-friendly.
- Move audit writes off the critical request path without adding new infrastructure.
- Separate migrations from the application container startup.

## Non-Goals

- Introducing a DI container library.
- Adding Redis, message queues, or external workers.
- Refactoring unrelated code.

## Design

### 1. `app_state` Decoupling

#### Current State

- `xinyi_platform/db.py` imports `app_state` from `main` to obtain `session_factory`.
- `xinyi_platform/api/logout.py` imports `app_state` from `main`.
- `xinyi_platform/auth/audit.py` reads `request.app.state.session_factory` (already OK) but still has no clean fallback.

#### Proposed Change

Introduce an explicit module-level session factory in `xinyi_platform/db.py`:

```python
# xinyi_platform/db.py
_session_factory: async_sessionmaker | None = None

def set_session_factory(factory: async_sessionmaker) -> None:
    global _session_factory
    _session_factory = factory

async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("session_factory not set")
    async with _session_factory() as session:
        yield session

async def get_session_or_none() -> AsyncIterator[AsyncSession | None]:
    if _session_factory is None:
        yield None
        return
    async with _session_factory() as session:
        yield session
```

`lifespan` in `main.py` calls `set_session_factory(session_factory)` after creating the engine and session factory.

`logout.py` and `auth/audit.py` stop importing `app_state`. They use `request.app.state.session_factory` when a request is available, and `get_session_or_none()` as the FastAPI dependency.

#### Error Handling

- `get_session()` raises `RuntimeError` if the factory is not set.
- `get_session_or_none()` yields `None` for standalone test apps or commands that do not need a DB.
- Callers that receive `None` skip DB-dependent work gracefully.

### 2. Async Audit Logging

#### Current State

- `xinyi_platform/auth/audit.py:record_audit()` is already async, but it opens a DB session and commits on the request path; failures propagate to the caller.
- `xinyi_platform/api/internal.py` `/internal/audit` endpoint waits for the audit write before returning.

#### Proposed Change

1. Keep `AuditService.push()` signature unchanged.
2. Add `AuditService.push_safe(session_factory, **kwargs)` that wraps the write in `try/except` and logs failures.
3. Update `/internal/audit` to accept `BackgroundTasks` and schedule the write:

```python
@router.post("/audit", status_code=202)
async def push_audit(
    body: dict = Body(...),
    background: BackgroundTasks = Depends(),
):
    background.add_task(_push_audit_async, body)
    return {"status": "accepted"}
```

4. Update `record_audit()` to schedule its work via `BackgroundTasks` when available, or use `push_safe` directly; swallow exceptions either way.

#### Error Handling

- Background task failures are logged but do not fail the HTTP response.
- Audit data loss is acceptable for this iteration because the failure is still recorded in application logs.

### 3. Dockerfile Migration Separation

#### Current State

`Dockerfile` runs `uv run alembic upgrade head` before starting uvicorn in the same container command.

#### Proposed Change

1. Change `Dockerfile` CMD to only start the application:

```dockerfile
CMD ["sh", "-c", "uv run uvicorn xinyi_platform.main:app --host 0.0.0.0 --port 8000"]
```

2. Add `docker-compose.migrate.yml` for one-off migrations:

```yaml
services:
  migrate:
    build: .
    command: uv run alembic upgrade head
    env_file: .env
```

3. Update `README.md` to document the deployment requirement that migrations must run before the app starts.

#### Error Handling

- Running the app against an unmigrated database results in errors at runtime. This is a deployment responsibility, not a code issue.
- The migration command remains the same in local development.

## Testing Plan

| Test | File | Purpose |
|---|---|---|
| `test_get_session_without_factory_raises` | `tests/unit/test_db.py` | Verify explicit error when factory is unset. |
| `test_get_session_or_none_without_factory_returns_none` | `tests/unit/test_db.py` | Verify graceful fallback path. |
| `test_logout_without_session_factory` | `tests/api/test_logout_api.py` | Ensure logout renders without crashing in standalone apps. |
| `test_audit_record_does_not_raise_on_db_failure` | `tests/unit/test_audit.py` | Verify audit failure does not propagate. |
| `test_internal_audit_uses_background_task` | `tests/api/test_internal_audit_api.py` | Verify `/internal/audit` schedules background task. |
| `test_health_check_does_not_require_db` | `tests/test_smoke.py` | Confirm health check works without lifespan DB connection. |
| Docker build | manual / CI | Verify `docker build .` succeeds. |

## Out of Scope

- P2 issues: missing foreign keys, password policy, refresh token grace period, unused `manager_url`, hard-coded template path.
- Production infrastructure beyond the provided Docker Compose example.

## Files to Modify

- `xinyi_platform/db.py`
- `xinyi_platform/main.py`
- `xinyi_platform/api/logout.py`
- `xinyi_platform/auth/audit.py`
- `xinyi_platform/api/internal.py`
- `xinyi_platform/services/audit_service.py`
- `Dockerfile`
- `docker-compose.migrate.yml` (new)
- `README.md`
- test files as listed above

## Acceptance Criteria

- [ ] `grep -r "from xinyi_platform.main import app_state" xinyi_platform/` returns no matches.
- [ ] All existing tests pass.
- [ ] New tests for decoupling, audit async, and DB-less health check pass.
- [ ] `docker build .` succeeds.
- [ ] `docker compose -f docker-compose.migrate.yml up` runs migrations successfully.
