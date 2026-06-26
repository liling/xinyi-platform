from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.session import SELF_AUDIENCE, decode_access_token
from xinyi_platform.config import Settings
from xinyi_platform.db import get_session_or_none
from xinyi_platform.services.oauth_service import OAuthService


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
    response: Response = None,
    session: AsyncSession | None = Depends(get_session_or_none),
) -> dict:
    token = _extract_token(xinyi_session, authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token, settings.jwt_secret, audience=SELF_AUDIENCE)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    import uuid
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        return {
            "id": payload["sub"],
            "username": payload.get("username", ""),
            "role": payload.get("role", ""),
        }

    if session is not None and await OAuthService.is_user_revoked(session, user_id):
        response.delete_cookie("xinyi_session", path="/")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")

    return {
        "id": payload["sub"],
        "username": payload["username"],
        "role": payload["role"],
    }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
