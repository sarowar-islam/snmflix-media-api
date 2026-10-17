import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_wildcard_origin(client: AsyncClient):
    headers = {
        "Origin": "https://watch.melopee.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,X-API-Key",
    }
    response = await client.options("/extract", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://watch.melopee.app"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_any_origin(client: AsyncClient):
    headers = {
        "Origin": "https://any-arbitrary-domain.com",
        "Access-Control-Request-Method": "POST",
    }
    response = await client.options("/extract", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://any-arbitrary-domain.com"
