import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert "docs_url" in data
    assert "endpoints" in data
    assert "health" in data["endpoints"]
    assert "extract" in data["endpoints"]
    assert "formats" in data["endpoints"]


@pytest.mark.asyncio
async def test_docs_availability(client: AsyncClient):
    docs_resp = await client.get("/docs")
    assert docs_resp.status_code == 200
    assert "swagger" in docs_resp.text.lower() or "html" in docs_resp.headers.get("content-type", "")

    openapi_resp = await client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert "openapi" in schema
    assert "/health" in schema["paths"]
    assert "/extract" in schema["paths"]
    assert "/extract/formats" in schema["paths"]
