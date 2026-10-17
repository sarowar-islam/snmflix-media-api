from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable description of the error")
    details: Optional[Any] = Field(default=None, description="Optional extra error context")


class APIErrorResponse(BaseModel):
    success: bool = Field(default=False, description="Always false for error responses")
    error: ErrorDetail


class RootEndpointInfo(BaseModel):
    name: str
    version: str
    description: str
    docs_url: str
    endpoints: Dict[str, str]
