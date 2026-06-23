import secrets as pysecrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.session import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from xinyi_platform.config import Settings
from xinyi_platform.models.oauth_code import OAuthCode
from xinyi_platform.models.refresh_token import RefreshToken
from xinyi_platform.models.token_revocation import TokenRevocation
from xinyi_platform.models.user import User
from xinyi_platform.services.business_client_service import BusinessClientService


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    user_info: dict


class OAuthService:
    @staticmethod
    async def generate_code(
        session: AsyncSession,
        *,
        client_id: str,
        user_id: uuid.UUID,
        redirect_uri: str,
        scope: str | None,
        ttl_seconds: int,
    ) -> str:
        code = pysecrets.token_urlsafe(32)
        oauth_code = OAuthCode(
            code=code,
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scope=scope,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        session.add(oauth_code)
        await session.flush()
        return code

    @staticmethod
    async def _lookup_code(session: AsyncSession, code: str) -> OAuthCode | None:
        result = await session.execute(select(OAuthCode).where(OAuthCode.code == code))
        oc = result.scalar_one_or_none()
        if oc is None:
            return None
        if oc.used_at is not None:
            return None
        if oc.expires_at < datetime.now(timezone.utc):
            return None
        return oc

    @staticmethod
    async def exchange_code(
        session: AsyncSession,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        settings: Settings,
    ) -> TokenPair | None:
        client = await BusinessClientService.verify_secret(session, client_id, client_secret)
        if client is None:
            return None
        if not await BusinessClientService.verify_redirect_uri(session, client_id, redirect_uri):
            return None

        oc = await OAuthService._lookup_code(session, code)
        if oc is None or oc.client_id != client_id or oc.redirect_uri != redirect_uri:
            return None

        user = await session.get(User, oc.user_id)
        if user is None or not user.is_active:
            return None

        oc.used_at = datetime.now(timezone.utc)

        return await OAuthService._issue_token_pair(
            session, user=user, client_id=client_id, settings=settings
        )

    @staticmethod
    async def _issue_token_pair(
        session: AsyncSession,
        *,
        user: User,
        client_id: str,
        settings: Settings,
    ) -> TokenPair:
        access = create_access_token(
            sub=str(user.id),
            username=user.username,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            client_id=client_id,
            secret=settings.jwt_secret,
            ttl_seconds=settings.access_token_ttl_seconds,
        )
        raw_refresh = generate_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            client_id=client_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
        )
        session.add(refresh)
        await session.flush()

        return TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=settings.access_token_ttl_seconds,
            user_info={
                "id": str(user.id),
                "username": user.username,
                "display_name": user.display_name,
                "email": user.email,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            },
        )

    @staticmethod
    async def refresh(
        session: AsyncSession,
        *,
        refresh_token_raw: str,
        client_id: str,
        client_secret: str,
        settings: Settings,
    ) -> TokenPair | None:
        client = await BusinessClientService.verify_secret(session, client_id, client_secret)
        if client is None:
            return None

        token_hash = hash_refresh_token(refresh_token_raw)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt is None or rt.revoked_at is not None:
            return None
        if rt.expires_at < datetime.now(timezone.utc):
            return None
        if rt.client_id != client_id:
            return None

        if await OAuthService.is_user_revoked(session, rt.user_id):
            return None

        user = await session.get(User, rt.user_id)
        if user is None or not user.is_active:
            return None

        rt.revoked_at = datetime.now(timezone.utc)
        return await OAuthService._issue_token_pair(
            session, user=user, client_id=client_id, settings=settings
        )

    @staticmethod
    async def revoke_refresh_token(session: AsyncSession, refresh_token_raw: str) -> None:
        token_hash = hash_refresh_token(refresh_token_raw)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt is not None and rt.revoked_at is None:
            rt.revoked_at = datetime.now(timezone.utc)

    @staticmethod
    async def revoke_all_for_user(
        session: AsyncSession, user_id: uuid.UUID, reason: str
    ) -> None:
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        now = datetime.now(timezone.utc)
        for rt in result.scalars().all():
            rt.revoked_at = now

        revocation = TokenRevocation(
            jti=str(uuid.uuid4()),
            user_id=user_id,
            reason=reason,
            expires_at=now + timedelta(seconds=900),
        )
        session.add(revocation)

    @staticmethod
    async def is_user_revoked(session: AsyncSession, user_id: uuid.UUID) -> bool:
        result = await session.execute(
            select(TokenRevocation).where(
                TokenRevocation.user_id == user_id,
                TokenRevocation.expires_at >= datetime.now(timezone.utc),
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def clear_revocation(session: AsyncSession, user_id: uuid.UUID) -> None:
        await session.execute(
            delete(TokenRevocation).where(TokenRevocation.user_id == user_id)
        )
