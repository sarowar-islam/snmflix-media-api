import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_request_size_limit_exceeded(client: AsyncClient):
    # Simulate an oversized request with Content-Length header exceeding settings.MAX_REQUEST_BODY_SIZE
    huge_length = str(settings.MAX_REQUEST_BODY_SIZE + 1024)
    headers = {"Content-Length": huge_length}

    response = await client.post("/extract", content=b"{}", headers=headers)
    assert response.status_code == 413
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "REQUEST_ENTITY_TOO_LARGE"
