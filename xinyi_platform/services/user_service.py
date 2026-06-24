import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.password import (
    PasswordStrengthError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from xinyi_platform.models.user import AuthProvider, User, UserRole


class UsernameConflictError(Exception):
    pass


class UserService:
    @staticmethod
    async def create_user(
        session: AsyncSession,
        *,
        username: str,
        password: str,
        email: str | None,
        display_name: str,
        provider: AuthProvider,
        role: UserRole = UserRole.USER,
    ) -> User:
        validate_password_strength(password)
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none() is not None:
            raise UsernameConflictError(f"Username {username!r} already exists")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            auth_provider=provider,
            role=role,
        )
        session.add(user)
        await session.flush()
        return user

    @staticmethod
    async def authenticate_local(session: AsyncSession, username: str, password: str) -> User | None:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        if not user.password_hash or not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def get_by_username(session: AsyncSession, username: str) -> User | None:
        result = await session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await session.get(User, user_id)

    @staticmethod
    async def batch_get(
        session: AsyncSession,
        user_ids: list[uuid.UUID],
        fields: list[str] | None = None,
    ) -> dict[uuid.UUID, dict]:
        if not user_ids:
            return {}
        if len(user_ids) > 100:
            raise ValueError("batch_get supports up to 100 ids")
        result = await session.execute(select(User).where(User.id.in_(user_ids)))
        users = result.scalars().all()
        out = {}
        for u in users:
            out[u.id] = {
                "id": str(u.id),
                "username": u.username,
                "display_name": u.display_name,
                "email": u.email,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_active": u.is_active,
            }
        return out

    @staticmethod
    async def change_password(session: AsyncSession, user_id: uuid.UUID, new_password: str) -> None:
        validate_password_strength(new_password)
        user = await session.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        user.password_hash = hash_password(new_password)

    @staticmethod
    async def update_last_login(session: AsyncSession, user_id: uuid.UUID) -> None:
        from datetime import datetime, timezone
        user = await session.get(User, user_id)
        if user is not None:
            user.last_login_at = datetime.now(timezone.utc)

    @staticmethod
    async def search(
        session: AsyncSession,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        stmt = select(User).where(
            (User.username.ilike(f"%{query}%"))
            | (User.display_name.ilike(f"%{query}%"))
            | (User.email.ilike(f"%{query}%"))
        ).limit(limit)
        result = await session.execute(stmt)
        users = result.scalars().all()
        return [
            {
                "id": str(u.id),
                "username": u.username,
                "display_name": u.display_name,
                "email": u.email,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_active": u.is_active,
            }
            for u in users
        ]

    @staticmethod
    async def soft_delete(session: AsyncSession, user_id: uuid.UUID) -> None:
        user = await session.get(User, user_id)
        if user is not None:
            user.is_active = False
