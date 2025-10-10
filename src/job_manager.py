"""
Job Manager for async operations

Handles long-running operations (server creation, app deployment, etc.)
Jobs are persisted in state.json and can be queried for status.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """
    Represents a long-running job

    Tracks progress, logs, and results of async operations
    """
    job_id: str
    job_type: str
    params: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    current_step: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[Dict[str, str]] = field(default_factory=list)

    def add_log(self, message: str):
        """Add log entry with timestamp"""
        self.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        })
        logger.info(f"[Job {self.job_id}] {message}")

    def update_progress(self, progress: int, step: str = ""):
        """Update job progress and current step"""
        self.progress = progress
        if step:
            self.current_step = step
            self.add_log(f"Progress: {progress}% - {step}")

    def mark_started(self):
        """Mark job as started"""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.add_log("Job started")

    def mark_completed(self, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """
        Mark job as completed

        Args:
            result: Result data if successful
            error: Error message if failed
        """
        self.completed_at = datetime.utcnow()

        if error:
            self.status = JobStatus.FAILED
            self.error = error
            self.add_log(f"Job failed: {error}")
        else:
            self.status = JobStatus.COMPLETED
            self.result = result
            self.progress = 100
            self.add_log("Job completed successfully")

    def mark_cancelled(self):
        """Mark job as cancelled"""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.add_log("Job cancelled")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "logs": self.logs
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Deserialize from dictionary"""
        return cls(
            job_id=data["job_id"],
            job_type=data["job_type"],
            params=data["params"],
            status=JobStatus(data["status"]),
            progress=data["progress"],
            current_step=data.get("current_step", ""),
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            logs=data.get("logs", [])
        )


class JobManager:
    """
    Manages job lifecycle and execution

    Responsibilities:
    - Create and track jobs
    - Execute jobs in background
    - Persist jobs to storage
    - Cleanup old jobs
    """

    def __init__(self, storage=None):
        """
        Initialize JobManager

        Args:
            storage: StorageManager instance for persistence
        """
        self.storage = storage
        self.jobs: Dict[str, Job] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

        # Load existing jobs from storage
        if storage:
            self._load_from_storage()

    def create_job(
        self,
        job_type: str,
        params: Dict[str, Any],
        job_id: Optional[str] = None
    ) -> Job:
        """
        Create new job

        Args:
            job_type: Type of job (create_server, deploy_app, etc.)
            params: Job parameters
            job_id: Optional custom job ID

        Returns:
            Created Job instance
        """
        if job_id is None:
            job_id = f"{job_type}-{uuid.uuid4().hex[:8]}"

        job = Job(
            job_id=job_id,
            job_type=job_type,
            params=params
        )

        self.jobs[job_id] = job
        self.save_to_storage()

        logger.info(f"Created job {job_id} (type: {job_type})")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID

        Args:
            job_id: Job identifier

        Returns:
            Job instance or None if not found
        """
        return self.jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Job]:
        """
        List jobs with optional filters

        Args:
            status: Filter by status
            job_type: Filter by job type
            limit: Maximum number of jobs to return

        Returns:
            List of Job instances
        """
        jobs = list(self.jobs.values())

        # Apply filters
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]

        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    async def run_job(
        self,
        job_id: str,
        task_func: Callable[[Job], Awaitable[Any]]
    ):
        """
        Execute job in background

        Args:
            job_id: Job identifier
            task_func: Async function that performs the work
                      Receives Job instance as parameter
                      Should update job progress and logs
                      Returns result data

        Raises:
            ValueError: If job not found
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            # Mark as started
            job.mark_started()
            self.save_to_storage()

            # Execute task
            result = await task_func(job)

            # Mark as completed
            job.mark_completed(result=result)

        except Exception as e:
            # Mark as failed
            error_msg = f"{type(e).__name__}: {str(e)}"
            job.mark_completed(error=error_msg)
            logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True)

        finally:
            self.save_to_storage()

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel pending job

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False if not found or already running
        """
        job = self.get_job(job_id)
        if not job:
            return False

        # Can only cancel pending jobs
        if job.status != JobStatus.PENDING:
            return False

        job.mark_cancelled()
        self.save_to_storage()

        return True

    def cleanup_old_jobs(self, max_age_days: int = 7) -> int:
        """
        Remove old completed/failed jobs

        Args:
            max_age_days: Maximum age in days for completed jobs

        Returns:
            Number of jobs removed
        """
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        removed = 0

        for job_id, job in list(self.jobs.items()):
            # Only remove completed/failed/cancelled jobs
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                if job.completed_at and job.completed_at < cutoff:
                    del self.jobs[job_id]
                    removed += 1

        if removed > 0:
            self.save_to_storage()
            logger.info(f"Cleaned up {removed} old jobs")

        return removed

    def save_to_storage(self):
        """Save all jobs to storage"""
        if not self.storage:
            return

        jobs_data = [job.to_dict() for job in self.jobs.values()]
        self.storage.state.save_jobs(jobs_data)

    def _load_from_storage(self):
        """Load jobs from storage"""
        if not self.storage:
            return

        try:
            jobs_data = self.storage.state.load_jobs()
            for job_data in jobs_data:
                job = Job.from_dict(job_data)
                self.jobs[job.job_id] = job

            logger.info(f"Loaded {len(self.jobs)} jobs from storage")
        except Exception as e:
            logger.warning(f"Failed to load jobs from storage: {e}")
