import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_allowed_origin(client: AsyncClient):
    headers = {
        "Origin": "https://snmflix.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,X-API-Key",
    }
    response = await client.options("/extract", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://snmflix.vercel.app"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_disallowed_origin(client: AsyncClient):
    headers = {
        "Origin": "https://unauthorized-malicious-site.com",
        "Access-Control-Request-Method": "POST",
    }
    response = await client.options("/extract", headers=headers)
    # Disallowed origin will not receive access-control-allow-origin matching the origin
    assert response.headers.get("access-control-allow-origin") != "https://unauthorized-malicious-site.com"
