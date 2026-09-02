import pytest
from unittest.mock import patch
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock database and Redis connection attempts during app startup."""
    with patch("main.init_db_pool"), patch("main.close_db_pool"), patch("main.close_redis"):
        yield

@pytest.mark.asyncio
async def test_health_check():
    """Test that the application boots and health check is accessible."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
        
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
