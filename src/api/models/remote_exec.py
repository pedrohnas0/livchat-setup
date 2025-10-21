"""Pydantic models for remote command execution API"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RemoteExecRequest(BaseModel):
    """Request model for remote command execution"""
    command: str = Field(
        ...,
        description="Shell command to execute on the remote server",
        examples=["docker ps", "ls -lah /var/log", "cat /etc/os-release"],
        min_length=1
    )
    timeout: int = Field(
        default=30,
        description="Command timeout in seconds (max 300s = 5min)",
        ge=1,
        le=300
    )
    working_dir: Optional[str] = Field(
        default=None,
        description="Optional working directory to execute command in",
        examples=["/var/log", "/opt/app", "/tmp"]
    )

    @field_validator('command')
    @classmethod
    def validate_command_not_empty(cls, v: str) -> str:
        """Ensure command is not just whitespace"""
        if not v or not v.strip():
            raise ValueError("Command cannot be empty or whitespace-only")
        return v.strip()


class RemoteExecResponse(BaseModel):
    """Response model for remote command execution"""
    success: bool = Field(
        ...,
        description="Whether command executed successfully (exit_code == 0)"
    )
    server_name: str = Field(
        ...,
        description="Name of the server where command was executed"
    )
    command: str = Field(
        ...,
        description="Command that was executed"
    )
    stdout: str = Field(
        default="",
        description="Standard output from command (truncated to 10KB if larger)"
    )
    stderr: str = Field(
        default="",
        description="Standard error from command (truncated to 10KB if larger)"
    )
    exit_code: int = Field(
        ...,
        description="Exit code from command execution"
    )
    timeout_seconds: int = Field(
        ...,
        description="Timeout used for execution (in seconds)"
    )
    working_dir: Optional[str] = Field(
        None,
        description="Working directory used (if specified)"
    )


class RemoteExecErrorResponse(BaseModel):
    """Error response for remote command execution"""
    success: bool = Field(
        default=False,
        description="Always false for errors"
    )
    error: str = Field(
        ...,
        description="Error message"
    )
    detail: Optional[str] = Field(
        None,
        description="Detailed error information"
    )
    server_name: Optional[str] = Field(
        None,
        description="Server name (if known)"
    )
    command: Optional[str] = Field(
        None,
        description="Command that failed (if known)"
    )
