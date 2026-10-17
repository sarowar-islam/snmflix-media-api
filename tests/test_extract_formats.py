from unittest.mock import patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_extract_formats_success(client: AsyncClient, mock_video_info):
    with patch("app.services.extractor.MediaExtractor._extract_sync", return_value=mock_video_info):
        with patch("app.services.ssrf_validator.validate_url_security"):
            response = await client.post(
                "/extract/formats",
                json={"url": "https://example.com/watch?v=mock123"},
            )
            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["title"] == "Big Buck Bunny - Animated Short Film"
            assert data["extractor"] == "youtube"
            assert data["original_url"] == "https://example.com/watch?v=mock123"
            assert data["format_count"] == 3
            assert len(data["formats"]) == 3

            # Check format attributes
            f0 = data["formats"][0]
            assert "format_id" in f0
            assert "has_video" in f0
            assert "has_audio" in f0
            assert "is_video_only" in f0
            assert "is_audio_only" in f0

            # Verify no internal yt-dlp debug fields are exposed
            for fmt in data["formats"]:
                assert "downloader_options" not in fmt
                assert "http_headers" not in fmt
                assert "_filename" not in fmt
