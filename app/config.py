from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General App Settings
    APP_NAME: str = "SNMflix Media Extraction API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"

    # Server Bindings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    API_KEY: Optional[str] = None
    REQUIRE_API_KEY: bool = False

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = [
        "https://snmflix.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Extraction Concurrency and Timeouts
    MAX_CONCURRENT_EXTRACTIONS: int = Field(default=5, ge=1, le=50)
    EXTRACTION_TIMEOUT_SECONDS: int = Field(default=20, ge=5, le=120)
    MAX_FORMATS_RETURNED: int = Field(default=100, ge=1, le=500)

    # Rate Limiting & Abuse Prevention
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1, le=1000)
    MAX_REQUEST_BODY_SIZE: int = Field(default=65536, ge=1024, le=1048576)  # 64 KB default

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return []


settings = Settings()
