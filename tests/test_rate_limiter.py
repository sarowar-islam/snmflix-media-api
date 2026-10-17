from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.main import app
from app.middleware.rate_limiter import InMemoryRateLimiterMiddleware


@pytest.mark.asyncio
async def test_rate_limiter_exceeded(client: AsyncClient, mock_video_info):
    # Find the rate limiter middleware on app
    rate_limiter = None
    for middleware in app.user_middleware:
        if middleware.cls == InMemoryRateLimiterMiddleware:
            # Note: Starlette app wraps middlewares in app.middleware_stack
            pass

    # Direct test by temporarily resetting rate limiter instance limit to 3
    # Let's locate the running middleware instance from app
    limiter_instance = None
    curr = app.middleware_stack
    while curr:
        if isinstance(curr, InMemoryRateLimiterMiddleware):
            limiter_instance = curr
            break
        curr = getattr(curr, "app", None)

    if limiter_instance:
        original_max = limiter_instance.max_requests
        limiter_instance.max_requests = 3
        limiter_instance.requests.clear()

        try:
            with patch("app.services.extractor.MediaExtractor._extract_sync", return_value=mock_video_info):
                with patch("app.services.ssrf_validator.validate_url_security"):
                    # First 3 requests should pass
                    for _ in range(3):
                        res = await client.post("/extract", json={"url": "https://example.com/v1"})
                        assert res.status_code == 200

                    # 4th request must be rate limited
                    res_blocked = await client.post("/extract", json={"url": "https://example.com/v1"})
                    assert res_blocked.status_code == 429
                    assert "Retry-After" in res_blocked.headers
                    data = res_blocked.json()
                    assert data["success"] is False
                    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        finally:
            limiter_instance.max_requests = original_max
            limiter_instance.requests.clear()
