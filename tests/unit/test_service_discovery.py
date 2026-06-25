import hashlib
import hmac
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from xinyi_platform.ui_common.service_discovery import (
    derive_client_secret,
    register_self,
    fetch_active_clients,
    build_product_list,
)


def test_derive_client_secret_deterministic():
    token = "test-registration-token-1234567890"
    client_id = "hm-prod"
    s1 = derive_client_secret(token, client_id)
    s2 = derive_client_secret(token, client_id)
    assert s1 == s2
    assert len(s1) > 30


def test_derive_client_secret_different_client_ids():
    token = "test-registration-token-1234567890"
    s1 = derive_client_secret(token, "hm-prod")
    s2 = derive_client_secret(token, "docupipe-prod")
    assert s1 != s2


def test_derive_client_secret_matches_hmac_formula():
    token = "my-token"
    client_id = "hm-prod"
    expected = base64.urlsafe_b64encode(
        hmac.new(token.encode(), client_id.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    assert derive_client_secret(token, client_id) == expected


async def test_register_self_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "registered"}
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await register_self(
            platform_url="http://xinyi:8000/xinyi",
            registration_token="tok",
            client_metadata={"client_id": "hm-prod", "name": "HM"},
        )
    assert result is True


async def test_register_self_platform_down_returns_false():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await register_self(
            platform_url="http://xinyi:8000/xinyi",
            registration_token="tok",
            client_metadata={"client_id": "hm-prod"},
        )
    assert result is False


async def test_fetch_active_clients_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"clients": [
        {"client_id": "hm-prod", "name": "HM", "base_url": "http://hm:8001", "home_path": "/dashboard", "description": "RAG"},
    ]}
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_active_clients(
            platform_url="http://xinyi:8000/xinyi",
            client_id="hm-prod",
            client_secret="secret",
        )
    assert len(result) == 1
    assert result[0]["client_id"] == "hm-prod"


async def test_fetch_active_clients_platform_down_returns_empty():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await fetch_active_clients(
            platform_url="http://xinyi:8000/xinyi",
            client_id="hm-prod",
            client_secret="secret",
        )
    assert result == []


def test_build_product_list_includes_platform_first():
    clients = [
        {"client_id": "hm-prod", "name": "HM", "base_url": "http://hm:8001", "home_path": "/dashboard", "description": "RAG"},
    ]
    products = build_product_list(
        clients,
        platform_url="http://xinyi:8000/xinyi",
        self_client_id="hm-prod",
        self_name="Hindsight Manager",
        self_home_path="/dashboard",
    )
    assert products[0]["id"] == "platform"
    assert products[0]["kind"] == "platform"
    assert products[0]["is_current"] is False


def test_build_product_list_marks_current_service():
    clients = [
        {"client_id": "hm-prod", "name": "HM", "base_url": "http://hm:8001", "home_path": "/dashboard", "description": "RAG"},
        {"client_id": "docupipe-prod", "name": "DM", "base_url": "http://dm:8002", "home_path": "/projects", "description": "Pipe"},
    ]
    products = build_product_list(
        clients,
        platform_url="http://xinyi:8000/xinyi",
        self_client_id="hm-prod",
        self_name="Hindsight Manager",
        self_home_path="/dashboard",
    )
    hm = [p for p in products if p["id"] == "hm-prod"][0]
    dm = [p for p in products if p["id"] == "docupipe-prod"][0]
    assert hm["is_current"] is True
    assert dm["is_current"] is False


def test_build_product_list_platform_self_is_current():
    products = build_product_list(
        [],
        platform_url="http://xinyi:8000/xinyi",
        self_client_id="platform",
        self_name="平台",
        self_home_path="/account",
    )
    assert products[0]["id"] == "platform"
    assert products[0]["is_current"] is True
