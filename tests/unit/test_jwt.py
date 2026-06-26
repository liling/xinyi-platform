import pytest
from jose import JWTError

from xinyi_platform.auth.session import (
    create_access_token,
    create_session_token,
    decode_access_token,
    decode_session_token,
    decode_token_skip_audience,
    generate_refresh_token,
    hash_refresh_token,
)

SECRET = "test-secret-with-at-least-32-characters!!"


def test_create_access_token_has_correct_claims():
    token = create_access_token(
        sub="user-uuid-123",
        username="alice",
        role="admin",
        client_id="hm-prod",
        secret=SECRET,
        ttl_seconds=900,
    )
    payload = decode_access_token(token, SECRET, audience="hm-prod")
    assert payload["sub"] == "user-uuid-123"
    assert payload["username"] == "alice"
    assert payload["role"] == "admin"
    assert payload["aud"] == "hm-prod"
    assert payload["iss"] == "xinyi-platform"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "jti" in payload


def test_decode_access_token_wrong_audience():
    token = create_access_token(
        sub="u1", username="x", role="user", client_id="hm-prod",
        secret=SECRET, ttl_seconds=900,
    )
    with pytest.raises(JWTError):
        decode_access_token(token, SECRET, audience="other-client")


def test_decode_access_token_expired():
    token = create_access_token(
        sub="u1", username="x", role="user", client_id="hm-prod",
        secret=SECRET, ttl_seconds=-10,
    )
    with pytest.raises(JWTError):
        decode_access_token(token, SECRET, audience="hm-prod")


def test_decode_access_token_wrong_secret():
    token = create_access_token(
        sub="u1", username="x", role="user", client_id="hm-prod",
        secret=SECRET, ttl_seconds=900,
    )
    with pytest.raises(JWTError):
        decode_access_token(token, "wrong-secret", audience="hm-prod")


def test_create_session_token_has_self_audience():
    token = create_session_token(sub="u1", username="x", role="user", secret=SECRET, ttl_seconds=900)
    payload = decode_session_token(token, SECRET)
    assert payload["aud"] == "xinyi-platform-self"
    assert payload["iss"] == "xinyi-platform"
    assert payload["type"] == "access"


def test_decode_session_token_rejects_other_audience():
    token = create_access_token(
        sub="u1", username="x", role="user", client_id="hm-prod",
        secret=SECRET, ttl_seconds=900,
    )
    with pytest.raises(JWTError):
        decode_session_token(token, SECRET)


def test_decode_token_skip_audience_accepts_any_aud():
    token = create_access_token(
        sub="u1", username="x", role="user", client_id="hm-prod",
        secret=SECRET, ttl_seconds=900,
    )
    payload = decode_token_skip_audience(token, SECRET)
    assert payload["sub"] == "u1"
    assert payload["aud"] == "hm-prod"


def test_generate_refresh_token_format():
    t = generate_refresh_token()
    assert isinstance(t, str)
    assert len(t) >= 32
    assert generate_refresh_token() != t


def test_hash_refresh_token_deterministic():
    t = generate_refresh_token()
    h1 = hash_refresh_token(t)
    h2 = hash_refresh_token(t)
    assert h1 == h2
    assert h1 != t
