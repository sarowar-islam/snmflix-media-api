from fastapi import APIRouter, Depends, status
from app.api.deps import verify_api_key
from app.schemas.extract import (
    ExtractFormatsRequest,
    ExtractFormatsResponse,
    ExtractRequest,
    ExtractResponse,
)
from app.services.extractor import extractor_service

router = APIRouter(tags=["Media Extraction"])


@router.post(
    "/extract",
    response_model=ExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Media Stream and Information",
    description="Inspect a media page URL using yt-dlp without downloading media. Returns title, duration, streams, and playback URLs.",
    dependencies=[Depends(verify_api_key)],
)
async def extract_media_endpoint(payload: ExtractRequest) -> ExtractResponse:
    return await extractor_service.extract_media(
        url=payload.url,
        format_preference=payload.format,
    )


@router.post(
    "/extract/formats",
    response_model=ExtractFormatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Available Formats",
    description="Inspect and list all available media formats, codecs, and stream metadata for a supported URL without exposing internal yt-dlp fields.",
    dependencies=[Depends(verify_api_key)],
)
async def extract_formats_endpoint(payload: ExtractFormatsRequest) -> ExtractFormatsResponse:
    return await extractor_service.extract_formats(url=payload.url)
