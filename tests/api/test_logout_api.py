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


def test_logout_get_clears_cookie_but_does_not_revoke():
    """GET should delete session cookie but not require CSRF."""
    client = TestClient(app)
    response = client.get("/xinyi/logout", follow_redirects=False)
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert "xinyi_session=" in cookie_header
    assert "退出" in response.text


# Payload that breaks out of a JS double-quoted string if rendered raw.
# `xXx` is a sentinel we can still find after escaping; `";alert` is the break-out.
_XSS_PAYLOAD = 'xXx";alert(1337);//'


def test_logout_get_return_to_not_reflected_as_xss():
    """return_to must not break out of the <script> JS string context.

    Regression for the reflective XSS caused by rendering return_to into
    logout.html's <script> block without JSON-encoding it.
    """
    client = TestClient(app)
    response = client.get(
        "/xinyi/logout", params={"return_to": _XSS_PAYLOAD}, follow_redirects=False
    )
    assert response.status_code == 200
    # The sentinel is still rendered (so the redirect target survives), ...
    assert "xXx" in response.text
    # ... but the break-out sequence must not appear unescaped.
    assert 'xXx";alert' not in response.text
    assert "xXx';alert" not in response.text


def test_logout_post_return_to_not_reflected_as_xss():
    """POST form's return_to must not break out of the <script> JS string context."""
    client = TestClient(app)
    app.dependency_overrides[verify_csrf_token] = _noop_csrf
    try:
        response = client.post(
            "/xinyi/logout",
            data={"return_to": _XSS_PAYLOAD},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "xXx" in response.text
        assert 'xXx";alert' not in response.text
        assert "xXx';alert" not in response.text
    finally:
        app.dependency_overrides.clear()
