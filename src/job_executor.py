"""
Job Executor - Background job processing engine

Processes pending jobs asynchronously using asyncio.
Integrates with JobManager to execute jobs and update their status.

Usage:
    executor = JobExecutor(job_manager, orchestrator)
    await executor.start()
    # ... jobs are processed in background ...
    await executor.stop()
"""

import asyncio
import logging
from typing import Optional, Callable, Awaitable, Dict

from src.job_manager import JobManager, Job, JobStatus
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class JobExecutor:
    """
    Background job executor using asyncio

    Responsibilities:
    - Monitor jobs for pending status
    - Execute jobs using appropriate executor functions
    - Update job progress in real-time
    - Handle errors and failures gracefully
    - Support concurrent job processing
    """

    # Time between checking for new jobs (seconds)
    POLL_INTERVAL = 2.0

    # Maximum concurrent jobs
    MAX_CONCURRENT_JOBS = 10

    def __init__(self, job_manager: JobManager, orchestrator: Orchestrator):
        """
        Initialize JobExecutor

        Args:
            job_manager: JobManager instance for job operations
            orchestrator: Orchestrator instance for business logic
        """
        self.job_manager = job_manager
        self.orchestrator = orchestrator
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._processing_jobs: Dict[str, asyncio.Task] = {}

        logger.info("JobExecutor initialized")

    async def start(self):
        """
        Start the job executor background loop

        Creates an asyncio task that continuously checks for
        and processes pending jobs.
        """
        if self.running:
            logger.warning("JobExecutor already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._process_loop())

        logger.info("JobExecutor started")

    async def stop(self):
        """
        Stop the job executor gracefully

        Stops accepting new jobs and waits for currently
        running jobs to complete (with timeout).
        """
        if not self.running:
            return

        self.running = False

        # Wait for main loop to finish
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Process loop did not stop gracefully, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        # Wait for running jobs (with timeout)
        if self._processing_jobs:
            logger.info(f"Waiting for {len(self._processing_jobs)} jobs to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._processing_jobs.values(), return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some jobs did not complete in time")

        # Don't set _task = None - keep it for inspection (it will be .done())
        self._processing_jobs.clear()

        logger.info("JobExecutor stopped")

    async def _process_loop(self):
        """
        Main processing loop

        Continuously checks for pending jobs and processes them.
        Runs until self.running is set to False.
        """
        logger.info("Job processing loop started")

        while self.running:
            try:
                await self._process_pending_jobs()
            except Exception as e:
                logger.error(f"Error in job processing loop: {e}", exc_info=True)

            # Wait before next check
            await asyncio.sleep(self.POLL_INTERVAL)

        logger.info("Job processing loop stopped")

    async def _process_pending_jobs(self):
        """
        Check for and process all pending jobs

        Gets list of pending jobs and spawns tasks to process them.
        Respects MAX_CONCURRENT_JOBS limit.
        """
        # Clean up completed tasks
        self._cleanup_completed_tasks()

        # Check concurrent limit
        if len(self._processing_jobs) >= self.MAX_CONCURRENT_JOBS:
            logger.debug(f"Max concurrent jobs ({self.MAX_CONCURRENT_JOBS}) reached, waiting...")
            return

        # Get pending jobs
        pending_jobs = self.job_manager.list_jobs(status=JobStatus.PENDING)

        if not pending_jobs:
            return

        logger.info(f"Found {len(pending_jobs)} pending job(s)")

        # Process each pending job
        for job in pending_jobs:
            # Skip if already processing
            if job.job_id in self._processing_jobs:
                continue

            # Check concurrent limit again
            if len(self._processing_jobs) >= self.MAX_CONCURRENT_JOBS:
                break

            # Spawn task to process job
            task = asyncio.create_task(self._execute_job(job))
            self._processing_jobs[job.job_id] = task

            logger.info(f"Started processing job {job.job_id} (type: {job.job_type})")

    def _cleanup_completed_tasks(self):
        """Remove completed tasks from tracking dict"""
        completed = [
            job_id for job_id, task in self._processing_jobs.items()
            if task.done()
        ]

        for job_id in completed:
            del self._processing_jobs[job_id]

    async def _execute_job(self, job: Job):
        """
        Execute a single job

        Gets the appropriate executor function for the job type
        and runs it using JobManager.run_job().

        Args:
            job: Job instance to execute
        """
        try:
            # Get executor function for this job type
            executor_func = self._get_executor_function(job.job_type)

            if not executor_func:
                # Unknown job type - mark as failed
                logger.error(f"Unknown job type: {job.job_type}")
                job.mark_completed(error=f"Unknown job type: {job.job_type}")
                self.job_manager.save_to_storage()
                return

            # Execute job using JobManager
            await self.job_manager.run_job(job.job_id, executor_func)

            logger.info(f"Job {job.job_id} completed successfully")

        except Exception as e:
            logger.error(f"Error executing job {job.job_id}: {e}", exc_info=True)
            # JobManager.run_job already handles exceptions, but log here too

    def _get_executor_function(self, job_type: str) -> Optional[Callable[[Job], Awaitable]]:
        """
        Get executor function for a job type

        Maps job_type to the appropriate executor function.
        Returns a wrapped function that injects orchestrator dependency.

        Args:
            job_type: Type of job (create_server, deploy_app, etc.)

        Returns:
            Async function that takes Job and returns result,
            or None if job type is unknown
        """
        from src.job_executors import EXECUTOR_REGISTRY

        # Get base executor function
        base_func = EXECUTOR_REGISTRY.get(job_type)

        if not base_func:
            logger.warning(f"No executor registered for job type: {job_type}")
            return None

        # Wrap function to inject orchestrator
        async def wrapped_executor(job: Job):
            """Wrapper that injects orchestrator dependency"""
            return await base_func(job, self.orchestrator)

        return wrapped_executor
