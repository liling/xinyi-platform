import os

os.environ.setdefault("XINYI_PLATFORM_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("XINYI_PLATFORM_JWT_SECRET", "test-secret-with-at-least-32-characters!!")
os.environ.setdefault("XINYI_PLATFORM_ENCRYPTION_KEY", "00112233445566778899aabbccddeeff")
os.environ.setdefault("XINYI_PLATFORM_ADMIN_PASSWORD", "test-admin-pwd-123")

import pytest


@pytest.fixture
def settings():
    from xinyi_platform.config import Settings
    return Settings()
