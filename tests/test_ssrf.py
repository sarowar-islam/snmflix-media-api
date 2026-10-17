import pytest
from httpx import AsyncClient

from app.services.ssrf_validator import (
    InvalidURLError,
    SSRFSecurityError,
    validate_url_security,
)


@pytest.mark.parametrize(
    "forbidden_url",
    [
        "http://localhost:8000/video",
        "http://127.0.0.1:8000/media",
        "http://127.0.1.1:8000",
        "http://0.0.0.0:8000",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/stream",
        "http://10.255.255.255/stream",
        "http://192.168.1.1/stream",
        "http://172.16.0.1/stream",
        "http://172.31.255.255/stream",
        "http://100.64.0.1/stream",
        "http://[::1]/stream",
        "http://[fe80::1]/stream",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data/latest/meta-data/",
        "http://my-service.local/video",
        "http://server.internal/video",
        "http://user:password@example.com/video",
    ],
)
def test_ssrf_validator_blocks_forbidden_urls(forbidden_url: str):
    with pytest.raises(SSRFSecurityError):
        validate_url_security(forbidden_url)


@pytest.mark.parametrize(
    "invalid_scheme_url",
    [
        "file:///etc/passwd",
        "ftp://example.com/media.mp4",
        "gopher://example.com/",
        "data:text/html,Hello",
        "javascript:alert(1)",
    ],
)
def test_ssrf_validator_blocks_invalid_schemes(invalid_scheme_url: str):
    with pytest.raises((SSRFSecurityError, InvalidURLError, ValueError)):
        validate_url_security(invalid_scheme_url)


@pytest.mark.asyncio
async def test_extract_endpoint_rejects_ssrf(client: AsyncClient):
    response = await client.post(
        "/extract",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "SSRF_VIOLATION"


@pytest.mark.asyncio
async def test_extract_endpoint_rejects_localhost(client: AsyncClient):
    response = await client.post(
        "/extract",
        json={"url": "http://localhost:3000/media"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "SSRF_VIOLATION"


@pytest.mark.asyncio
async def test_extract_endpoint_rejects_non_http_scheme(client: AsyncClient):
    response = await client.post(
        "/extract",
        json={"url": "file:///etc/shadow"},
    )
    assert response.status_code == 422 or response.status_code == 400
    data = response.json()
    assert data["success"] is False
