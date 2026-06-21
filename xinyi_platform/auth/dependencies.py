from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError

from xinyi_platform.auth.session import decode_access_token
from xinyi_platform.config import Settings

SELF_CLIENT_ID = "xinyi-platform-self"


def _get_settings() -> Settings:
    return Settings()


def _extract_token(cookie_token: Optional[str], authorization: Optional[str]) -> Optional[str]:
    if cookie_token:
        return cookie_token
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def get_current_user(
    xinyi_session: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(_get_settings),
) -> dict:
    token = _extract_token(xinyi_session, authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token, settings.jwt_secret, audience=SELF_CLIENT_ID)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return {
        "id": payload["sub"],
        "username": payload["username"],
        "role": payload["role"],
    }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
