"""
Pydantic models for Configuration API

Request and response models for configuration endpoints
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ConfigGetResponse(BaseModel):
    """Response with configuration value"""
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")

    class Config:
        json_schema_extra = {
            "example": {
                "key": "provider",
                "value": "hetzner"
            }
        }


class ConfigSetRequest(BaseModel):
    """Request to set configuration value"""
    value: Any = Field(..., description="Value to set")

    class Config:
        json_schema_extra = {
            "example": {
                "value": "hetzner"
            }
        }


class ConfigSetResponse(BaseModel):
    """Response from setting configuration"""
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Status message")
    key: str = Field(..., description="Configuration key that was set")
    value: Any = Field(..., description="New value")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Configuration updated",
                "key": "provider",
                "value": "hetzner"
            }
        }


class ConfigAllResponse(BaseModel):
    """Response with all configuration"""
    config: Dict[str, Any] = Field(..., description="Complete configuration dictionary")

    class Config:
        json_schema_extra = {
            "example": {
                "config": {
                    "version": 1,
                    "provider": "hetzner",
                    "region": "nbg1",
                    "server_type": "cx21"
                }
            }
        }


class ConfigUpdateRequest(BaseModel):
    """Request to update multiple configuration values"""
    updates: Dict[str, Any] = Field(..., description="Dictionary of key-value pairs to update")

    class Config:
        json_schema_extra = {
            "example": {
                "updates": {
                    "provider": "hetzner",
                    "region": "nbg1",
                    "server_type": "cx21"
                }
            }
        }


class ConfigUpdateResponse(BaseModel):
    """Response from bulk update"""
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Status message")
    updated_count: int = Field(..., description="Number of keys updated")
    updated_keys: list = Field(..., description="List of keys that were updated")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Configuration updated",
                "updated_count": 3,
                "updated_keys": ["provider", "region", "server_type"]
            }
        }
