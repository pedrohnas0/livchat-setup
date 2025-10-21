"""Pydantic models for state management API"""

from typing import Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class StateAction(str, Enum):
    """Actions for state management"""
    GET = "get"
    SET = "set"
    LIST = "list"
    DELETE = "delete"


class StateGetRequest(BaseModel):
    """Request model for getting state value"""
    path: Optional[str] = Field(
        None,
        description="Dot notation path (e.g., 'servers.prod.ip'). None or empty returns entire state",
        examples=["servers.prod.ip", "settings.admin_email", "servers"]
    )


class StateSetRequest(BaseModel):
    """Request model for setting state value"""
    path: str = Field(
        ...,
        description="Dot notation path where to set the value",
        examples=["servers.prod.ip", "settings.admin_email"]
    )
    value: Any = Field(
        ...,
        description="Value to set (can be any JSON type: string, number, object, array, boolean, null)"
    )


class StateDeleteRequest(BaseModel):
    """Request model for deleting state key"""
    path: str = Field(
        ...,
        description="Dot notation path of key to delete",
        examples=["servers.prod.status", "settings.admin_email"]
    )


class StateListRequest(BaseModel):
    """Request model for listing keys at path"""
    path: Optional[str] = Field(
        None,
        description="Dot notation path to list keys from. None or empty lists root keys",
        examples=["servers", "servers.prod", "settings"]
    )


class StateResponse(BaseModel):
    """Response model for state operations"""
    success: bool = Field(..., description="Whether operation succeeded")
    action: StateAction = Field(..., description="Action performed")
    path: Optional[str] = Field(None, description="Path operated on")
    value: Optional[Any] = Field(None, description="Value at path (for get action)")
    keys: Optional[List[str]] = Field(None, description="Keys at path (for list action)")
    message: Optional[str] = Field(None, description="Success/error message")


class StateErrorResponse(BaseModel):
    """Error response for state operations"""
    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    path: Optional[str] = Field(None, description="Path that caused the error")
