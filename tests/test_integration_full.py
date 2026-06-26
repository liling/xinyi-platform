from fastapi.testclient import TestClient

from xinyi_platform.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/xinyi/health")
    assert response.status_code == 200


def test_openapi_lists_all_routes():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = [
        "/xinyi/login", "/xinyi/login/form", "/xinyi/logout", "/xinyi/me", "/xinyi/account",
        "/xinyi/register", "/xinyi/password/forgot", "/xinyi/password/reset",
        "/xinyi/cas/login", "/xinyi/cas/callback",
        "/xinyi/oauth/authorize", "/xinyi/oauth/token", "/xinyi/oauth/revoke",
        "/xinyi/oauth/userinfo",
        "/xinyi/internal/users/batch-get",
        "/xinyi/internal/notifications/email",
        "/xinyi/internal/audit",
        "/xinyi/internal/auth/check-revocation",
        "/xinyi/admin/users", "/xinyi/admin/clients",
        "/xinyi/admin/audit-logs", "/xinyi/admin/login-history",
        "/xinyi/health",
    ]
    for path in expected:
        assert any(p.startswith(path) for p in paths.keys()), f"Missing route starting with {path}"
