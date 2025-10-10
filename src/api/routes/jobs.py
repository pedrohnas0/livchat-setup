"""
Job routes for LivChatSetup API

Endpoints for managing long-running jobs:
- GET /api/jobs - List jobs
- GET /api/jobs/{job_id} - Get job status
- POST /api/jobs/{job_id}/cancel - Cancel job
- POST /api/jobs/cleanup - Cleanup old jobs
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

try:
    from ..dependencies import get_job_manager
    from ..models.job import (
        JobResponse,
        JobListResponse,
        JobCancelResponse,
        JobStatusEnum
    )
    from ..models.common import SuccessResponse
    from ...job_manager import JobManager, JobStatus
except ImportError:
    from src.api.dependencies import get_job_manager
    from src.api.models.job import (
        JobResponse,
        JobListResponse,
        JobCancelResponse,
        JobStatusEnum
    )
    from src.api.models.common import SuccessResponse
    from src.job_manager import JobManager, JobStatus

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _job_to_response(job) -> dict:
    """Convert Job instance to response dict"""
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status.value,
        "progress": job.progress,
        "current_step": job.current_step,
        "params": job.params,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "logs": job.logs
    }


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    List all jobs with optional filters

    Returns list of jobs matching the filters, sorted by creation time (newest first).

    Query parameters:
    - status: Filter by job status (pending, running, completed, failed, cancelled)
    - job_type: Filter by job type (create_server, deploy_app, etc.)
    - limit: Maximum number of jobs to return (default: 100, max: 1000)
    """
    try:
        # Convert JobStatusEnum to JobStatus if needed
        status_filter = None
        if status:
            status_filter = JobStatus(status.value)

        # Get jobs from manager
        jobs = job_manager.list_jobs(
            status=status_filter,
            job_type=job_type,
            limit=limit
        )

        # Convert to response format
        job_responses = [_job_to_response(job) for job in jobs]

        return JobListResponse(
            jobs=job_responses,
            total=len(job_responses)
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Get specific job by ID

    Returns complete job information including status, progress, logs, and results.

    Raises:
    - 404: Job not found
    """
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    return JobResponse(**_job_to_response(job))


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Cancel a pending job

    Only pending jobs can be cancelled. Running jobs cannot be stopped.

    Raises:
    - 404: Job not found
    - 400: Job cannot be cancelled (already running/completed)
    """
    # Check if job exists
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    # Try to cancel
    success = job_manager.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} cannot be cancelled (status: {job.status.value})"
        )

    logger.info(f"Job {job_id} cancelled successfully")

    return JobCancelResponse(
        success=True,
        message="Job cancelled successfully",
        job_id=job_id
    )


@router.post("/cleanup", response_model=SuccessResponse)
async def cleanup_jobs(
    max_age_days: int = Query(7, ge=1, le=365, description="Remove jobs older than this many days"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Cleanup old completed/failed/cancelled jobs

    Removes jobs that completed more than max_age_days ago.
    Does not remove pending or running jobs.

    Query parameters:
    - max_age_days: Remove jobs older than this (default: 7, max: 365)

    Returns count of removed jobs.
    """
    try:
        removed = job_manager.cleanup_old_jobs(max_age_days=max_age_days)

        logger.info(f"Cleaned up {removed} old jobs (max_age={max_age_days} days)")

        return SuccessResponse(
            success=True,
            message=f"Cleaned up {removed} old jobs",
            data={"removed": removed}
        )

    except Exception as e:
        logger.error(f"Failed to cleanup jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
