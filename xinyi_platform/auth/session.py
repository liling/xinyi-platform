import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt

ALGORITHM = "HS256"
ISSUER = "xinyi-platform"
SELF_AUDIENCE = "xinyi-platform-self"


def create_access_token(
    *,
    sub: str,
    username: str,
    role: str,
    client_id: str,
    secret: str,
    ttl_seconds: int,
) -> str:
    """Create a JWT access token.

    audience (aud) is set to client_id.
    - Session tokens (cookie): client_id=SELF_AUDIENCE → aud="xinyi-platform-self"
    - OAuth tokens: client_id=<business_client_id> → aud=<client_id>
    """
    now = datetime.now(timezone.utc)
    payload = {
        "iss": ISSUER,
        "sub": sub,
        "aud": client_id,
        "username": username,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_session_token(
    *,
    sub: str,
    username: str,
    role: str,
    secret: str,
    ttl_seconds: int,
) -> str:
    """Session token (cookie), aud = SELF_AUDIENCE."""
    return create_access_token(
        sub=sub, username=username, role=role,
        client_id=SELF_AUDIENCE, secret=secret, ttl_seconds=ttl_seconds,
    )


def decode_access_token(token: str, secret: str, audience: str) -> dict:
    return jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        audience=audience,
        issuer=ISSUER,
    )


def decode_session_token(token: str, secret: str) -> dict:
    """Decode and verify a session token (aud must match SELF_AUDIENCE)."""
    return decode_access_token(token, secret, audience=SELF_AUDIENCE)


def decode_token_skip_audience(token: str, secret: str) -> dict:
    """Decode and verify a token without checking audience.

    Use for the /oauth/userinfo endpoint where the access token's
    audience is a business client_id, not SELF_AUDIENCE.
    """
    return jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        options={"verify_aud": False},
    )


def generate_refresh_token() -> str:
    import secrets
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
