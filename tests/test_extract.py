import asyncio
from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient
import yt_dlp.utils

from app.config import settings


@pytest.mark.asyncio
async def test_extract_success(client: AsyncClient, mock_video_info):
    with patch("app.services.extractor.MediaExtractor._extract_sync", return_value=mock_video_info):
        with patch("app.services.ssrf_validator.validate_url_security"):
            response = await client.post(
                "/extract",
                json={"url": "https://example.com/watch?v=mock123", "format": "best"},
            )
            assert response.status_code == 200
            data = response.json()

            # Verify response schema and structure
            assert data["success"] is True
            assert data["title"] == "Big Buck Bunny - Animated Short Film"
            assert data["duration"] == 596.0
            assert data["extractor"] == "youtube"
            assert data["original_url"] == "https://example.com/watch?v=mock123"
            assert data["media_url"] == "https://stream.example.com/video/master.m3u8"
            assert data["format_id"] == "22"
            assert data["resolution"] == "1920x1080"
            assert data["has_video"] is True
            assert data["has_audio"] is True
            assert data["is_video_only"] is False
            assert data["is_audio_only"] is False

            # Verify format items and stream separation
            formats = data["formats"]
            assert len(formats) == 3

            # Format 140 (audio only)
            audio_fmt = next(f for f in formats if f["format_id"] == "140")
            assert audio_fmt["has_audio"] is True
            assert audio_fmt["has_video"] is False
            assert audio_fmt["is_audio_only"] is True
            assert audio_fmt["is_video_only"] is False

            # Format 137 (video only)
            video_fmt = next(f for f in formats if f["format_id"] == "137")
            assert video_fmt["has_video"] is True
            assert video_fmt["has_audio"] is False
            assert video_fmt["is_video_only"] is True
            assert video_fmt["is_audio_only"] is False

            # Format 22 (combined)
            combined_fmt = next(f for f in formats if f["format_id"] == "22")
            assert combined_fmt["has_video"] is True
            assert combined_fmt["has_audio"] is True
            assert combined_fmt["is_video_only"] is False
            assert combined_fmt["is_audio_only"] is False

            # Verify header sanitization: Authorization must be stripped
            assert "http_headers" in data
            if data["http_headers"]:
                assert "Authorization" not in data["http_headers"]
                assert "authorization" not in data["http_headers"]


@pytest.mark.asyncio
async def test_extract_unsupported_url(client: AsyncClient):
    with patch(
        "app.services.extractor.MediaExtractor._extract_sync",
        side_effect=yt_dlp.utils.UnsupportedError("Unsupported URL"),
    ):
        with patch("app.services.ssrf_validator.validate_url_security"):
            response = await client.post(
                "/extract",
                json={"url": "https://unsupported-unknown-website.com/page"},
            )
            assert response.status_code == 422
            data = response.json()
            assert data["success"] is False
            assert data["error"]["code"] == "UNSUPPORTED_URL"


@pytest.mark.asyncio
async def test_extract_media_unavailable(client: AsyncClient):
    with patch(
        "app.services.extractor.MediaExtractor._extract_sync",
        side_effect=yt_dlp.utils.UnavailableVideoError("Video unavailable"),
    ):
        with patch("app.services.ssrf_validator.validate_url_security"):
            response = await client.post(
                "/extract",
                json={"url": "https://example.com/watch?v=deleted_video"},
            )
            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False
            assert data["error"]["code"] == "MEDIA_UNAVAILABLE"


@pytest.mark.asyncio
async def test_extract_upstream_rate_limit(client: AsyncClient):
    with patch(
        "app.services.extractor.MediaExtractor._extract_sync",
        side_effect=yt_dlp.utils.DownloadError("HTTP Error 429: Too Many Requests"),
    ):
        with patch("app.services.ssrf_validator.validate_url_security"):
            response = await client.post(
                "/extract",
                json={"url": "https://example.com/watch?v=ratelimited"},
            )
            assert response.status_code == 429
            data = response.json()
            assert data["success"] is False
            assert data["error"]["code"] == "UPSTREAM_RATE_LIMITED"


@pytest.mark.asyncio
async def test_extract_timeout_handling(client: AsyncClient):
    async def slow_extract(*args, **kwargs):
        await asyncio.sleep(1.0)

    with patch.object(settings, "EXTRACTION_TIMEOUT_SECONDS", 0.05):
        with patch("app.services.extractor.asyncio.to_thread", side_effect=slow_extract):
            with patch("app.services.ssrf_validator.validate_url_security"):
                response = await client.post(
                    "/extract",
                    json={"url": "https://example.com/watch?v=slow"},
                )
                assert response.status_code == 504
                data = response.json()
                assert data["success"] is False
                assert data["error"]["code"] == "EXTRACTION_TIMEOUT"


@pytest.mark.asyncio
async def test_extract_unexpected_exception_never_exposes_traceback(client: AsyncClient):
    with patch(
        "app.services.extractor.MediaExtractor._extract_sync",
        side_effect=RuntimeError("Secret internal database connection string failed at /var/secrets"),
    ):
        with patch("app.services.ssrf_validator.validate_url_security"):
            response = await client.post(
                "/extract",
                json={"url": "https://example.com/watch?v=crash"},
            )
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert data["error"]["code"] in ("INTERNAL_SERVER_ERROR", "EXTRACTION_FAILED")
            # Traceback or secret info must never leak
            assert "/var/secrets" not in response.text
            assert "Traceback" not in response.text
