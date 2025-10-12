"""
Pydantic models for secrets management API

Models for secrets (Ansible Vault) operations
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional


class SecretListResponse(BaseModel):
    """Response for listing secret keys"""
    keys: List[str] = Field(description="List of secret keys (no values for security)")
    total: int = Field(description="Total number of secrets")

    class Config:
        json_schema_extra = {
            "example": {
                "keys": ["hetzner_token", "cloudflare_api_key", "postgres_password"],
                "total": 3
            }
        }


class SecretGetResponse(BaseModel):
    """Response for getting a secret value"""
    key: str = Field(description="Secret key")
    value: str = Field(description="Secret value (decrypted)")

    class Config:
        json_schema_extra = {
            "example": {
                "key": "hetzner_token",
                "value": "hetzner_api_token_abc123xyz"
            }
        }


class SecretSetRequest(BaseModel):
    """Request for setting a secret value"""
    value: str = Field(
        min_length=1,
        description="Secret value to store (will be encrypted in vault)"
    )

    @validator('value')
    def value_not_empty(cls, v):
        """Validate that value is not empty or whitespace only"""
        if not v or not v.strip():
            raise ValueError("Secret value cannot be empty")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "value": "my_secret_api_token_123"
            }
        }


class SecretSetResponse(BaseModel):
    """Response for setting a secret"""
    success: bool = Field(description="Whether operation succeeded")
    message: str = Field(description="Success message")
    key: str = Field(description="Secret key that was set")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Secret 'hetzner_token' saved successfully to vault",
                "key": "hetzner_token"
            }
        }


class SecretDeleteResponse(BaseModel):
    """Response for deleting a secret"""
    success: bool = Field(description="Whether operation succeeded")
    message: str = Field(description="Success message")
    key: str = Field(description="Secret key that was deleted")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Secret 'old_token' deleted from vault",
                "key": "old_token"
            }
        }
