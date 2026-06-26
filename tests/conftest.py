import os

os.environ.setdefault("XINYI_PLATFORM_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("XINYI_PLATFORM_JWT_SECRET", "test-secret-with-at-least-32-characters!!")
os.environ.setdefault("XINYI_PLATFORM_ADMIN_PASSWORD", "test-admin-pwd-123")

import pytest


@pytest.fixture
def settings():
    from xinyi_platform.config import Settings
    return Settings()


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    from xinyi_platform.middleware.rate_limit import (
        login_limiter, password_reset_limiter, register_limiter,
    )
    for limiter in (login_limiter, register_limiter, password_reset_limiter):
        limiter._buckets.clear()
    yield
    for limiter in (login_limiter, register_limiter, password_reset_limiter):
        limiter._buckets.clear()
