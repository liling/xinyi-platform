# 安全问题与代码质量修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 xinyi-platform 身份认证平台的 5 个安全问题 + CSRF 全面接入 + 6 个代码质量问题，架构性改动留作 TODO 文档。

**Architecture:** 按"安全优先 → 代码质量（为 CSRF 铺路）→ CSRF 接入 → TODO 文档"顺序分批执行。CSRF 采用 double-submit cookie 模式（middleware 设 cookie + 模板上下文注入 token + 依赖验证）。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, pytest + pytest-asyncio, uv

## Global Constraints

- Python >= 3.12, 使用 `uv run pytest` 运行测试
- 代码风格：ruff, line-length=120, target-version=py312
- 测试框架：pytest + pytest-asyncio (asyncio_mode=auto)
- 不引入新依赖
- 所有对话和注释使用简体中文（用户偏好）；代码标识符用英文

---

## File Structure

**新建文件：**
- `xinyi_platform/api/_shared.py` — 公共模板上下文函数 + csrf_token 注入
- `xinyi_platform/middleware/csrf.py` — CSRF double-submit cookie middleware + 验证依赖
- `docs/security-todos.md` — 架构性安全改进 TODO

**删除文件：**
- `xinyi_platform/crypto.py` — SM4-ECB 死代码
- `xinyi_platform/auth/oauth_state.py` — 误导性死代码
- `tests/unit/test_sm4.py`
- `tests/unit/test_oauth_state.py`
- `xinyi_platform/tests/` — 空目录

**修改文件（按批次）：**

| 批次 | 文件 | 改动 |
|------|------|------|
| 1 | `auth/internal_auth.py` | compare_digest |
| 1 | `config.py`, `.env`, `.env.example`, `README.md` | 删 encryption_key |
| 1 | `main.py` | session_secure 警告 |
| 1 | `api/login.py` | 登录失败记录 |
| 3 | `auth/session.py` | 新增 SELF_AUDIENCE 常量 |
| 3 | `api/login.py`, `api/cas.py`, `api/oauth.py`, `auth/dependencies.py` | 引用集中常量 |
| 3 | `api/login.py`, `api/cas.py`, 6 个 admin api | `_ui_ctx` → `_shared.py` |
| 3 | `main.py` | 产品列表逻辑去重 |
| 3 | `models/business_client.py` | 时间戳重复定义删除 |
| 2 | `middleware/csrf.py` | CSRF 核心 |
| 2 | `main.py` | 注册 CSRF middleware |
| 2 | `api/_shared.py` | 注入 csrf_token |
| 2 | 8 个表单 POST 端点 + 2 个 JSON POST 端点 | 加 CSRF 验证依赖 |
| 2 | ~6 个模板 | 加 hidden csrf_token |

---

## 批次 1 — 快速安全修复

### Task 1: registration_token 时序侧信道修复

**Files:**
- Modify: `xinyi_platform/auth/internal_auth.py`
- Test: `tests/unit/test_internal_auth.py`

**Interfaces:**
- Produces: `verify_registration_token` 行为不变（返回 token 或抛 401），但内部改用 `compare_digest`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_internal_auth.py`:

```python
import secrets

import pytest
from fastapi import HTTPException

from xinyi_platform.auth.internal_auth import verify_registration_token


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr("xinyi_platform.auth.internal_auth.get_settings", lambda: type("S", (), {"registration_token": "valid-token-123"})())
    return "valid-token-123"


async def test_correct_token_passes(mock_settings):
    result = await verify_registration_token(x_registration_token="valid-token-123")
    assert result == "valid-token-123"


async def test_wrong_token_rejected(mock_settings):
    with pytest.raises(HTTPException) as exc:
        await verify_registration_token(x_registration_token="wrong-token")
    assert exc.value.status_code == 401


async def test_empty_token_rejected(mock_settings):
    with pytest.raises(HTTPException) as exc:
        await verify_registration_token(x_registration_token="")
    assert exc.value.status_code == 401


async def test_token_not_configured(monkeypatch):
    monkeypatch.setattr("xinyi_platform.auth.internal_auth.get_settings", lambda: type("S", (), {"registration_token": ""})())
    with pytest.raises(HTTPException) as exc:
        await verify_registration_token(x_registration_token="anything")
    assert exc.value.status_code == 500
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_internal_auth.py -v
```

Expected: FAIL (current code returns 401 for empty config, not 500)

- [ ] **Step 3: Implement the fix**

Replace `xinyi_platform/auth/internal_auth.py:21-27` with:

```python
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.config import get_settings
from xinyi_platform.db import get_session
from xinyi_platform.models.business_client import BusinessClient
from xinyi_platform.services.business_client_service import BusinessClientService


async def verify_internal_client(
    x_client_id: str = Header(..., alias="X-Client-Id"),
    x_client_secret: str = Header(..., alias="X-Client-Secret"),
    session: AsyncSession = Depends(get_session),
) -> BusinessClient:
    client = await BusinessClientService.verify_secret(session, x_client_id, x_client_secret)
    if client is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client credentials")
    return client


async def verify_registration_token(
    x_registration_token: str = Header(..., alias="X-Registration-Token"),
) -> str:
    settings = get_settings()
    if not settings.registration_token:
        raise HTTPException(status_code=500, detail="Registration token not configured")
    if not secrets.compare_digest(x_registration_token, settings.registration_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid registration token")
    return x_registration_token
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_internal_auth.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/auth/internal_auth.py tests/unit/test_internal_auth.py
git commit -m "fix: use compare_digest for registration_token to prevent timing attack"
```

---

### Task 2: 删除死代码（SM4-ECB + oauth_state）

**Files:**
- Delete: `xinyi_platform/crypto.py`, `xinyi_platform/auth/oauth_state.py`
- Delete: `tests/unit/test_sm4.py`, `tests/unit/test_oauth_state.py`
- Modify: `xinyi_platform/config.py:15` (删 `encryption_key`)
- Modify: `.env`, `.env.example` (删 `ENCRYPTION_KEY` 行)
- Modify: `README.md:17` (删 ENCRYPTION_KEY 生成说明)

**Note:** `config.py:15` 的 `encryption_key: str` 是必填项。删除前必须先清理 `.env`，否则 `Settings()` 启动报错。`extra="ignore"` 确保旧 .env 残留的行不会报错，但必须删除 `encryption_key` 字段定义。

- [ ] **Step 1: 删除死代码文件**

```bash
rm xinyi_platform/crypto.py xinyi_platform/auth/oauth_state.py
rm tests/unit/test_sm4.py tests/unit/test_oauth_state.py
```

- [ ] **Step 2: 删除 config.py 中的 encryption_key**

在 `xinyi_platform/config.py` 中，删除第 15 行：

```
    encryption_key: str
```

改为只保留 `jwt_secret`:
```python
    jwt_secret: str
    admin_username: str = "admin"
```

- [ ] **Step 3: 清理 .env 和 .env.example**

删除这两个文件中包含 `ENCRYPTION_KEY` 的行。

- [ ] **Step 4: 清理 README.md**

删除 Quick Start 中生成 ENCRYPTION_KEY 的那一行注释：
```
#   python -c "import secrets; print(secrets.token_hex(16))"     # ENCRYPTION_KEY
```

- [ ] **Step 5: 确认无残留引用**

```bash
rg "encryption_key|ENCRYPTION_KEY|crypto\.|oauth_state" xinyi_platform/ tests/ --type py
```

Expected: 无输出（或仅有无关匹配）

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -x -q
```

Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove dead code (SM4-ECB crypto + oauth_state HMAC tools)"
```

---

### Task 3: session_secure 启动警告

**Files:**
- Modify: `xinyi_platform/main.py` (lifespan 函数)
- Test: `tests/test_startup.py`

**Interfaces:**
- Produces: lifespan 中 seed_admin 之后新增 session_secure 检查日志

- [ ] **Step 1: Write the failing test**

Append to `tests/test_startup.py`:

```python
import logging

from xinyi_platform.main import settings


def test_session_secure_warning_when_disabled(caplog):
    """session_secure=False 时应输出 WARNING 日志"""
    with caplog.at_level(logging.WARNING, logger="xinyi_platform"):
        # 直接调用检查函数
        from xinyi_platform.main import _warn_if_session_insecure
        _warn_if_session_insecure(settings.__class__(session_secure=False))
    assert any("SESSION_SECURE is False" in r.message for r in caplog.records)


def test_session_secure_no_warning_when_enabled(caplog):
    """session_secure=True 时不应输出 WARNING"""
    with caplog.at_level(logging.WARNING, logger="xinyi_platform"):
        from xinyi_platform.main import _warn_if_session_insecure
        _warn_if_session_insecure(settings.__class__(session_secure=True))
    assert not any("SESSION_SECURE" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_startup.py::test_session_secure_warning_when_disabled -v
```

Expected: FAIL (`_warn_if_session_insecure` not defined)

- [ ] **Step 3: Implement**

在 `xinyi_platform/main.py` 中，`_cleanup_expired_tokens` 函数之前（约第 54 行），添加：

```python
def _warn_if_session_insecure(settings: Settings) -> None:
    if not settings.session_secure:
        logger.warning(
            "SESSION_SECURE is False — session cookies will be transmitted over HTTP. "
            "Set XINYI_PLATFORM_SESSION_SECURE=true in production (HTTPS only)."
        )
```

在 `lifespan` 函数中，`seed_admin_if_absent` 调用之后（约第 71 行），添加：

```python
    async with app_state.session_factory() as session:
        from xinyi_platform.startup import seed_admin_if_absent
        await seed_admin_if_absent(session, settings)

    _warn_if_session_insecure(settings)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_startup.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/main.py tests/test_startup.py
git commit -m "feat: warn at startup when session_secure is disabled"
```

---

### Task 4: 登录失败审计记录

**Files:**
- Modify: `xinyi_platform/api/login.py` (`login_json` 和 `login_form` 两个失败分支)
- Test: `tests/api/test_login.py`

**Interfaces:**
- Produces: 登录失败时写入 `LoginHistory(success=False, failure_reason=...)`

- [ ] **Step 1: Write the failing test**

在 `tests/api/test_login.py` 中新增（如果文件不存在则创建，参照现有 API 测试的 conftest 模式）：

```python
import pytest
from sqlalchemy import select

from xinyi_platform.models.login_history import LoginHistory


async def test_login_failure_records_history(authenticated_client, db_session):
    """错误密码应写入 LoginHistory(success=False)"""
    response = await authenticated_client.post("/xinyi/login", json={
        "username": "admin",
        "password": "wrong-password",
    })
    assert response.status_code == 401
    result = await db_session.execute(
        select(LoginHistory).where(LoginHistory.success == False)
    )
    records = result.scalars().all()
    assert len(records) >= 1
    assert records[-1].failure_reason is not None


async def test_login_form_failure_records_history(authenticated_client, db_session):
    """表单登录失败也应写入 LoginHistory"""
    response = await authenticated_client.post("/xinyi/login/form", data={
        "username": "admin",
        "password": "wrong-password",
        "return_to": "/xinyi/account",
    })
    result = await db_session.execute(
        select(LoginHistory).where(LoginHistory.success == False)
    )
    records = result.scalars().all()
    assert len(records) >= 1
```

> 注意：测试中的 fixture 名称和路径需参照 `tests/conftest.py` 的实际定义。如果 `authenticated_client` 不存在，用现有测试的 client fixture 替代。

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/api/test_login.py::test_login_failure_records_history -v
```

Expected: FAIL (当前失败分支不写 LoginHistory)

- [ ] **Step 3: Implement**

在 `xinyi_platform/api/login.py` 中，提取一个失败记录辅助函数（在 `_get_client_ip` 之后）：

```python
async def _record_failed_login(session: AsyncSession, request: Request, user: User | None, reason: str):
    """记录失败的登录尝试到 LoginHistory"""
    session.add(LoginHistory(
        user_id=user.id if user else None,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        success=False,
        failure_reason=reason,
    ))
    await session.commit()
```

修改 `login_json`（约第 80-83 行），在 raise 之前记录：

```python
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.password_hash or not verify_password(password, user.password_hash):
        reason = "user_not_found" if user is None else ("user_disabled" if not user.is_active else "invalid_credentials")
        await _record_failed_login(session, request, user, reason)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
```

修改 `login_form`（约第 121-128 行），在返回模板之前记录：

```python
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.password_hash or not verify_password(password, user.password_hash):
        reason = "user_not_found" if user is None else ("user_disabled" if not user.is_active else "invalid_credentials")
        await _record_failed_login(session, request, user, reason)
        return templates.TemplateResponse(
            request, "login.html",
            {**_ui_ctx(request), "error": "用户名或密码错误", "return_to": return_to},
            status_code=200,
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/api/test_login.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/api/login.py tests/api/test_login.py
git commit -m "feat: record failed login attempts to LoginHistory for audit"
```

---

## 批次 3 — 代码质量清理（先于 CSRF 执行）

### Task 5: 常量集中与工具函数去重

**Files:**
- Modify: `xinyi_platform/auth/session.py` (新增 SELF_AUDIENCE 常量)
- Modify: `xinyi_platform/api/login.py`, `xinyi_platform/api/cas.py`, `xinyi_platform/api/oauth.py`, `xinyi_platform/auth/dependencies.py`
- Create: `xinyi_platform/auth/request_util.py` (`_get_client_ip` 提取)

**Interfaces:**
- Produces: `auth.session.SELF_AUDIENCE`, `auth.request_util.get_client_ip`

- [ ] **Step 1: 添加 SELF_AUDIENCE 常量到 session.py**

在 `xinyi_platform/auth/session.py` 顶部添加：

```python
SELF_AUDIENCE = "xinyi-platform-self"
```

- [ ] **Step 2: 创建 request_util.py**

Create `xinyi_platform/auth/request_util.py`:

```python
from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
```

- [ ] **Step 3: 替换各文件中的重复定义**

在以下文件中：
- `api/login.py`: 删除 `SELF_CLIENT_ID = "xinyi-platform-self"` (第 21 行) 和 `_get_client_ip` (第 49-53 行)，改为 `from xinyi_platform.auth.session import SELF_AUDIENCE` 和 `from xinyi_platform.auth.request_util import get_client_ip`。将所有 `SELF_CLIENT_ID` 替换为 `SELF_AUDIENCE`，`_get_client_ip` 替换为 `get_client_ip`。
- `api/cas.py`: 同上模式，删除本地 `SELF_CLIENT_ID` 和 `_get_client_ip`，改为 import。
- `api/oauth.py`: 删除 `SELF_AUDIENCE = "xinyi-platform-self"` (第 17 行)，改为 `from xinyi_platform.auth.session import SELF_AUDIENCE`。
- `auth/dependencies.py`: 将硬编码的 `"xinyi-platform-self"` 改为 `from xinyi_platform.auth.session import SELF_AUDIENCE` 引用。

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -x -q
```

Expected: 全部 PASS（纯重构，不改行为）

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: centralize SELF_AUDIENCE constant and deduplicate get_client_ip"
```

---

### Task 6: _ui_ctx 去重

**Files:**
- Create: `xinyi_platform/api/_shared.py`
- Modify: `api/login.py`, `api/register.py`, `api/password.py`, `api/me.py`, `api/admin_users.py`, `api/admin_clients.py`, `api/admin_audit.py`, `api/admin_login_history.py`

**Interfaces:**
- Produces: `api._shared.build_template_context(request) -> dict`

- [ ] **Step 1: 创建 _shared.py**

Create `xinyi_platform/api/_shared.py`:

```python
from fastapi import Request


def build_template_context(request: Request) -> dict:
    """统一的模板上下文：UI globals。CSRF token 在批次 2 接入时追加。"""
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "products": ui["products"],
        "platform_url": ui["platform_url"],
        "manager_url": ui.get("manager_url", ""),
        "service_prefix": ui.get("service_prefix", ""),
    }
```

- [ ] **Step 2: 替换 8 个文件中的 _ui_ctx**

在每个文件中：
1. 添加 `from xinyi_platform.api._shared import build_template_context`
2. 删除本地的 `_ui_ctx` 函数定义
3. 将所有 `_ui_ctx(request)` 调用替换为 `build_template_context(request)`

涉及文件（每个文件的结构相同，都有 `_ui_ctx` 函数）：
- `api/login.py` (第 24-34 行)
- `api/register.py`
- `api/password.py`
- `api/me.py`
- `api/admin_users.py`
- `api/admin_clients.py`
- `api/admin_audit.py`
- `api/admin_login_history.py`

- [ ] **Step 3: 确认无残留 _ui_ctx**

```bash
rg "_ui_ctx" xinyi_platform/ --type py
```

Expected: 无输出

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -x -q
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: deduplicate _ui_ctx into shared build_template_context"
```

---

### Task 7: main.py 产品列表去重 + 模型去重 + 删空目录

**Files:**
- Modify: `xinyi_platform/main.py`
- Modify: `xinyi_platform/models/business_client.py` (第 44-49 行删除)
- Delete: `xinyi_platform/tests/` 目录

- [ ] **Step 1: 提取 _build_products 函数**

在 `xinyi_platform/main.py` 中，`_cleanup_expired_tokens` 之后（约第 60 行），添加：

```python
async def _build_products(session_factory, settings) -> list:
    """从 DB 查询 active 业务客户端，构建产品切换器列表。"""
    from xinyi_platform.models.business_client import BusinessClient, ClientStatus
    from xinyi_platform.ui_common.service_discovery import build_product_list

    async with session_factory() as session:
        result = await session.execute(
            select(BusinessClient).where(
                BusinessClient.status == ClientStatus.ACTIVE,
                BusinessClient.base_url.isnot(None),
            ).order_by(BusinessClient.name)
        )
        active = result.scalars().all()
        active_dicts = [
            {"client_id": c.client_id, "name": c.name, "base_url": c.base_url,
             "home_path": c.home_path or "", "description": c.description or ""}
            for c in active
        ]
        return build_product_list(
            active_dicts,
            platform_url=settings.base_url,
            self_client_id="platform",
            self_name=settings.brand_name,
            self_home_path="/account",
        )
```

- [ ] **Step 2: 替换 lifespan 中的重复逻辑**

lifespan 中（约第 72-100 行）替换为：

```python
    app.state.ui["products"] = await _build_products(app_state.session_factory, settings)
```

`_refresh_products` 函数体替换为：

```python
    async def _refresh_products():
        app.state.ui["products"] = await _build_products(app_state.session_factory, settings)
```

- [ ] **Step 3: 删除 business_client.py 重复时间戳**

删除 `xinyi_platform/models/business_client.py` 第 44-49 行（第二组重复的 `created_at`/`updated_at` 定义）。

- [ ] **Step 4: 删除空目录**

```bash
rm -rf xinyi_platform/tests/
```

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -x -q
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: deduplicate product list builder, remove duplicate timestamps and empty test dir"
```

---

## 批次 2 — CSRF 全面接入

### Task 8: CSRF 核心（middleware + 验证依赖）

**Files:**
- Create: `xinyi_platform/middleware/csrf.py`
- Modify: `xinyi_platform/main.py` (注册 middleware)
- Modify: `xinyi_platform/api/_shared.py` (注入 csrf_token)
- Test: `tests/unit/test_csrf.py`

**Interfaces:**
- Produces: `CsrfMiddleware` (ASGI middleware), `verify_csrf_token` (FastAPI dependency)
- Produces: `build_template_context` 返回值新增 `csrf_token` 字段

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_csrf.py`:

```python
import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from xinyi_platform.auth.csrf import generate_csrf_token, verify_csrf


def test_verify_csrf_matching():
    token = generate_csrf_token()
    assert verify_csrf(token, token) is True


def test_verify_csrf_mismatch():
    assert verify_csrf("token-a", "token-b") is False


def test_verify_csrf_empty():
    assert verify_csrf("", "") is False
    assert verify_csrf("token", "") is False
    assert verify_csrf("", "token") is False
```

- [ ] **Step 2: Run test to verify it passes (existing csrf.py)**

```bash
uv run pytest tests/unit/test_csrf.py -v
```

Expected: PASS (csrf.py 已有，这是回归确认)

- [ ] **Step 3: Create CSRF middleware**

Create `xinyi_platform/middleware/csrf.py`:

```python
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from xinyi_platform.auth.csrf import generate_csrf_token, verify_csrf


class CsrfMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF 防护。

    所有请求：生成/复用 csrf token，存入 request.state，首次设 cookie。
    POST 验证不在 middleware 做（由 verify_csrf_token 依赖按需加到端点），
    这样 internal API / oauth/token 等非浏览器端点不受影响。
    """

    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get("xinyi_csrf") or generate_csrf_token()
        request.state.csrf_token = token

        response = await call_next(request)

        # 首次设置 cookie（不存在时）
        if not request.cookies.get("xinyi_csrf"):
            response.set_cookie(
                "xinyi_csrf", token,
                httponly=False, samesite="lax", path="/",
            )
        return response


async def verify_csrf_token(request: Request) -> None:
    """FastAPI 依赖：验证 CSRF token。表单用 form field，JSON 用 header。

    用法：在需要保护的端点加 _csrf=Depends(verify_csrf_token)
    internal API 和 oauth/token 不加此依赖（非浏览器提交，靠 secret 认证）。
    """
    cookie_token = request.cookies.get("xinyi_csrf", "")

    # 先尝试 form field（表单提交）
    submitted = ""
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        submitted = form.get("csrf_token", "")

    # 再尝试 header（JSON API）
    if not submitted:
        submitted = request.headers.get("x-csrf-token", "")

    if not verify_csrf(cookie_token, submitted):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
```

- [ ] **Step 4: 注册 middleware 到 main.py**

在 `xinyi_platform/main.py` 中，`app = FastAPI(...)` 之后（约第 147 行），添加：

```python
from xinyi_platform.middleware.csrf import CsrfMiddleware

app.add_middleware(CsrfMiddleware)
```

- [ ] **Step 5: 注入 csrf_token 到模板上下文**

修改 `xinyi_platform/api/_shared.py`，在 `build_template_context` 中添加 csrf_token：

```python
def build_template_context(request: Request) -> dict:
    """统一的模板上下文：UI globals + csrf_token。"""
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "products": ui["products"],
        "platform_url": ui["platform_url"],
        "manager_url": ui.get("manager_url", ""),
        "service_prefix": ui.get("service_prefix", ""),
        "csrf_token": getattr(request.state, "csrf_token", ""),
    }
```

- [ ] **Step 6: Write integration test for middleware**

Append to `tests/unit/test_csrf.py`:

```python
from fastapi import FastAPI, Depends, Form
from fastapi.testclient import TestClient

from xinyi_platform.middleware.csrf import CsrfMiddleware, verify_csrf_token


def _make_test_app():
    app = FastAPI()
    app.add_middleware(CsrfMiddleware)

    @app.get("/form-page")
    async def form_page(request):
        from starlette.responses import HTMLResponse
        token = getattr(request.state, "csrf_token", "")
        return HTMLResponse(f'<form method="post"><input name="csrf_token" value="{token}"></form>')

    @app.post("/submit")
    async def submit(_=Depends(verify_csrf_token)):
        return {"ok": True}

    return app


def test_get_sets_csrf_cookie():
    app = _make_test_app()
    client = TestClient(app)
    resp = client.get("/form-page")
    assert "xinyi_csrf" in resp.cookies


def test_post_without_token_rejected():
    app = _make_test_app()
    client = TestClient(app)
    client.get("/form-page")  # 获取 cookie
    resp = client.post("/submit", data={})
    assert resp.status_code == 403


def test_post_with_matching_token_accepted():
    app = _make_test_app()
    client = TestClient(app)
    resp_get = client.get("/form-page")
    token = resp_get.cookies["xinyi_csrf"]
    resp = client.post("/submit", data={"csrf_token": token})
    assert resp.status_code == 200


def test_post_with_mismatched_token_rejected():
    app = _make_test_app()
    client = TestClient(app)
    client.get("/form-page")
    resp = client.post("/submit", data={"csrf_token": "wrong"})
    assert resp.status_code == 403
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/unit/test_csrf.py -v
```

Expected: PASS (全部)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add CSRF double-submit cookie middleware and verification dependency"
```

---

### Task 9: CSRF 接入表单端点

**Files:**
- Modify: `api/login.py`, `api/register.py`, `api/password.py`, `api/admin_users.py`, `api/admin_clients.py`, `api/logout.py` (如有表单 POST)
- Modify templates: `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, `admin/user_form.html`, `admin/clients.html`
- Test: `tests/api/test_csrf_integration.py`

**Note:** GET 表单页面已自动有 csrf_token（middleware + build_template_context），只需改 POST 端点加依赖 + 模板加 hidden field。

- [ ] **Step 1: 给表单 POST 端点加 CSRF 依赖**

在每个表单 POST 端点的函数签名中添加 `_=Depends(verify_csrf_token)`。

示例（`api/login.py` 的 `login_form`）：

```python
from xinyi_platform.middleware.csrf import verify_csrf_token

@router.post("/login/form")
async def login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    return_to: str = Form("/xinyi/account"),
    _limiter=Depends(login_limiter),
    _csrf=Depends(verify_csrf_token),  # 新增
    session: AsyncSession = Depends(get_session),
):
```

需要添加 CSRF 依赖的端点：
- `api/login.py`: `POST /login/form`
- `api/register.py`: `POST /register`
- `api/password.py`: `POST /password/reset`
- `api/admin_users.py`: `POST /admin/users`, `POST /admin/users/{id}`, `POST /admin/users/{id}/delete`
- `api/admin_clients.py`: `POST /admin/clients`, `PATCH /admin/clients/{id}`, `POST /admin/clients/{id}/disable`, `POST /admin/clients/{id}/enable`
- `api/logout.py`: `POST /logout`（如果是表单提交）

> 执行时读取每个文件，在所有表单 POST/PATCH/DELETE 端点签名中添加 `_csrf=Depends(verify_csrf_token)`。

- [ ] **Step 2: 给模板表单加 hidden csrf_token**

在每个含 `<form method="post">` 的模板中，在 `<form>` 标签之后添加：

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

需要改的模板（用 `rg "<form.*method=\"post\"" xinyi_platform/templates/` 确认完整列表）：
- `templates/login.html`
- `templates/register.html`
- `templates/forgot_password.html`
- `templates/reset_password.html`
- `templates/admin/user_form.html`
- `templates/admin/clients.html`

- [ ] **Step 3: Write integration test**

Create `tests/api/test_csrf_integration.py`:

```python
import pytest


async def test_register_requires_csrf(client):
    """注册端点无 CSRF token 应返回 403"""
    resp = client.post("/xinyi/register", data={
        "username": "testuser",
        "password": "Test1234",
    })
    assert resp.status_code == 403


async def test_register_with_csrf_succeeds(client):
    """注册端点带正确 CSRF token 应通过 CSRF 检查"""
    # 先 GET 注册页面获取 csrf cookie
    page = client.get("/xinyi/register")
    token = page.cookies.get("xinyi_csrf", "")
    resp = client.post("/xinyi/register", data={
        "username": "testuser2",
        "password": "Test1234",
        "csrf_token": token,
    })
    # 可能因业务逻辑失败（如用户名重复），但不应是 403
    assert resp.status_code != 403


async def test_admin_create_user_requires_csrf(admin_client):
    """管理端点无 CSRF 应 403"""
    resp = admin_client.post("/xinyi/admin/users", data={
        "username": "newuser",
        "password": "Test1234",
        "role": "user",
    })
    assert resp.status_code == 403
```

> 注意：fixture 名称参照 `tests/conftest.py`。如果 `admin_client` 不存在，用现有认证 client 替代。

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/api/test_csrf_integration.py -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite (修复被 CSRF 影响的现有测试)**

```bash
uv run pytest -x -q
```

> 现有测试中的 POST 表单请求现在会因缺少 CSRF token 而 403。需要在测试 client 的 fixture 中先 GET 页面获取 cookie，或者在测试中手动添加 csrf_token。更新受影响的测试。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: enforce CSRF protection on all form POST endpoints"
```

---

### Task 10: CSRF 接入 JSON API 端点

**Files:**
- Modify: `api/login.py` (`POST /login` JSON), `api/oauth.py` (`POST /oauth/revoke`)

**Note:** 这些是浏览器 JS fetch 调用的 JSON 端点，用 `X-CSRF-Token` header 提交 CSRF token。

- [ ] **Step 1: 给 JSON POST 端点加 CSRF 依赖**

`api/login.py` 的 `login_json`（`POST /login`）：

```python
@router.post("/login")
async def login_json(
    request: Request,
    body: dict,
    _limiter=Depends(login_limiter),
    _csrf=Depends(verify_csrf_token),  # 新增
    session: AsyncSession = Depends(get_session),
):
```

`api/oauth.py` 的 `revoke`（`POST /oauth/revoke`）：

```python
@router.post("/revoke")
async def revoke(
    body: dict = Body(...),
    _csrf=Depends(verify_csrf_token),  # 新增
    session: AsyncSession = Depends(get_session),
):
```

- [ ] **Step 2: 添加测试**

Append to `tests/api/test_csrf_integration.py`:

```python
async def test_json_login_requires_csrf_header(client):
    """JSON 登录无 CSRF header 应 403"""
    resp = client.post("/xinyi/login", json={
        "username": "admin",
        "password": "test",
    })
    assert resp.status_code == 403


async def test_json_login_with_csrf_header(client):
    """JSON 登录带正确 X-CSRF-Token header 应通过 CSRF 检查"""
    page = client.get("/xinyi/login")
    token = page.cookies.get("xinyi_csrf", "")
    resp = client.post("/xinyi/login", json={
        "username": "admin",
        "password": "test",
    }, headers={"X-CSRF-Token": token})
    assert resp.status_code != 403
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/api/test_csrf_integration.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: enforce CSRF on JSON POST endpoints (login, oauth/revoke)"
```

---

## 批次 4 — 架构性 TODO 文档

### Task 11: 创建 security-todos.md

**Files:**
- Create: `docs/security-todos.md`

- [ ] **Step 1: Write the document**

Create `docs/security-todos.md`:

```markdown
# 安全改进 TODO

记录已知的架构性安全改进，需独立设计周期，未包含在常规修复批次中。

## 1. 分布式限流

**现状**: `middleware/rate_limit.py` 的 `InMemoryRateLimiter` 是单进程内存计数器。
多 worker 部署（`uvicorn --workers N`）下各进程独立计数，限流阈值实际放大 N 倍。

**计划**: 引入 Redis 实现分布式滑动窗口计数器，保留 InMemoryRateLimiter 作为
单进程 fallback（开发环境）。限流 key 统一使用 `x-forwarded-for` 解析的真实 IP。

**优先级**: 中。生产多 worker 部署时需处理。

## 2. JWT 密钥轮换

**现状**: 所有业务客户端共享单一 `jwt_secret`（HS256 对称密钥）。任一业务泄露密钥
即全平台沦陷。无密钥轮换机制。

**计划**: 实现 kid（key ID）机制：
- JWT header 增加 `kid` 字段标识签发密钥
- 配置支持密钥列表（current + previous）
- 签发用 current，验签按 kid 查找
- 轮换流程：previous=current, current=new，旧密钥设置过期窗口

**优先级**: 中。密钥泄露影响范围大。

## 3. client_secret 派生算法

**现状**: `ui_common/service_discovery.py` 的 `derive_client_secret` 使用
`HMAC-SHA256(registration_token, client_id)` 确定性派生。算法公开，保护完全压在
`registration_token` 保密上。

**评估**: 当前为可接受的设计权衡。业务自注册流程简洁，无需手动保管 secret。

**如需更高安全**: 改为每客户端独立随机 secret + 数据库存储，注册时返回一次明文。

**优先级**: 低。

## 4. OAuth PKCE 支持

**现状**: OAuth2 授权码流程不支持 PKCE（Proof Key for Code Exchange）。

**计划**: 在 `/oauth/authorize` 支持 `code_challenge` / `code_challenge_method` 参数，
在 `/oauth/token` 支持 `code_verifier` 校验。需评估与现有业务客户端
（`ui_common/service_discovery.py`）的兼容性。

**优先级**: 中。PKCE 是 OAuth 2.1 推荐的安全增强。
```

- [ ] **Step 2: Commit**

```bash
git add docs/security-todos.md
git commit -m "docs: add security TODO for architectural improvements"
```

---

## Verification Checklist

完成所有任务后，运行最终验证：

- [ ] **全量测试通过**

```bash
uv run pytest -v
```

- [ ] **Lint 通过**

```bash
uv run ruff check xinyi_platform/ tests/
```

- [ ] **无死代码残留**

```bash
rg "encryption_key|ENCRYPTION_KEY|from xinyi_platform.crypto|oauth_state" xinyi_platform/ tests/ --type py
```

Expected: 无输出

- [ ] **无 _ui_ctx 残留**

```bash
rg "_ui_ctx|_get_client_ip|SELF_CLIENT_ID" xinyi_platform/ --type py
```

Expected: 无输出（已全部替换为集中常量/函数）

- [ ] **CSRF 覆盖确认**

```bash
rg "Depends\(verify_csrf_token\)" xinyi_platform/api/ --type py
```

Expected: 所有表单 POST + JSON POST 端点都有
