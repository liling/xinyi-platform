from fastapi.testclient import TestClient

from xinyi_platform.main import app


def test_logout_clears_cookie():
    client = TestClient(app)
    response = client.post("/xinyi/logout", follow_redirects=False)
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert "xinyi_session" in cookie_header
    assert "退出" in response.text


def test_logout_get_renders_page():
    client = TestClient(app)
    response = client.get("/xinyi/logout", follow_redirects=False)
    assert response.status_code == 200
    assert "退出" in response.text
