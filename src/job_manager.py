"""
Job Manager for async operations

Handles long-running operations (server creation, app deployment, etc.)
Jobs are persisted in state.json and can be queried for status.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
import logging
import functools

from src.job_log_manager import JobLogManager

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
    logs: List[Dict[str, str]] = field(default_factory=list)  # Deprecated: Use log_file instead
    log_file: Optional[str] = None  # Path to job log file

    # Step tracking for better progress visualization
    total_steps: int = 0  # Total number of steps (e.g., 7 for setup-server)
    current_step_num: int = 0  # Current step number (1-based)
    step_name: str = ""  # Human-readable step name
    step_start_time: Optional[datetime] = None  # When current step started

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

    def advance_step(self, step_num: int, total_steps: int, step_name: str):
        """
        Advance to next step and calculate hybrid progress

        Progress combines completed steps with time-based increment within current step.
        This provides smooth progress updates even during long-running steps.

        Args:
            step_num: Current step number (1-based)
            total_steps: Total number of steps in the job
            step_name: Human-readable name of the step

        Progress calculation:
            - Base progress: (completed_steps / total) * 100
            - Time increment: Grows smoothly during step execution
            - Total: base + time_increment (capped at next step threshold)
        """
        self.current_step_num = step_num
        self.total_steps = total_steps
        self.step_name = step_name
        self.current_step = step_name  # Keep backward compatibility
        self.step_start_time = datetime.utcnow()

        # Calculate base progress from completed steps
        if total_steps > 0:
            # Progress from fully completed steps
            base_progress = int(((step_num - 1) / total_steps) * 100)

            # Maximum progress we can show before completing this step
            next_step_progress = int((step_num / total_steps) * 100)
            max_increment = next_step_progress - base_progress

            # Start at base progress when entering new step
            # Time-based increment will be added during execution
            self.progress = base_progress
        else:
            self.progress = 0

        self.add_log(f"Step {step_num}/{total_steps}: {step_name}")
        logger.info(f"[Job {self.job_id}] Advancing to step {step_num}/{total_steps}: {step_name} (progress: {self.progress}%)")

    def update_progress_with_time(self):
        """
        Update progress based on elapsed time in current step

        Called periodically to show smooth progress during long steps.
        Progress grows gradually but never exceeds the threshold for the next step.
        """
        if self.step_start_time and self.total_steps > 0 and self.current_step_num > 0:
            # Calculate time-based increment
            elapsed = (datetime.utcnow() - self.step_start_time).total_seconds()

            # Base progress from completed steps
            base_progress = int(((self.current_step_num - 1) / self.total_steps) * 100)

            # Maximum we can reach in this step
            next_step_progress = int((self.current_step_num / self.total_steps) * 100)
            max_increment = next_step_progress - base_progress

            # Smooth time-based increment (grows ~1% per 30 seconds, capped at 80% of step)
            # This ensures we never reach 100% of the step until it's actually complete
            time_factor = min(elapsed / 30.0, 10.0)  # Cap at 10 (5 minutes)
            time_increment = min(int(time_factor * max_increment * 0.1), int(max_increment * 0.8))

            new_progress = base_progress + time_increment

            # Only update if it actually changed
            if new_progress != self.progress:
                self.progress = new_progress
                logger.debug(f"[Job {self.job_id}] Time-based progress update: {self.progress}%")

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
            "logs": self.logs,
            "log_file": self.log_file,
            "total_steps": self.total_steps,
            "current_step_num": self.current_step_num,
            "step_name": self.step_name,
            "step_start_time": self.step_start_time.isoformat() if self.step_start_time else None
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
            logs=data.get("logs", []),
            log_file=data.get("log_file"),
            total_steps=data.get("total_steps", 0),
            current_step_num=data.get("current_step_num", 0),
            step_name=data.get("step_name", ""),
            step_start_time=datetime.fromisoformat(data["step_start_time"]) if data.get("step_start_time") else None
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

        # Initialize JobLogManager
        logs_dir = Path.home() / ".livchat" / "logs"
        self.log_manager = JobLogManager(logs_dir)

        # Load existing jobs from storage
        if storage:
            self._load_from_storage()

    async def create_job(
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
        await self.save_to_storage()

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
            # Start log capture
            log_file = self.log_manager.start_job_logging(job_id)
            job.log_file = str(log_file)

            # Mark as started
            job.mark_started()
            await self.save_to_storage()

            # Execute task (logs are automatically captured!)
            result = await task_func(job)

            # Mark as completed
            job.mark_completed(result=result)

        except Exception as e:
            # Mark as failed
            error_msg = f"{type(e).__name__}: {str(e)}"
            job.mark_completed(error=error_msg)
            logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True)

        finally:
            # Stop log capture
            self.log_manager.stop_job_logging(job_id)
            await self.save_to_storage()

    async def cancel_job(self, job_id: str) -> bool:
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
        await self.save_to_storage()

        return True

    async def cleanup_old_jobs(self, max_age_days: int = 7) -> int:
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
            await self.save_to_storage()
            logger.info(f"Cleaned up {removed} old jobs")

        return removed

    async def save_to_storage(self):
        """
        Save all jobs to storage (async-safe for FastAPI)

        Uses run_in_executor to prevent blocking the event loop
        during synchronous I/O operations.
        """
        if not self.storage:
            return

        # Run sync I/O in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_to_storage_sync)

    def _save_to_storage_sync(self):
        """Synchronous save - runs in thread pool"""
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
