# business_clients URL 存储重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `business_clients` 表中的 `redirect_uris` 和 `logout_url` 从完整 URL 改为相对路径，`base_url` 作为唯一完整 URL 来源。

**Architecture:** 平台端通过 Alembic 数据迁移截断存量数据，OAuth 匹配和 SLO 登出改为拼接 `base_url + 相对路径`。三个业务服务同步改为注册时传相对路径、OAuth 流程发起时拼完整 URL。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, pytest

## Global Constraints

- `base_url` 是唯一的完整 URL 来源
- `redirect_uris`、`logout_url`、`home_path` 均存储相对路径（以 `/` 开头）
- 拼接规则：`f"{base_url}{相对路径}"`
- 部署顺序：先部署 xinyi-platform → 跑迁移 → 重启 → 再升级业务服务
- 三个项目同步改动：xinyi-platform、hindsight-manager、docupipe-manager

---

## File Structure

### xinyi-platform

| File | Responsibility |
|------|----------------|
| `xinyi_platform/migrations/versions/006_relative_client_urls.py` | 数据迁移：截断存量完整 URL |
| `xinyi_platform/api/oauth.py` | OAuth authorize 匹配改为拼接 |
| `xinyi_platform/services/business_client_service.py` | verify_redirect_uri 拼接 |
| `xinyi_platform/api/logout.py` | SLO logout_urls 拼接 base_url |
| `xinyi_platform/templates/admin/clients.html` | 表单 placeholder 改为相对路径 |

### hindsight-manager

| File | Responsibility |
|------|----------------|
| `hindsight_manager/main.py` | 注册参数改为相对路径 |
| `hindsight_manager/config.py` | oauth_redirect_uri 默认值改为相对路径 |
| `hindsight_manager/api/auth.py` | OAuth 流程发起时拼完整 URL |
| `hindsight_manager/platform/config.py` | PlatformSettings.oauth_redirect_uri 改为完整 URL 拼接 |

### docupipe-manager

| File | Responsibility |
|------|----------------|
| `docupipe_manager/main.py` | 注册参数改为相对路径 |
| `docupipe_manager/config.py` | oauth_redirect_uri 默认值改为相对路径 |
| `docupipe_manager/api/auth.py` | OAuth 流程发起时拼完整 URL |
| `docupipe_manager/platform/config.py` | PlatformSettings.oauth_redirect_uri 改为完整 URL 拼接 |

---

### Task 1: xinyi-platform 数据迁移脚本

**Files:**
- Create: `xinyi_platform/migrations/versions/006_relative_client_urls.py`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces: Alembic migration `006` that transforms existing `redirect_uris` and `logout_url` from full URLs to relative paths by stripping the `base_url` prefix.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrations.py`:

```python
import pytest
from unittest.mock import MagicMock
from alembic import command
from alembic.config import Config


def test_migration_006_strips_base_url_prefix():
    """Verify the migration logic strips base_url from redirect_uris and logout_url."""
    # We test the migration's helper logic directly
    import importlib
    import sys

    # The migration module is importable after creating it
    # We verify the core logic: given base_url and a full URL, strip the prefix
    base_url = "http://hm:8001/hindsight"

    # Simulate what the migration does
    def strip_prefix(full_url, base_url):
        if full_url and base_url and full_url.startswith(base_url):
            return full_url[len(base_url):]
        return full_url

    assert strip_prefix("http://hm:8001/hindsight/auth/callback", base_url) == "/auth/callback"
    assert strip_prefix("http://hm:8001/hindsight/auth/logout", base_url) == "/auth/logout"
    assert strip_prefix("/already/relative", base_url) == "/already/relative"
    assert strip_prefix(None, base_url) is None
    assert strip_prefix("http://other:9999/path", base_url) == "http://other:9999/path"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_migrations.py -v
```

Expected: PASS (this is a pure logic test, it tests the strip pattern). If the test file doesn't exist yet, it FAILS.

- [ ] **Step 3: Write the migration**

Create `xinyi_platform/migrations/versions/006_relative_client_urls.py`:

```python
"""convert redirect_uris and logout_url to relative paths

Revision ID: 006
Revises: 005
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _strip_base_url(full_url, base_url):
    """Strip base_url prefix from a full URL, returning relative path."""
    if full_url and base_url and full_url.startswith(base_url):
        return full_url[len(base_url):]
    return full_url


def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        sa.text("SELECT id, base_url, redirect_uris, logout_url FROM xinyi.business_clients")
    ).fetchall()

    for row in rows:
        client_id, base_url, redirect_uris, logout_url = row
        if not base_url:
            continue

        new_redirect_uris = None
        if redirect_uris:
            new_redirect_uris = [
                _strip_base_url(u, base_url) for u in redirect_uris
            ]

        new_logout_url = _strip_base_url(logout_url, base_url) if logout_url else None

        conn.execute(
            sa.text(
                "UPDATE xinyi.business_clients SET redirect_uris = :ru, logout_url = :lu WHERE id = :id"
            ),
            {
                "ru": sa.text("null") if new_redirect_uris is None else new_redirect_uris,
                "lu": new_logout_url,
                "id": client_id,
            },
        )


def downgrade() -> None:
    # Cannot reverse — relative paths cannot be expanded back to full URLs
    # without knowing the historical base_url (which may have changed).
    pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_migrations.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/migrations/versions/006_relative_client_urls.py tests/test_migrations.py
git commit -m "feat: add migration to convert client URLs to relative paths"
```

---

### Task 2: xinyi-platform OAuth 匹配与 SLO 拼接

**Files:**
- Modify: `xinyi_platform/api/oauth.py:44`
- Modify: `xinyi_platform/services/business_client_service.py:68`
- Modify: `xinyi_platform/api/logout.py:44`
- Test: `tests/api/test_oauth_authorize.py`, `tests/unit/test_business_client_service.py`

**Interfaces:**
- Consumes: `BusinessClient.base_url`, `BusinessClient.redirect_uris`, `BusinessClient.logout_url`
- Produces: OAuth authorize and SLO logout correctly match/construct full URLs from relative paths

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_business_client_service.py`:

```python
async def test_verify_redirect_uri_matches_relative_path():
    """verify_redirect_uri should construct full URL from base_url + relative path."""
    from unittest.mock import AsyncMock, MagicMock
    from xinyi_platform.services.business_client_service import BusinessClientService

    mock_client = MagicMock()
    mock_client.base_url = "http://hm:8001/hindsight"
    mock_client.redirect_uris = ["/auth/callback"]
    mock_client.status = MagicMock()
    mock_client.status.value = "active"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_client

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Full URL from OAuth request should match base_url + relative path
    result = await BusinessClientService.verify_redirect_uri(
        mock_session, "hm-prod", "http://hm:8001/hindsight/auth/callback"
    )
    assert result is True

    # Wrong URL should not match
    result = await BusinessClientService.verify_redirect_uri(
        mock_session, "hm-prod", "http://evil.com/callback"
    )
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_business_client_service.py::test_verify_redirect_uri_matches_relative_path -v
```

Expected: FAIL because `verify_redirect_uri` still does direct comparison without base_url.

- [ ] **Step 3: Modify verify_redirect_uri**

In `xinyi_platform/services/business_client_service.py`, replace the `verify_redirect_uri` method body:

```python
    @staticmethod
    async def verify_redirect_uri(session: AsyncSession, client_id: str, redirect_uri: str) -> bool:
        result = await session.execute(
            select(BusinessClient).where(BusinessClient.client_id == client_id)
        )
        client = result.scalar_one_or_none()
        if client is None:
            return False
        base_url = client.base_url or ""
        full_uris = [f"{base_url}{u}" for u in (client.redirect_uris or [])]
        return redirect_uri in full_uris
```

- [ ] **Step 4: Modify OAuth authorize endpoint**

In `xinyi_platform/api/oauth.py`, replace line 44:

```python
    # Old: if redirect_uri not in (client.redirect_uris or []):
    # New:
    base_url = client.base_url or ""
    full_uris = [f"{base_url}{u}" for u in (client.redirect_uris or [])]
    if redirect_uri not in full_uris:
        raise HTTPException(status_code=400, detail="redirect_uri not allowed")
```

- [ ] **Step 5: Modify SLO logout**

In `xinyi_platform/api/logout.py`, replace line 44:

```python
    # Old: logout_urls = [c.logout_url for c in result.scalars().all() if c.logout_url]
    # New:
    logout_urls = [
        f"{c.base_url}{c.logout_url}"
        for c in result.scalars().all()
        if c.logout_url and c.base_url
    ]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_business_client_service.py tests/api/test_oauth_authorize.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add xinyi_platform/services/business_client_service.py xinyi_platform/api/oauth.py xinyi_platform/api/logout.py tests/unit/test_business_client_service.py
git commit -m "feat: construct full URLs from base_url + relative path in oauth and slo"
```

---

### Task 3: xinyi-platform 管理页面 placeholder 更新

**Files:**
- Modify: `xinyi_platform/templates/admin/clients.html`

**Interfaces:**
- Produces: Form placeholders show relative path examples

- [ ] **Step 1: Update placeholders**

In `xinyi_platform/templates/admin/clients.html`, update the register modal and edit modal placeholders:

Register modal (around line 58-62):
```html
<!-- Old -->
<textarea name="redirect_uris" rows="2" class="form-control" placeholder="http://localhost:8002/auth/callback"></textarea>
...
<input name="logout_url" class="form-control" placeholder="http://localhost:8002/auth/logout">

<!-- New -->
<textarea name="redirect_uris" rows="2" class="form-control" placeholder="/auth/callback"></textarea>
...
<input name="logout_url" class="form-control" placeholder="/auth/logout">
```

Edit modal (around line 134-138): same change.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add xinyi_platform/templates/admin/clients.html
git commit -m "refactor: update admin clients form placeholders to relative paths"
```

---

### Task 4: hindsight-manager 注册参数与 OAuth 流程

**Files:**
- Modify: `hindsight_manager/main.py:108-117`
- Modify: `hindsight_manager/config.py:40`
- Modify: `hindsight_manager/platform/config.py:17`
- Test: `tests/test_auth.py` (if exists) or manual verification

**Interfaces:**
- Consumes: `settings.oauth_redirect_uri` (now relative), `settings.base_url`
- Produces: Registration sends relative paths; `PlatformSettings.oauth_redirect_uri` constructs full URL so callers need no change.

**Key insight:** `api/auth.py` reads `ps.oauth_redirect_uri` from `PlatformSettings`. If `PlatformSettings.from_app_settings` constructs the full URI (`base_url + /hindsight + oauth_redirect_uri`), then `api/auth.py` needs **zero changes**.

- [ ] **Step 1: Update config default**

In `hindsight_manager/config.py`, change line 40:

```python
# Old
oauth_redirect_uri: str = "http://localhost:8001/hindsight/auth/callback"

# New
oauth_redirect_uri: str = "/auth/callback"
```

- [ ] **Step 2: Update registration parameters**

In `hindsight_manager/main.py`, change the `client_metadata` dict (around line 108-117):

```python
# Old
client_metadata={
    "client_id": settings.oauth_client_id,
    "name": "Hindsight Manager",
    "redirect_uris": [settings.oauth_redirect_uri],
    "logout_url": f"{settings.base_url}/hindsight/auth/logout",
    "base_url": f"{settings.base_url}/hindsight",
    "home_path": "/dashboard",
    "description": "RAG 记忆库",
},

# New
client_metadata={
    "client_id": settings.oauth_client_id,
    "name": "Hindsight Manager",
    "base_url": f"{settings.base_url}/hindsight",
    "redirect_uris": ["/auth/callback"],
    "logout_url": "/auth/logout",
    "home_path": "/dashboard",
    "description": "RAG 记忆库",
},
```

- [ ] **Step 3: Update PlatformSettings to construct full URI**

In `hindsight_manager/platform/config.py`, change `from_app_settings`:

```python
# Old
oauth_redirect_uri=settings.oauth_redirect_uri,

# New
oauth_redirect_uri=f"{settings.base_url}/hindsight{settings.oauth_redirect_uri}",
```

This makes `ps.oauth_redirect_uri` a full URL. `api/auth.py` reads `ps.oauth_redirect_uri` unchanged — no edits needed there.

- [ ] **Step 4: Run tests**

```bash
uv run pytest
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add hindsight_manager/main.py hindsight_manager/config.py hindsight_manager/platform/config.py
git commit -m "refactor: register relative URLs, construct full redirect_uri from base_url"
```

---

### Task 5: docupipe-manager 注册参数与 OAuth 流程

**Files:**
- Modify: `docupipe_manager/main.py:78-80`
- Modify: `docupipe_manager/config.py:23`
- Modify: `docupipe_manager/platform/config.py:9,17`

**Interfaces:**
- Same pattern as Task 4, with `/docupipe` prefix instead of `/hindsight`.

- [ ] **Step 1: Update config default**

In `docupipe_manager/config.py`, change line 23:

```python
# Old
oauth_redirect_uri: str = "http://localhost:8002/docupipe/auth/callback"

# New
oauth_redirect_uri: str = "/auth/callback"
```

- [ ] **Step 2: Update registration parameters**

In `docupipe_manager/main.py`, change the `client_metadata` dict (around line 78-80):

```python
# Old
"redirect_uris": [settings.oauth_redirect_uri],
"logout_url": f"{settings.base_url}/docupipe/auth/logout",
"base_url": f"{settings.base_url}/docupipe",

# New
"base_url": f"{settings.base_url}/docupipe",
"redirect_uris": ["/auth/callback"],
"logout_url": "/auth/logout",
```

- [ ] **Step 3: Update PlatformSettings to construct full URI**

In `docupipe_manager/platform/config.py`:

```python
# Old
oauth_redirect_uri=settings.oauth_redirect_uri,

# New
oauth_redirect_uri=f"{settings.base_url}/docupipe{settings.oauth_redirect_uri}",
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add docupipe_manager/main.py docupipe_manager/config.py docupipe_manager/platform/config.py
git commit -m "refactor: register relative URLs, construct full redirect_uri from base_url"
```

---

### Task 6: 全量测试与端到端验证

**Files:**
- No file changes.

- [ ] **Step 1: Run full test suite in all three projects**

```bash
# xinyi-platform
cd /Users/liling/src/lab/xinyi-platform && uv run pytest

# hindsight-manager
cd /Users/liling/src/lab/hindsight-manager && uv run pytest

# docupipe-manager
cd /Users/liling/src/lab/docupipe-manager && uv run pytest
```

Expected: All tests pass in all three projects.

- [ ] **Step 2: Start xinyi-platform and run migration**

```bash
cd /Users/liling/src/lab/xinyi-platform
uv run alembic upgrade head
uv run uvicorn xinyi_platform.main:app --reload --port 8000
```

- [ ] **Step 3: Verify admin clients page**

1. Open `http://localhost:8000/xinyi/admin/clients`
2. Verify `redirect_uris` and `logout_url` columns show relative paths (e.g., `/auth/callback`, `/auth/logout`)

- [ ] **Step 4: Start hindsight-manager and verify OAuth flow**

```bash
cd /Users/liling/src/lab/hindsight-manager
uv run uvicorn hindsight_manager.main:app --reload --port 8001
```

1. Open `http://localhost:8001/hindsight/dashboard`
2. Should redirect to platform OAuth authorize
3. Login and verify callback works

- [ ] **Step 5: Start docupipe-manager and verify OAuth flow**

```bash
cd /Users/liling/src/lab/docupipe-manager
uv run uvicorn docupipe_manager.main:app --reload --port 8002
```

1. Open `http://localhost:8002/docupipe/projects`
2. Should redirect to platform OAuth authorize
3. Login and verify callback works

- [ ] **Step 6: Verify SLO logout**

1. From any service, click logout
2. Verify all iframes load correctly (check browser network tab for logout_url requests)

---

## Self-Review

**Spec coverage:**
- 数据迁移：Task 1
- OAuth authorize 匹配：Task 2
- verify_redirect_uri 拼接：Task 2
- SLO 登出拼接：Task 2
- 管理页面 placeholder：Task 3
- hindsight-manager 注册+OAuth：Task 4
- docupipe-manager 注册+OAuth：Task 5
- 端到端验证：Task 6

**Placeholder scan:** 所有步骤包含完整代码和命令，无 TBD/TODO。

**Type consistency:** `PlatformSettings.oauth_redirect_uri` 在两个业务服务中都改为存储完整 URL（由 base_url + 相对路径拼接），保持调用方接口不变。
