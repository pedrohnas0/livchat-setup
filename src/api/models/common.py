"""
Common Pydantic models for API responses

These models are used across all API endpoints for standardized responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ErrorResponse(BaseModel):
    """
    Standard error response model

    Used for all error responses (4xx, 5xx)
    """
    error: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code (e.g., SERVER_NOT_FOUND)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "Server not found",
                    "code": "SERVER_NOT_FOUND",
                    "details": {"server_name": "prod-01"}
                }
            ]
        }
    }


class SuccessResponse(BaseModel):
    """
    Standard success response model

    Used for successful operations that need structured response
    """
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Server created successfully",
                    "data": {"server_id": "123", "ip": "1.2.3.4"}
                }
            ]
        }
    }


class MessageResponse(BaseModel):
    """
    Simple message response model

    Used for endpoints that just need to return a message
    """
    message: str = Field(..., description="Response message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"message": "Operation completed successfully"}
            ]
        }
    }
