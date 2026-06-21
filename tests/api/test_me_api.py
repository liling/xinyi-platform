from fastapi.testclient import TestClient

from xinyi_platform.auth.session import create_access_token
from xinyi_platform.config import Settings
from xinyi_platform.main import app


def _token(role: str = "admin"):
    s = Settings()
    return create_access_token(
        sub="u-1", username="alice", role=role,
        client_id="xinyi-platform-self",
        secret=s.jwt_secret, ttl_seconds=900,
    )


def test_me_without_token_returns_401():
    client = TestClient(app)
    response = client.get("/me")
    assert response.status_code == 401


def test_me_with_valid_token_returns_user():
    client = TestClient(app)
    response = client.get("/me", cookies={"xinyi_session": _token()})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
