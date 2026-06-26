import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from xinyi_platform.auth.csrf import generate_csrf_token, verify_csrf


def test_verify_csrf_matching():
    token = generate_csrf_token()
    assert verify_csrf(token, token) is True


def test_verify_csrf_mismatch():
    assert verify_csrf("token-a", "token-b") is False


def test_verify_csrf_empty():
    assert verify_csrf("", "") is False
    assert verify_csrf("token", "") is False
    assert verify_csrf("", "token") is False


from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from xinyi_platform.middleware.csrf import CsrfMiddleware, verify_csrf_token


def _make_test_app():
    app = FastAPI()
    app.add_middleware(CsrfMiddleware)

    @app.get("/form-page")
    async def form_page(request):
        from starlette.responses import HTMLResponse
        token = getattr(request.state, "csrf_token", "")
        return HTMLResponse(f'<form method="post"><input name="csrf_token" value="{token}"></form>')

    @app.post("/submit")
    async def submit(_=Depends(verify_csrf_token)):
        return {"ok": True}

    return app


def test_get_sets_csrf_cookie():
    app = _make_test_app()
    client = TestClient(app)
    resp = client.get("/form-page")
    assert "xinyi_csrf" in resp.cookies


def test_post_without_token_rejected():
    app = _make_test_app()
    client = TestClient(app)
    client.get("/form-page")
    resp = client.post("/submit", data={})
    assert resp.status_code == 403


def test_post_with_matching_token_accepted():
    app = _make_test_app()
    client = TestClient(app)
    resp_get = client.get("/form-page")
    token = resp_get.cookies["xinyi_csrf"]
    resp = client.post("/submit", data={"csrf_token": token})
    assert resp.status_code == 200


def test_post_with_mismatched_token_rejected():
    app = _make_test_app()
    client = TestClient(app)
    client.get("/form-page")
    resp = client.post("/submit", data={"csrf_token": "wrong"})
    assert resp.status_code == 403
