import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
import yt_dlp
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    UnavailableVideoError,
    UnsupportedError,
)

from app.config import settings
from app.schemas.extract import ExtractFormatsResponse, ExtractResponse, FormatMetadata
from app.services import ssrf_validator

logger = logging.getLogger(__name__)


class MediaExtractionException(Exception):
    """Base exception for media extraction failures."""
    def __init__(self, message: str, status_code: int = 502, code: str = "EXTRACTION_FAILED"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


# Alias for backward-compatibility
MediaExtractionError = MediaExtractionException


class UnsupportedURLError(MediaExtractionException):
    """Raised when the URL or site is not supported by any extractor."""
    def __init__(self, message: str = "The requested URL is not supported by any available extractor"):
        super().__init__(message, status_code=422, code="UNSUPPORTED_URL")


class MediaUnavailableError(MediaExtractionException):
    """Raised when the media is private, deleted, or otherwise inaccessible."""
    def __init__(self, message: str = "The requested media is unavailable, private, or removed"):
        super().__init__(message, status_code=404, code="MEDIA_UNAVAILABLE")


class ExtractionTimeoutError(MediaExtractionException):
    """Raised when the extraction exceeds the allowed timeout limit."""
    def __init__(self, message: str = "Media extraction timed out"):
        super().__init__(message, status_code=504, code="EXTRACTION_TIMEOUT")


class ExtractionRateLimitError(MediaExtractionException):
    """Raised when the upstream service rate-limits requests."""
    def __init__(self, message: str = "The upstream media provider has rate-limited requests"):
        super().__init__(message, status_code=429, code="UPSTREAM_RATE_LIMITED")


class MediaExtractor:
    def __init__(self):
        # Bound concurrency across the entire process
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_EXTRACTIONS)

    def _build_ydl_options(self, format_preference: Optional[str] = None) -> Dict[str, Any]:
        """Build safe yt-dlp execution options preventing downloads, writes, and unsafe behaviors."""
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "simulate": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
            "ignoreconfig": True,
            "no_color": True,
            "socket_timeout": settings.EXTRACTION_TIMEOUT_SECONDS,
            "retries": 1,
            "fragment_retries": 1,
            "logger": None,
        }
        if format_preference:
            ydl_opts["format"] = format_preference
        return ydl_opts

    def _parse_format(self, fmt: Dict[str, Any]) -> FormatMetadata:
        """Parse and sanitize a raw yt-dlp format dictionary into a structured model."""
        vcodec = fmt.get("vcodec")
        acodec = fmt.get("acodec")

        has_video = bool(vcodec and vcodec.lower() != "none")
        has_audio = bool(acodec and acodec.lower() != "none")
        is_video_only = has_video and not has_audio
        is_audio_only = has_audio and not has_video

        # Check resolution
        resolution = fmt.get("resolution")
        width = fmt.get("width")
        height = fmt.get("height")
        if not resolution and width and height:
            resolution = f"{width}x{height}"

        # Sanitize URL if present
        raw_url = fmt.get("url")
        media_url = None
        if raw_url and isinstance(raw_url, str):
            clean_url = raw_url.strip()
            if clean_url.startswith("http://") or clean_url.startswith("https://"):
                media_url = clean_url

        return FormatMetadata(
            format_id=str(fmt.get("format_id", "unknown")),
            format_note=fmt.get("format_note"),
            ext=fmt.get("ext"),
            resolution=resolution,
            width=width,
            height=height,
            fps=fmt.get("fps"),
            vcodec=vcodec if vcodec != "none" else None,
            acodec=acodec if acodec != "none" else None,
            filesize=fmt.get("filesize"),
            filesize_approx=fmt.get("filesize_approx"),
            tbr=fmt.get("tbr"),
            vbr=fmt.get("vbr"),
            abr=fmt.get("abr"),
            has_video=has_video,
            has_audio=has_audio,
            is_video_only=is_video_only,
            is_audio_only=is_audio_only,
            protocol=fmt.get("protocol"),
            url=media_url,
        )

    def _sanitize_http_headers(self, raw_headers: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """Sanitize HTTP headers, keeping safe playback headers while removing secrets."""
        if not raw_headers or not isinstance(raw_headers, dict):
            return None

        safe_header_names = {
            "user-agent",
            "referer",
            "origin",
            "accept",
            "accept-language",
            "sec-fetch-mode",
            "sec-fetch-site",
            "sec-fetch-dest",
        }
        sanitized: Dict[str, str] = {}
        for k, v in raw_headers.items():
            if isinstance(k, str) and k.lower() in safe_header_names and isinstance(v, (str, int)):
                sanitized[k] = str(v)
        return sanitized if sanitized else None

    def _map_ytdlp_exception(self, e: Exception) -> MediaExtractionException:
        """Map any exception to a typed MediaExtractionException."""
        if isinstance(e, MediaExtractionException):
            return e
        if isinstance(e, UnsupportedError):
            return UnsupportedURLError("The requested URL is not supported by any available extractor")
        if isinstance(e, (UnavailableVideoError, GeoRestrictedError)):
            return MediaUnavailableError("The requested media is unavailable, private, or removed")
        if isinstance(e, ExtractorError):
            msg = str(e).lower()
            if "private" in msg or "sign in" in msg or "login" in msg:
                return MediaUnavailableError("The media is private or requires authentication")
            if "unsupported" in msg:
                return UnsupportedURLError("The URL is not supported by this extractor")
            return MediaExtractionException("Extraction error from media provider", status_code=502)
        if isinstance(e, DownloadError):
            msg = str(e).lower()
            if "unsupported url" in msg or "is not a valid url" in msg:
                return UnsupportedURLError("Unsupported or unrecognized media page URL")
            if "private video" in msg or "sign in" in msg:
                return MediaUnavailableError("The requested media is private or requires authentication")
            if "video unavailable" in msg or "404" in msg or "not found" in msg:
                return MediaUnavailableError("The media was not found or is unavailable")
            if "rate limit" in msg or "429" in msg or "too many requests" in msg:
                return ExtractionRateLimitError("The media provider is currently rate-limiting requests")
            return MediaExtractionException("Failed to retrieve media information from provider", status_code=502)

        logger.error(f"Unexpected error during media extraction: {type(e).__name__}")
        return MediaExtractionException("An unexpected error occurred during media extraction", status_code=500)

    def _extract_sync(self, url: str, format_preference: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous yt-dlp execution run inside a worker thread."""
        opts = self._build_ydl_options(format_preference)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise MediaUnavailableError("No media information could be extracted from this URL")
                return info
        except Exception as e:
            raise self._map_ytdlp_exception(e) from e

    async def extract_media(self, url: str, format_preference: Optional[str] = None) -> ExtractResponse:
        """Asynchronously extract media information with concurrency limits and timeouts."""
        # 1. Validate URL security against SSRF
        ssrf_validator.validate_url_security(url)

        # 2. Acquire concurrency semaphore
        async with self.semaphore:
            try:
                info = await asyncio.wait_for(
                    asyncio.to_thread(self._extract_sync, url, format_preference),
                    timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as e:
                raise ExtractionTimeoutError(
                    f"Extraction timed out after {settings.EXTRACTION_TIMEOUT_SECONDS} seconds"
                ) from e
            except MediaExtractionException:
                raise
            except Exception as e:
                raise self._map_ytdlp_exception(e) from e

        # 3. Format extraction response
        raw_formats = info.get("formats", [])
        parsed_formats: List[FormatMetadata] = []
        for fmt in raw_formats:
            if isinstance(fmt, dict):
                parsed_formats.append(self._parse_format(fmt))

        # Limit returned formats
        truncated_formats = parsed_formats[: settings.MAX_FORMATS_RETURNED]

        # Extract selected stream properties
        vcodec = info.get("vcodec")
        acodec = info.get("acodec")
        has_video = bool(vcodec and vcodec.lower() != "none") if vcodec else None
        has_audio = bool(acodec and acodec.lower() != "none") if acodec else None
        is_video_only = (has_video and not has_audio) if (has_video is not None and has_audio is not None) else None
        is_audio_only = (has_audio and not has_video) if (has_video is not None and has_audio is not None) else None

        # Resolution
        resolution = info.get("resolution")
        width = info.get("width")
        height = info.get("height")
        if not resolution and width and height:
            resolution = f"{width}x{height}"

        # Selected media URL
        media_url = None
        raw_url = info.get("url")
        if raw_url and isinstance(raw_url, str):
            clean_url = raw_url.strip()
            if clean_url.startswith("http://") or clean_url.startswith("https://"):
                media_url = clean_url

        # If direct url not at root of info, pick from the best format that has a URL
        if not media_url and truncated_formats:
            # Prefer combined format with url, else any format with url
            for fmt in reversed(truncated_formats):
                if fmt.url:
                    if fmt.has_video and fmt.has_audio:
                        media_url = fmt.url
                        vcodec = fmt.vcodec
                        acodec = fmt.acodec
                        has_video = True
                        has_audio = True
                        is_video_only = False
                        is_audio_only = False
                        resolution = fmt.resolution or resolution
                        break
                    elif not media_url:
                        media_url = fmt.url
                        vcodec = fmt.vcodec
                        acodec = fmt.acodec
                        has_video = fmt.has_video
                        has_audio = fmt.has_audio
                        is_video_only = fmt.is_video_only
                        is_audio_only = fmt.is_audio_only
                        resolution = fmt.resolution or resolution

        return ExtractResponse(
            success=True,
            title=info.get("title"),
            duration=float(info.get("duration")) if info.get("duration") is not None else None,
            thumbnail=info.get("thumbnail"),
            extractor=str(info.get("extractor", "generic")),
            original_url=url,
            media_url=media_url,
            format_id=str(info.get("format_id")) if info.get("format_id") else None,
            resolution=resolution,
            vcodec=vcodec if vcodec != "none" else None,
            acodec=acodec if acodec != "none" else None,
            has_video=has_video,
            has_audio=has_audio,
            is_video_only=is_video_only,
            is_audio_only=is_audio_only,
            is_live=info.get("is_live"),
            http_headers=self._sanitize_http_headers(info.get("http_headers")),
            formats=truncated_formats,
        )

    async def extract_formats(self, url: str) -> ExtractFormatsResponse:
        """Asynchronously extract and return available formats list."""
        ssrf_validator.validate_url_security(url)

        async with self.semaphore:
            try:
                info = await asyncio.wait_for(
                    asyncio.to_thread(self._extract_sync, url, None),
                    timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as e:
                raise ExtractionTimeoutError(
                    f"Extraction timed out after {settings.EXTRACTION_TIMEOUT_SECONDS} seconds"
                ) from e
            except MediaExtractionException:
                raise
            except Exception as e:
                raise self._map_ytdlp_exception(e) from e

        raw_formats = info.get("formats", [])
        parsed_formats: List[FormatMetadata] = []
        for fmt in raw_formats:
            if isinstance(fmt, dict):
                parsed_formats.append(self._parse_format(fmt))

        truncated_formats = parsed_formats[: settings.MAX_FORMATS_RETURNED]

        return ExtractFormatsResponse(
            success=True,
            title=info.get("title"),
            extractor=str(info.get("extractor", "generic")),
            original_url=url,
            format_count=len(truncated_formats),
            formats=truncated_formats,
        )


extractor_service = MediaExtractor()
