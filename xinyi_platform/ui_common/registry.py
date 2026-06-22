"""Global product registry used by the product switcher in the topbar.

`url_template` uses `{platform_url}` / `{manager_url}` placeholders that
`install_ui` substitutes with concrete URLs at app startup.
"""
from __future__ import annotations

PRODUCTS: list[dict] = [
    {
        "id": "platform",
        "label": "平台账户中心",
        "subtitle": "用户 · 审计 · 登录历史",
        "kind": "platform",
        "url_template": "{platform_url}/account",
    },
    {
        "id": "hindsight-manager",
        "label": "Hindsight",
        "subtitle": "RAG 记忆库",
        "kind": "business",
        "url_template": "{manager_url}/dashboard",
    },
]
