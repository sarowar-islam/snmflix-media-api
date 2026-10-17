import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == settings.APP_VERSION
    assert "timestamp" in data
    assert isinstance(data["timestamp"], (int, float))
    assert data["timestamp"] > 0
