import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from xinyi_platform.auth.password import hash_password
from xinyi_platform.config import Settings
from xinyi_platform.models.user import AuthProvider, User, UserRole

logger = logging.getLogger(__name__)


async def seed_admin_if_absent(session: AsyncSession, settings: Settings) -> None:
    """If no admin user exists, create one with configured username + password."""
    if not settings.admin_password:
        logger.warning("ADMIN_PASSWORD not set, skipping admin seeding")
        return
    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        logger.info("Admin user already exists, skipping seeding")
        return
    admin = User(
        username=settings.admin_username,
        display_name="Administrator",
        email=None,
        password_hash=hash_password(settings.admin_password),
        auth_provider=AuthProvider.LOCAL,
        role=UserRole.ADMIN,
    )
    session.add(admin)
    await session.commit()
    logger.info("Seeded admin user %r", settings.admin_username)
