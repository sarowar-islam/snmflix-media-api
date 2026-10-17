import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Verify the X-API-Key header against the configured API_KEY setting.
    If API_KEY is set in settings, enforce strict authentication.
    If API_KEY is not configured and REQUIRE_API_KEY is False, permit requests for local development.
    """
    configured_key = settings.API_KEY

    # If an API key is set, enforce it strictly
    if configured_key:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key. Provide a valid 'X-API-Key' header.",
            )
        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(api_key, configured_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key. Access denied.",
            )
        return api_key

    # If REQUIRE_API_KEY is true but no key configured on the server
    if settings.REQUIRE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication configuration error: API_KEY is required but not set.",
        )

    # Safe development default: permit requests if no key is configured
    return api_key
