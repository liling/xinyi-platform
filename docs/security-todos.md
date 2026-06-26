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
