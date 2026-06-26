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


def decode_access_token(token: str, secret: str, audience: str) -> dict:
    return jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        audience=audience,
        issuer=ISSUER,
    )


def generate_refresh_token() -> str:
    import secrets
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
