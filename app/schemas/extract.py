from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class ExtractRequest(BaseModel):
    url: str = Field(..., description="The media page URL to extract from")
    format: Optional[str] = Field(
        default=None,
        description="Optional format selector or preference (e.g. 'best', 'bestvideo+bestaudio/best', 'mp4')",
        max_length=100,
    )

    @field_validator("url")
    @classmethod
    def validate_url_string(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL is too long (maximum 2048 characters)")
        return v

    @field_validator("format")
    @classmethod
    def sanitize_format_preference(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        # Disallow dangerous characters that might be used if passed improperly
        disallowed_chars = {";", "&", "|", "`", "$", "<", ">", "\n", "\r"}
        if any(c in v for c in disallowed_chars):
            raise ValueError("Invalid format parameter containing forbidden characters")
        return v if v else None


class ExtractFormatsRequest(BaseModel):
    url: str = Field(..., description="The media page URL to list formats for")

    @field_validator("url")
    @classmethod
    def validate_url_string(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL is too long (maximum 2048 characters)")
        return v


class FormatMetadata(BaseModel):
    format_id: str = Field(..., description="Identifier for this format stream")
    format_note: Optional[str] = Field(default=None, description="Quality or stream note")
    ext: Optional[str] = Field(default=None, description="File container extension (e.g. mp4, webm, m4a)")
    resolution: Optional[str] = Field(default=None, description="Resolution string (e.g. 1920x1080)")
    width: Optional[int] = Field(default=None, description="Video width in pixels")
    height: Optional[int] = Field(default=None, description="Video height in pixels")
    fps: Optional[float] = Field(default=None, description="Frames per second")
    vcodec: Optional[str] = Field(default=None, description="Video codec name")
    acodec: Optional[str] = Field(default=None, description="Audio codec name")
    filesize: Optional[int] = Field(default=None, description="Exact file size in bytes, if known")
    filesize_approx: Optional[int] = Field(default=None, description="Approximate file size in bytes")
    tbr: Optional[float] = Field(default=None, description="Total bitrate in kbps")
    vbr: Optional[float] = Field(default=None, description="Video bitrate in kbps")
    abr: Optional[float] = Field(default=None, description="Audio bitrate in kbps")
    has_video: bool = Field(default=False, description="True if format contains video")
    has_audio: bool = Field(default=False, description="True if format contains audio")
    is_video_only: bool = Field(default=False, description="True if format has video but no audio stream")
    is_audio_only: bool = Field(default=False, description="True if format has audio but no video stream")
    protocol: Optional[str] = Field(default=None, description="Transport protocol (e.g. https, m3u8, m3u8_native)")
    url: Optional[str] = Field(default=None, description="Direct stream or manifest URL if safe to expose")


class ExtractResponse(BaseModel):
    success: bool = Field(default=True, description="Extraction status")
    title: Optional[str] = Field(default=None, description="Media title")
    duration: Optional[float] = Field(default=None, description="Duration in seconds")
    thumbnail: Optional[str] = Field(default=None, description="Thumbnail image URL")
    extractor: str = Field(..., description="yt-dlp extractor name")
    original_url: str = Field(..., description="Original requested URL")
    media_url: Optional[str] = Field(default=None, description="Resolved media URL for playback")
    format_id: Optional[str] = Field(default=None, description="Resolved format ID")
    resolution: Optional[str] = Field(default=None, description="Resolved media resolution")
    vcodec: Optional[str] = Field(default=None, description="Resolved video codec")
    acodec: Optional[str] = Field(default=None, description="Resolved audio codec")
    has_video: Optional[bool] = Field(default=None, description="True if resolved stream contains video")
    has_audio: Optional[bool] = Field(default=None, description="True if resolved stream contains audio")
    is_video_only: Optional[bool] = Field(default=None, description="True if resolved stream has video without audio")
    is_audio_only: Optional[bool] = Field(default=None, description="True if resolved stream has audio without video")
    is_live: Optional[bool] = Field(default=None, description="True if content is a live stream")
    http_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Required HTTP headers for stream playback (e.g. Referer, User-Agent)",
    )
    formats: List[FormatMetadata] = Field(
        default_factory=list,
        description="List of available stream formats up to MAX_FORMATS_RETURNED",
    )


class ExtractFormatsResponse(BaseModel):
    success: bool = Field(default=True, description="Extraction status")
    title: Optional[str] = Field(default=None, description="Media title")
    extractor: str = Field(..., description="yt-dlp extractor name")
    original_url: str = Field(..., description="Original requested URL")
    format_count: int = Field(..., description="Number of formats returned")
    formats: List[FormatMetadata] = Field(
        default_factory=list,
        description="List of available stream formats up to MAX_FORMATS_RETURNED",
    )
