import asyncio
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class InMemoryRateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = asyncio.Lock()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from headers (CF-Connecting-IP, X-Forwarded-For) or client host."""
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP is the original client
            parts = forwarded.split(",")
            return parts[0].strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Exempt health check and documentation endpoints from rate limiting
        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        current_time = time.time()
        window_start = current_time - self.window_seconds

        async with self.lock:
            # Clean expired timestamps for this IP
            self.requests[client_ip] = [
                ts for ts in self.requests[client_ip] if ts > window_start
            ]

            if len(self.requests[client_ip]) >= self.max_requests:
                # Calculate retry after
                oldest_ts = self.requests[client_ip][0]
                retry_after = max(1, int(self.window_seconds - (current_time - oldest_ts)))

                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Too many requests. Maximum {self.max_requests} requests per minute allowed.",
                            "details": {"retry_after_seconds": retry_after},
                        },
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            # Record this request
            self.requests[client_ip].append(current_time)

        return await call_next(request)
