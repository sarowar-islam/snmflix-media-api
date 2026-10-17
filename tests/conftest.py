import asyncio
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_video_info() -> Dict[str, Any]:
    """Sample realistic mock yt-dlp extract_info output with combined and split streams."""
    return {
        "id": "mock123",
        "title": "Big Buck Bunny - Animated Short Film",
        "duration": 596.0,
        "thumbnail": "https://images.example.com/thumbnails/mock123.jpg",
        "extractor": "youtube",
        "extractor_key": "Youtube",
        "webpage_url": "https://example.com/watch?v=mock123",
        "url": "https://stream.example.com/video/master.m3u8",
        "format_id": "22",
        "resolution": "1920x1080",
        "width": 1920,
        "height": 1080,
        "vcodec": "avc1.640028",
        "acodec": "mp4a.40.2",
        "fps": 30.0,
        "is_live": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://example.com/",
            "Authorization": "Bearer secret-token-should-be-stripped",
        },
        "formats": [
            {
                "format_id": "140",
                "format_note": "audio only",
                "ext": "m4a",
                "resolution": "audio only",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "abr": 128.0,
                "tbr": 128.0,
                "filesize": 9540000,
                "url": "https://stream.example.com/audio/140.m4a",
                "protocol": "https",
            },
            {
                "format_id": "137",
                "format_note": "1080p video only",
                "ext": "mp4",
                "resolution": "1920x1080",
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "vbr": 4500.0,
                "tbr": 4500.0,
                "filesize": 335000000,
                "url": "https://stream.example.com/video/137.mp4",
                "protocol": "https",
            },
            {
                "format_id": "22",
                "format_note": "720p combined",
                "ext": "mp4",
                "resolution": "1280x720",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "vcodec": "avc1.4d401f",
                "acodec": "mp4a.40.2",
                "tbr": 2200.0,
                "filesize": 165000000,
                "url": "https://stream.example.com/video/22.mp4",
                "protocol": "https",
            },
        ],
    }


@pytest.fixture
async def client():
    """Async test client using httpx."""
    # Reset default test settings
    original_api_key = settings.API_KEY
    original_cors = settings.CORS_ORIGINS
    settings.API_KEY = None
    settings.CORS_ORIGINS = ["https://snmflix.vercel.app", "http://localhost:3000"]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    # Restore settings
    settings.API_KEY = original_api_key
    settings.CORS_ORIGINS = original_cors
