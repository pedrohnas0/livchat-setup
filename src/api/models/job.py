"""
Pydantic models for Job API

Response and request models for job-related endpoints
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class JobStatusEnum(str, Enum):
    """Job status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobLogEntry(BaseModel):
    """Single log entry"""
    timestamp: str = Field(..., description="ISO timestamp of log entry")
    message: str = Field(..., description="Log message")


class JobResponse(BaseModel):
    """Job information response"""
    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job (create_server, deploy_app, etc.)")
    status: JobStatusEnum = Field(..., description="Current job status")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str = Field("", description="Current step description")
    params: Dict[str, Any] = Field(..., description="Job parameters")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result data (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    logs: List[JobLogEntry] = Field(default_factory=list, description="Job execution logs")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "create_server-abc123",
                "job_type": "create_server",
                "status": "running",
                "progress": 50,
                "current_step": "Installing Docker",
                "params": {"name": "production-1", "region": "nbg1"},
                "result": None,
                "error": None,
                "created_at": "2024-12-16T10:00:00",
                "started_at": "2024-12-16T10:00:05",
                "completed_at": None,
                "logs": [
                    {"timestamp": "2024-12-16T10:00:05", "message": "Job started"},
                    {"timestamp": "2024-12-16T10:00:10", "message": "Creating server..."}
                ]
            }
        }


class JobListResponse(BaseModel):
    """List of jobs"""
    jobs: List[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")

    class Config:
        json_schema_extra = {
            "example": {
                "jobs": [
                    {
                        "job_id": "create_server-abc123",
                        "job_type": "create_server",
                        "status": "completed",
                        "progress": 100,
                        "current_step": "Done",
                        "params": {"name": "server-1"},
                        "result": {"server_id": "123"},
                        "error": None,
                        "created_at": "2024-12-16T10:00:00",
                        "started_at": "2024-12-16T10:00:05",
                        "completed_at": "2024-12-16T10:05:00",
                        "logs": []
                    }
                ],
                "total": 1
            }
        }


class JobCreateRequest(BaseModel):
    """Request to create a new job"""
    job_type: str = Field(..., description="Type of job to create")
    params: Dict[str, Any] = Field(..., description="Job parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "create_server",
                "params": {
                    "name": "production-1",
                    "server_type": "cx21",
                    "region": "nbg1"
                }
            }
        }


class JobCancelResponse(BaseModel):
    """Response from job cancellation"""
    success: bool = Field(..., description="Whether cancellation was successful")
    message: str = Field(..., description="Result message")
    job_id: str = Field(..., description="Job identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Job cancelled successfully",
                "job_id": "create_server-abc123"
            }
        }
