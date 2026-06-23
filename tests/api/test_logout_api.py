from fastapi.testclient import TestClient

from xinyi_platform.main import app


def test_logout_clears_cookie():
    client = TestClient(app)
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"
    cookie_header = response.headers.get("set-cookie", "")
    assert "xinyi_session" in cookie_header


def test_logout_get_redirects():
    client = TestClient(app)
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
