import bcrypt
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.models.business_client import BusinessClient, ClientStatus


class ClientConflictError(Exception):
    pass


class BusinessClientService:
    @staticmethod
    async def register(
        session: AsyncSession,
        *,
        client_id: str,
        name: str,
        redirect_uris: list[str],
        logout_url: str | None = None,
    ) -> tuple[BusinessClient, str]:
        existing = await session.execute(
            select(BusinessClient).where(BusinessClient.client_id == client_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ClientConflictError(f"client_id {client_id!r} already registered")

        raw_secret = secrets.token_urlsafe(32)
        secret_hash = bcrypt.hashpw(raw_secret.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")
        client = BusinessClient(
            client_id=client_id,
            name=name,
            client_secret_hash=secret_hash,
            redirect_uris=redirect_uris,
            logout_url=logout_url,
            status=ClientStatus.ACTIVE,
        )
        session.add(client)
        await session.flush()
        return client, raw_secret

    @staticmethod
    async def verify_secret(session: AsyncSession, client_id: str, raw_secret: str) -> BusinessClient | None:
        result = await session.execute(
            select(BusinessClient).where(BusinessClient.client_id == client_id)
        )
        client = result.scalar_one_or_none()
        if client is None or client.status != ClientStatus.ACTIVE:
            return None
        try:
            if not bcrypt.checkpw(raw_secret.encode("utf-8"), client.client_secret_hash.encode("ascii")):
                return None
        except (ValueError, TypeError):
            return None
        return client

    @staticmethod
    async def verify_redirect_uri(session: AsyncSession, client_id: str, redirect_uri: str) -> bool:
        result = await session.execute(
            select(BusinessClient).where(BusinessClient.client_id == client_id)
        )
        client = result.scalar_one_or_none()
        if client is None:
            return False
        return redirect_uri in (client.redirect_uris or [])

    @staticmethod
    async def set_status(session: AsyncSession, client_id: str, status: ClientStatus) -> None:
        result = await session.execute(
            select(BusinessClient).where(BusinessClient.client_id == client_id)
        )
        client = result.scalar_one_or_none()
        if client is not None:
            client.status = status
            client.updated_at = datetime.now(timezone.utc)

    @staticmethod
    async def register_or_update(
        session: AsyncSession,
        *,
        client_id: str,
        name: str,
        client_secret_hash: str,
        redirect_uris: list[str],
        logout_url: str | None = None,
        base_url: str | None = None,
        home_path: str | None = None,
        description: str | None = None,
    ) -> BusinessClient:
        """Idempotent upsert: creates if absent, updates metadata if present.

        client_secret_hash is only set on INSERT, never overwritten on UPDATE.
        """
        result = await session.execute(
            select(BusinessClient).where(BusinessClient.client_id == client_id)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.name = name
            existing.redirect_uris = redirect_uris
            existing.logout_url = logout_url
            existing.base_url = base_url
            existing.home_path = home_path
            existing.description = description
            existing.last_seen_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return existing

        client = BusinessClient(
            client_id=client_id,
            name=name,
            client_secret_hash=client_secret_hash,
            redirect_uris=redirect_uris,
            logout_url=logout_url,
            base_url=base_url,
            home_path=home_path,
            description=description,
            last_seen_at=datetime.now(timezone.utc),
            status=ClientStatus.ACTIVE,
        )
        session.add(client)
        await session.flush()
        return client
