import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.extract import router as extract_router
from app.api.routes.health import router as health_router
from app.config import settings
from app.middleware.rate_limiter import InMemoryRateLimiterMiddleware
from app.middleware.request_size import RequestSizeLimitMiddleware
from app.schemas.common import RootEndpointInfo
from app.services.extractor import MediaExtractionException
from app.services.ssrf_validator import InvalidURLError, SSRFSecurityError

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("snmflix_media_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup log
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in {settings.ENVIRONMENT} mode."
    )
    if settings.API_KEY:
        logger.info("API Key protection is ENABLED for extraction endpoints.")
    else:
        logger.warning(
            "API Key protection is NOT set. Extraction endpoints are publicly accessible in development mode."
        )
    yield
    # Shutdown
    logger.info("Shutting down SNMflix Media API service.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="High-performance, secure media extraction backend for SNMflix powered by yt-dlp and FastAPI.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# 1. Request Body Size Limiter Middleware
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_bytes=settings.MAX_REQUEST_BODY_SIZE,
)

# 2. In-Memory Rate Limiting Middleware
app.add_middleware(
    InMemoryRateLimiterMiddleware,
    max_requests=settings.RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)

# 3. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(SSRFSecurityError)
async def ssrf_exception_handler(request: Request, exc: SSRFSecurityError):
    logger.warning(f"Blocked SSRF attempt: {str(exc)} | Path: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "SSRF_VIOLATION",
                "message": str(exc),
                "details": None,
            },
        },
    )


@app.exception_handler(InvalidURLError)
async def invalid_url_exception_handler(request: Request, exc: InvalidURLError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "INVALID_URL",
                "message": str(exc),
                "details": None,
            },
        },
    )


@app.exception_handler(MediaExtractionException)
async def media_extraction_exception_handler(request: Request, exc: MediaExtractionException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": None,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        errors.append({"field": loc, "message": msg})
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request body or parameters failed validation.",
                "details": errors,
            },
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "details": None,
            },
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred while processing the request.",
                "details": None,
            },
        },
    )


# Root Endpoint
@app.get(
    "/",
    response_model=RootEndpointInfo,
    tags=["General"],
    summary="API Information and Documentation Link",
)
async def root_info(request: Request) -> RootEndpointInfo:
    base_url = str(request.base_url).rstrip("/")
    return RootEndpointInfo(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="SNMflix Media Extraction API using yt-dlp and FastAPI.",
        docs_url=f"{base_url}/docs",
        endpoints={
            "health": f"{base_url}/health",
            "extract": f"{base_url}/extract",
            "formats": f"{base_url}/extract/formats",
            "docs": f"{base_url}/docs",
            "openapi": f"{base_url}/openapi.json",
        },
    )


# Include Routers
app.include_router(health_router)
app.include_router(extract_router)
