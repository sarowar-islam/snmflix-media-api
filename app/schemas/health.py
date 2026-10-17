from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application operational status")
    version: str = Field(..., description="Application version")
    timestamp: float = Field(..., description="Current server UNIX timestamp")
