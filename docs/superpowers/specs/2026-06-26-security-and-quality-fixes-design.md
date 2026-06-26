# 安全问题与代码质量修复设计

**日期**: 2026-06-26
**状态**: 已批准，待写实现计划
**范围**: xinyi-platform 身份认证平台的安全加固与代码质量清理

## 问题陈述

xinyi-platform 是一个基于 FastAPI 的统一身份认证 / SSO 平台，服务于"心懿"系列业务系统。架构审查发现 8 个安全问题和 6 个代码质量问题。

安全方面：存在 CSRF 防护缺失、时序侧信道、死代码（含不安全算法）、审计盲区等问题。代码质量方面：存在多处重复代码、散落的魔法字符串、冗余定义和残留空目录。

本设计修复其中可快速安全落地的部分，架构性改动（分布式限流、密钥轮换、PKCE）留作 TODO 文档。

## 范围

### In scope（本轮修复）

**安全（5 项明确修复 + CSRF 全面接入）**:
1. `registration_token` 时序侧信道 → `compare_digest`
2. 删除 SM4-ECB 死代码（不安全算法 + 零引用）
3. 删除 `oauth_state.py` 死代码（误导性，场景与标准 OAuth2 冲突）
4. `session_secure=False` 时启动警告
5. 登录失败记录到 `LoginHistory`
6. CSRF double-submit cookie 全面接入（~10 个表单端点）

**代码质量（6 项重构）**:
1. `_ui_ctx(request)` 去重（8 处重复 → 1 处）
2. `SELF_CLIENT_ID` 常量集中（4 处散落 → 1 处）
3. `_get_client_ip(request)` 去重（2 处 → 1 处）
4. `main.py` 产品列表构建逻辑去重
5. `business_client.py` 时间戳重复定义删除
6. `xinyi_platform/tests/` 空目录删除

**文档**:
- `docs/security-todos.md`：记录 3 个架构性安全改进的计划

### NOT in scope（留作 TODO）

| 项目 | 原因 |
|------|------|
| 分布式限流（Redis） | 需引入新依赖 + 部署成本，应有独立设计周期 |
| JWT 密钥轮换（kid header + 多密钥） | 较大架构改动，需评估对业务客户端的影响 |
| client_secret 派生算法改造 | HMAC(token, client_id) 是可接受的设计权衡，保护压在 registration_token 保密上 |
| OAuth PKCE 支持 | 功能增强而非 bug 修复，需评估与现有业务客户端的兼容性 |

## 执行策略

按风险和改动量分 4 批，每批可独立提交、测试、回滚：

```
批次 1 (快速安全修复)  ──→  批次 2 (CSRF 接入)  ──→  批次 3 (代码质量)  ──→  批次 4 (TODO 文档)
  5 项小改动               ~10 端点 + 模板          6 项纯重构              1 个文档
  独立测试                 依赖批次 3 的 _ui_ctx     现有测试验证            无测试
```

批次间有顺序依赖：批次 2 的 CSRF token 注入会修改模板上下文，与批次 3 的 `_ui_ctx` 去重有交集。为避免改两次模板，**批次 3 先于批次 2 执行**（`_ui_ctx` 去重后，CSRF token 注入到统一的上下文函数中）。

修正后的执行顺序：

```
批次 1 (快速安全修复)
   │
   ▼
批次 3 (代码质量：先去重 _ui_ctx 等共享逻辑)
   │
   ▼
批次 2 (CSRF 接入：在统一的上下文函数里注入 csrf_token)
   │
   ▼
批次 4 (TODO 文档)
```

## 详细设计

### 批次 1 — 快速安全修复

#### 1.1 registration_token 时序侧信道

**文件**: `xinyi_platform/auth/internal_auth.py`

**现状** (第 25 行):
```python
if not settings.registration_token or x_registration_token != settings.registration_token:
```

普通 `!=` 比较在字节不匹配时提前返回，存在时序侧信道。该 token 权限极高（可直接注册任意业务客户端并派生其 secret）。

**方案**:
```python
import secrets

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

`compare_digest` 要求两边类型一致（都 str 或都 bytes），上例中均为 str。

**测试**: 正确 token 通过；错误 token → 401；空 token → 401；registration_token 未配置 → 500。

#### 1.2 删除 SM4-ECB 死代码

**删除文件**:
- `xinyi_platform/crypto.py`（SM4-ECB 实现，ECB 模式本身不安全）
- `tests/unit/test_sm4.py`

**修改文件**:
- `xinyi_platform/config.py`：移除 `encryption_key` 配置项
- `.env` / `.env.example`：移除 `ENCRYPTION_KEY` 行
- `README.md`：移除 Quick Start 里生成 `ENCRYPTION_KEY` 的说明

**依据**: 全仓库生产代码零引用，仅测试覆盖。`encryption_key` 配置形同虚设。

#### 1.3 删除 oauth_state.py 死代码

**删除文件**:
- `xinyi_platform/auth/oauth_state.py`
- `tests/unit/test_oauth_state.py`

**依据**: `generate_oauth_state` / `sign_oauth_state` / `verify_oauth_state` 全仓库无生产调用方（仅测试引用）。其设计意图（授权服务器签名 state）与 OAuth2 标准冲突——state 由业务方生成和验证，授权服务器只负责原样回传。保留会误导后续维护者以为已有 CSRF 防护。

真正的授权端点 CSRF 防护是 PKCE，记录到批次 4 的 TODO 文档。

#### 1.4 session_secure 启动警告

**文件**: `xinyi_platform/startup.py`（或 `main.py` lifespan 内）

**方案**: 在应用启动阶段（lifespan 或 seed_admin 之后），检查 `settings.session_secure`：
```python
import logging
logger = logging.getLogger("xinyi_platform")

if not settings.session_secure:
    logger.warning(
        "SESSION_SECURE is False — session cookies will be transmitted over HTTP. "
        "Set XINYI_PLATFORM_SESSION_SECURE=true in production (HTTPS only)."
    )
```

**测试**: 单元测试验证 `session_secure=False` 时产生 WARNING 日志，`True` 时不产生。

#### 1.5 记录登录失败

**文件**: `xinyi_platform/api/login.py`

**现状**: 仅成功登录写 `LoginHistory`，`failure_reason` 字段从未被使用，暴力破解无审计痕迹。

**方案**: 现有成功登录直接用 `session.add(LoginHistory(...))` 写入（login.py:86、131），无独立 service。失败分支复用同一模式。

涉及两个端点的失败路径：
- `login_json`（`POST /login`，JSON）— 当前失败时直接 `raise HTTPException(401)`，需在 raise 前 add + commit。
- `login_form`（`POST /login/form`，表单）— 当前失败时返回模板，需在返回前 add + commit。

```python
# 失败分支（两个端点共用逻辑）
session.add(LoginHistory(
    user_id=user.id if user else None,   # 用户不存在时为 None（login_history 无 FK，已支持）
    ip_address=_get_client_ip(request),
    user_agent=request.headers.get("user-agent"),
    success=False,
    failure_reason=reason,  # "invalid_credentials" / "user_not_found" / "user_disabled"
))
await session.commit()
```

对外消息统一模糊（"用户名或密码错误"），不区分具体原因，防用户名枚举；但 `failure_reason` 内部记录精确原因供审计。

限流命中（429）不写 LoginHistory（限流器拒绝，未到认证逻辑）。

**测试**: 错误密码 → LoginHistory(success=False) 写入；正确密码 → success=True 写入（现有）；用户不存在 → 写入 user_id=None, failure_reason="user_not_found"；两个端点都覆盖。

---

### 批次 3 — 代码质量清理（先于批次 2 执行）

#### 3.1 _ui_ctx 去重

**现状**: `_ui_ctx(request)` 函数在 8 个 API 文件中逐字重复：login、register、password、me、admin_users、admin_clients、admin_audit、admin_login_history。

**方案**: 抽取到 `xinyi_platform/ui_common/install.py`（已有 `ui_jinja_globals` 函数，但路由未使用它），或新建 `xinyi_platform/api/_shared.py`。各路由改为 import 复用。

```python
# xinyi_platform/api/_shared.py
def build_template_context(request: Request) -> dict:
    """统一的模板上下文：UI globals + csrf_token。"""
    ctx = ui_jinja_globals(request)  # 复用现有
    ctx["csrf_token"] = request.cookies.get("xinyi_csrf", "")  # 批次 2 注入
    return ctx
```

注：函数名和具体结构在实现时确定，核心是消除 8 处重复并为 CSRF token 注入留好钩子。

#### 3.2 SELF_CLIENT_ID 常量集中

**现状**: `"xinyi-platform-self"` 字符串散落在 4 处：
- `api/login.py` (`SELF_CLIENT_ID`)
- `api/cas.py` (`SELF_CLIENT_ID`)
- `api/oauth.py` (`SELF_AUDIENCE`)
- `auth/dependencies.py`

**方案**: 在 `xinyi_platform/auth/session.py` 定义单一常量，各文件 import：
```python
# auth/session.py
SELF_AUDIENCE = "xinyi-platform-self"
```

#### 3.3 _get_client_ip 去重

**现状**: `_get_client_ip(request)` 在 `api/login.py` 与 `api/cas.py` 中重复。

**方案**: 抽到 `xinyi_platform/auth/` 下公共 util（如新建 `auth/request_util.py` 或并入现有模块）。

#### 3.4 main.py 产品列表逻辑去重

**现状**: lifespan 启动块（约 73-100 行）与 `_refresh_products`（约 112-135 行）几乎逐行相同。

**方案**: 抽取 `_build_products(session) -> list[dict]` 私有函数，两处共用。

#### 3.5 business_client.py 时间戳重复定义

**现状**: `created_at`/`updated_at` 在 `models/business_client.py` 第 38-43 行和 44-49 行定义了两遍，后者覆盖前者。

**方案**: 删除冗余的第二组定义，保留一组。

#### 3.6 删除空目录

`xinyi_platform/tests/` 仅含 `__pycache__`，无实际测试文件（测试在项目根 `tests/` 下）。删除整个目录。

---

### 批次 2 — CSRF 全面接入

#### 方案：Double-submit cookie

不需要服务端 session（当前架构是 JWT cookie，无 session store），适合本项目。

```
 GET 渲染表单页面                         POST 状态变更
         │                                     │
         ▼                                     ▼
 生成 csrf_token                         读 cookie: xinyi_csrf
 (secrets.token_urlsafe(32))            读提交值:
         │                                  - 表单: form.csrf_token
 设置 cookie:                             - JSON API: header X-CSRF-Token
   xinyi_csrf=token                      verify_csrf(cookie_val, submitted)
   (httponly=False,                      匹配 → 放行
    samesite=lax)                        不匹配 → 403
 注入模板上下文:
   csrf_token=token
         │
         ▼
 模板:
 <form method="post">
   <input type="hidden"
     name="csrf_token"
     value="{{ csrf_token }}">
 </form>
```

#### 改动点

**auth/csrf.py**:
- `verify_csrf(cookie_value, header_value)` 逻辑不变，参数语义文档化（第二个参数可来自 form field 或 header）。
- 新增 FastAPI 依赖函数：
  - `set_csrf_cookie(response) -> str`：生成 token 并设置 cookie，返回 token 供模板使用。
  - `verify_csrf_dependency(request, ...)`：从 cookie 和 form/header 读值，调用 `verify_csrf`，不匹配抛 403。

**受影响的 POST 端点**（表单类，用 hidden field）:
- `POST /xinyi/login/form`
- `POST /xinyi/register`
- `POST /xinyi/password/reset`
- `POST /xinyi/admin/users`（创建）
- `POST /xinyi/admin/users/{id}`（更新）
- `POST /xinyi/admin/users/{id}/delete`
- `POST /xinyi/admin/clients`（注册业务）
- `POST /xinyi/admin/clients/{id}/disable`、`/enable`

**受影响的 POST 端点**（JSON API 类，浏览器 JS 调用，用 header `X-CSRF-Token`）:
- `POST /xinyi/login`（JSON 登录，浏览器 fetch 调用，需防 login CSRF）
- `POST /xinyi/oauth/revoke`（浏览器可能调用的撤销端点）

**不需要 CSRF 的端点**:
- `POST /xinyi/internal/*`（server-to-server，X-Client-Secret 认证，非浏览器提交）
- `POST /xinyi/oauth/token`（标准 OAuth2 token 端点，client_secret 认证）

**GET 渲染表单的端点**（设置 csrf cookie + 注入上下文）:
- 所有返回 HTML 表单的 GET 端点（login、register、forgot_password、reset_password、admin 各表单页）。

**模板改动**（~10 个）:
- 所有 `<form method="post">` 内添加 `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`。
- 涉及：`login.html`、`register.html`、`forgot_password.html`、`reset_password.html`、`admin/user_form.html`、`admin/clients.html` 等。

#### 测试

- 无 csrf_token cookie → 403
- cookie 与表单值匹配 → 放行
- cookie 与表单值不匹配 → 403
- 只有 cookie 没有 form field → 403
- GET 请求不受影响（不校验 CSRF）
- JSON API 用 header `X-CSRF-Token` 正确时放行
- 内部 API 不受 CSRF 影响（无 token 也能通过，靠 X-Client-Secret）

---

### 批次 4 — 架构性 TODO 文档

新建 `docs/security-todos.md`，记录：

1. **分布式限流**: 当前 `InMemoryRateLimiter` 单进程内存，多 worker 部署计数失效。计划：引入 Redis 实现滑动窗口计数器，保留 InMemory 作为单进程 fallback。
2. **JWT 密钥轮换**: 当前所有业务共享单一 `jwt_secret`（HS256 对称密钥），任一泄露即全平台沦陷。计划：实现 kid（key ID）header + 多密钥列表，支持平滑轮换（新签发用新密钥，旧密钥仅验签）。
3. **client_secret 派生算法**: `HMAC(registration_token, client_id)` 确定性派生，算法公开。当前为可接受的设计权衡（保护压在 registration_token 保密上）。若未来需要更高安全性，改为每客户端独立随机 secret + 数据库存储。
4. **OAuth PKCE**: 授权码流程增强，防止授权码截获攻击。需评估与现有业务客户端（`ui_common/service_discovery.py`）的兼容性。

---

## 测试策略

| 批次 | 测试方式 |
|------|----------|
| 批次 1 | 每项新增单元测试（auth/internal_auth、startup、login 失败记录） |
| 批次 3 | 纯重构，现有测试全过即验证 |
| 批次 2 | 新增 CSRF 专项测试（`tests/api/test_csrf.py`），覆盖 403/放行/GET 不受影响 |
| 批次 4 | 无（文档） |

测试框架: pytest + pytest-asyncio（项目现有）。

运行命令: `uv run pytest`

## 风险

| 风险 | 缓解 |
|------|------|
| CSRF 接入后现有前端表单提交失败 | 模板改动全覆盖所有 POST 表单；测试覆盖每个端点 |
| `session_secure` 警告在开发环境噪音 | 仅启动时 WARNING 一次，不阻塞启动 |
| 删除 `encryption_key` 配置影响现有部署 | 该配置零引用，删除后旧 .env 多余行被忽略（pydantic-settings 默认忽略未定义的 env） |
| 登录失败记录增加 DB 写入 | login_history 表无 FK、无高频写入，性能影响可忽略 |
