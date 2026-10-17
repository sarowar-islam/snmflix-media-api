from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_api_key_enforcement(client: AsyncClient, mock_video_info):
    # Set API Key in settings
    settings.API_KEY = "test-secret-key-12345"

    try:
        # 1. Extraction request without header must fail with 401
        res_no_key = await client.post(
            "/extract",
            json={"url": "https://example.com/watch?v=123"},
        )
        assert res_no_key.status_code == 401
        assert "api key" in res_no_key.json()["error"]["message"].lower()

        # 2. Extraction request with invalid key must fail with 401
        res_bad_key = await client.post(
            "/extract",
            json={"url": "https://example.com/watch?v=123"},
            headers={"X-API-Key": "wrong-token"},
        )
        assert res_bad_key.status_code == 401

        # 3. Extraction request with correct key succeeds
        with patch("app.services.extractor.MediaExtractor._extract_sync", return_value=mock_video_info):
            with patch("app.services.ssrf_validator.validate_url_security"):
                res_good_key = await client.post(
                    "/extract",
                    json={"url": "https://example.com/watch?v=123"},
                    headers={"X-API-Key": "test-secret-key-12345"},
                )
                assert res_good_key.status_code == 200
                assert res_good_key.json()["success"] is True

        # 4. Health and root endpoints remain accessible without API Key
        health_res = await client.get("/health")
        assert health_res.status_code == 200

        root_res = await client.get("/")
        assert root_res.status_code == 200

    finally:
        # Reset settings
        settings.API_KEY = None
