from fastapi.testclient import TestClient

from xinyi_platform.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_openapi_lists_all_routes():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = [
        "/login", "/login/form", "/logout", "/me", "/account",
        "/register", "/password/forgot", "/password/reset",
        "/cas/login", "/cas/callback",
        "/oauth/authorize", "/oauth/token", "/oauth/revoke",
        "/internal/users/batch-get",
        "/internal/notifications/email",
        "/internal/audit",
        "/internal/auth/check-revocation",
        "/admin/users", "/admin/clients",
        "/admin/audit-logs", "/admin/login-history",
        "/health",
    ]
    for path in expected:
        assert any(p.startswith(path) for p in paths.keys()), f"Missing route starting with {path}"
