"""Shared auto-registration and service discovery for xinyi-platform business clients."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging

import httpx

logger = logging.getLogger(__name__)


def derive_client_secret(registration_token: str, client_id: str) -> str:
    """Derive a deterministic client_secret from registration token + client_id."""
    raw = hmac.new(
        registration_token.encode(),
        client_id.encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


async def register_self(
    platform_url: str,
    registration_token: str,
    client_metadata: dict,
) -> bool:
    """POST /internal/clients/register to register this service.

    Returns True on success, False on failure (never raises).
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{platform_url}/internal/clients/register",
                json=client_metadata,
                headers={"X-Registration-Token": registration_token},
            )
            if resp.status_code >= 400:
                logger.warning("register_self failed: %s %s", resp.status_code, resp.text[:200])
                return False
            logger.info("registered with platform as %s", client_metadata.get("client_id"))
            return True
    except Exception as e:
        logger.warning("register_self error: %s", e)
        return False


async def fetch_active_clients(
    platform_url: str,
    client_id: str,
    client_secret: str,
) -> list[dict]:
    """GET /internal/clients/active to discover all registered services.

    Returns list of client dicts, or empty list on failure (never raises).
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{platform_url}/internal/clients/active",
                headers={
                    "X-Client-Id": client_id,
                    "X-Client-Secret": client_secret,
                },
            )
            if resp.status_code >= 400:
                logger.warning("fetch_active_clients failed: %s", resp.status_code)
                return []
            data = resp.json()
            return data.get("clients", [])
    except Exception as e:
        logger.warning("fetch_active_clients error: %s", e)
        return []


def build_product_list(
    active_clients: list[dict],
    *,
    platform_url: str,
    self_client_id: str,
    self_name: str,
    self_home_path: str,
) -> list[dict]:
    """Assemble the product switcher list.

    Platform is always first. Each business client follows, with is_current flag.
    """
    products: list[dict] = []

    is_platform_current = self_client_id == "platform"
    products.append({
        "id": "platform",
        "label": "平台账户中心",
        "subtitle": "用户 · 审计 · 登录历史",
        "url": f"{platform_url}/account",
        "kind": "platform",
        "is_current": is_platform_current,
    })

    for c in active_clients:
        products.append({
            "id": c["client_id"],
            "label": c.get("name", c["client_id"]),
            "subtitle": c.get("description", ""),
            "url": f"{c['base_url']}{c.get('home_path', '')}",
            "kind": "business",
            "is_current": c["client_id"] == self_client_id,
        })

    return products
