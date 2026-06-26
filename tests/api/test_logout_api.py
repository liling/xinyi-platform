from fastapi.testclient import TestClient

from xinyi_platform.main import app
from xinyi_platform.middleware.csrf import verify_csrf_token


async def _noop_csrf():
    pass


def test_logout_clears_cookie():
    client = TestClient(app)
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        response = client.post("/xinyi/logout", follow_redirects=False)
        assert response.status_code == 200
        cookie_header = response.headers.get("set-cookie", "")
        assert "xinyi_session" in cookie_header
        assert "退出" in response.text
    finally:
        app.dependency_overrides.clear()


def test_logout_get_renders_page():
    client = TestClient(app)
    response = client.get("/xinyi/logout", follow_redirects=False)
    assert response.status_code == 200
    assert "退出" in response.text


def test_logout_get_does_not_clear_cookie():
    """GET should only render page, not clear session."""
    client = TestClient(app)
    response = client.get("/xinyi/logout", follow_redirects=False)
    cookie_header = response.headers.get("set-cookie", "")
    assert "xinyi_session=;" not in cookie_header
    assert "xinyi_session=" not in cookie_header
