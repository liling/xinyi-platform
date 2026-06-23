from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from xinyi_platform.config import Settings


def create_engine(settings: Settings):
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )


def create_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Override via dependency_overrides in tests."""
    from xinyi_platform.main import app_state
    factory = app_state.session_factory
    async with factory() as session:
        yield session


async def get_session_or_none() -> AsyncIterator[AsyncSession | None]:
    """Like get_session but returns None when the DB is not available.

    Use in shared dependencies (e.g. get_current_user) so that endpoints
    in standalone-test apps don't require DB setup.
    """
    try:
        from xinyi_platform.main import app_state
    except Exception:
        yield None
        return
    factory = getattr(app_state, "session_factory", None)
    if factory is None:
        yield None
        return
    async with factory() as session:
        yield session
