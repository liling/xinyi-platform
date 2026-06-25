# business_clients URL 存储重构设计

## 背景与目标

`business_clients` 表中，`redirect_uris` 和 `logout_url` 目前存储完整 URL（如 `http://localhost:8001/hindsight/auth/callback`）。这导致：

- 管理页面表格过宽
- 更换域名/端口时需逐字段修改
- 与 `base_url` + `home_path`（已存相对路径）的约定不一致

**目标**：`base_url` 是唯一的完整 URL 来源，其余地址字段（`redirect_uris`、`logout_url`、`home_path`）统一存储相对路径，使用时由 `base_url` 拼接。

## 涉及项目

- **xinyi-platform** — 数据迁移、OAuth 匹配、SLO 登出、管理页面
- **hindsight-manager** — 注册参数、配置项、OAuth 流程发起
- **docupipe-manager** — 同 hindsight-manager

## 存储约定（不改表结构）

| 字段 | 存储格式 | 示例 |
|------|----------|------|
| `base_url` | 完整 URL | `http://localhost:8001/hindsight` |
| `home_path` | 相对路径 | `/dashboard` |
| `redirect_uris` | 相对路径列表 | `["/auth/callback"]` |
| `logout_url` | 相对路径 | `/auth/logout` |

**拼接规则**：使用时 `f"{base_url}{相对路径}"`。

## 方案：迁移脚本一刀切

写一个 Alembic 数据迁移，遍历所有 `business_clients`，将 `redirect_uris` 和 `logout_url` 中以各自 `base_url` 开头的完整 URL 截掉前缀。代码端只认相对路径，不做兼容判断。

部署顺序：先部署 xinyi-platform 新版 → 跑迁移 → 重启 → 再升级各业务服务。

## xinyi-platform 改动

### 1. 数据迁移

新增 Alembic 迁移 `006_relative_client_urls.py`：
- 遍历 `business_clients` 所有记录
- 对每条记录的 `redirect_uris` 数组中每个元素：如果以该记录的 `base_url` 开头，截掉前缀
- 对 `logout_url`：同样截掉 `base_url` 前缀
- `base_url` 和 `home_path` 不变

### 2. OAuth authorize 匹配

`api/oauth.py` 的 `authorize` 端点：

```python
# 旧
if redirect_uri not in (client.redirect_uris or []):

# 新
full_uris = [f"{client.base_url}{u}" for u in (client.redirect_uris or [])]
if redirect_uri not in full_uris:
```

### 3. verify_redirect_uri

`services/business_client_service.py` 的 `verify_redirect_uri`：

```python
# 旧
return redirect_uri in (client.redirect_uris or [])

# 新
full_uris = [f"{client.base_url}{u}" for u in (client.redirect_uris or [])]
return redirect_uri in full_uris
```

### 4. SLO 登出

`api/logout.py` 的 `_render_slo_page`：

```python
# 旧
logout_urls = [c.logout_url for c in result.scalars().all() if c.logout_url]

# 新
logout_urls = [
    f"{c.base_url}{c.logout_url}"
    for c in result.scalars().all()
    if c.logout_url
]
```

### 5. 管理页面

`templates/admin/clients.html` 的表单 placeholder 改为相对路径示例：
- redirect_uris: `/auth/callback`
- logout_url: `/auth/logout`

## 业务服务改动

### hindsight-manager

**`main.py` 注册参数：**

```python
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

**`config.py` 配置项默认值：**

```python
# 旧
oauth_redirect_uri: str = "http://localhost:8001/hindsight/auth/callback"

# 新
oauth_redirect_uri: str = "/auth/callback"
```

**`api/auth.py` OAuth 流程发起：**

发起授权请求时，拼上 base_url 再传给平台：

```python
full_redirect_uri = f"{settings.base_url}/hindsight{settings.oauth_redirect_uri}"
```

涉及 `api/auth.py` 中所有使用 `settings.oauth_redirect_uri` 作为完整 URL 的位置，以及 `platform/config.py` 和 `platform/client.py` 中 `exchange_oauth_code` 传入的 `redirect_uri`。

### docupipe-manager

同 hindsight-manager，路径前缀改为 `/docupipe`。

**`main.py` 注册参数：**

```python
client_metadata={
    "client_id": settings.oauth_client_id,
    "name": "DocuPipe Manager",
    "base_url": f"{settings.base_url}/docupipe",
    "redirect_uris": ["/auth/callback"],
    "logout_url": "/auth/logout",
    "home_path": "/projects",
    "description": "文档流水线",
},
```

**`config.py` 配置项默认值：**

```python
oauth_redirect_uri: str = "/auth/callback"
```

**`api/auth.py`** 同样拼接 base_url。

## 部署顺序

1. 部署 xinyi-platform 新版（含迁移脚本）
2. 执行 `alembic upgrade head` 跑迁移
3. 重启 xinyi-platform
4. 升级 hindsight-manager / docupipe-manager 并重启

## 成功标准

- 迁移后 `business_clients` 表中 `redirect_uris` 和 `logout_url` 均为相对路径
- OAuth 授权流程正常（redirect_uri 匹配成功）
- SLO 登出正常（iframe 加载正确的完整 logout_url）
- 管理页面显示相对路径，表格不再过宽
- 产品切换器跳转正常（base_url + home_path 拼接）
- 三个项目均可正常启动和注册
