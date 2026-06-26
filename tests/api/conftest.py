import pytest
from fastapi.testclient import TestClient

from xinyi_platform.main import app


@pytest.fixture
def client():
    return TestClient(app)
