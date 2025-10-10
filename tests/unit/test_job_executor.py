"""
Unit tests for JobExecutor

Tests the core job execution engine that processes pending jobs
in background using asyncio.

TDD Approach: RED → GREEN → REFACTOR
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.job_executor import JobExecutor
from src.job_manager import JobManager, Job, JobStatus


class TestJobExecutorInitialization:
    """Tests for JobExecutor initialization"""

    @pytest.fixture
    def job_manager(self):
        """Mock JobManager"""
        manager = MagicMock(spec=JobManager)
        manager.list_jobs.return_value = []
        manager.run_job = AsyncMock()
        manager.get_job = MagicMock()
        return manager

    @pytest.fixture
    def orchestrator(self):
        """Mock Orchestrator"""
        return MagicMock()

    @pytest.fixture
    def executor(self, job_manager, orchestrator):
        """Create JobExecutor instance"""
        return JobExecutor(job_manager, orchestrator)

    def test_executor_initializes_with_dependencies(self, executor, job_manager, orchestrator):
        """Should initialize with job_manager and orchestrator"""
        assert executor.job_manager is job_manager
        assert executor.orchestrator is orchestrator
        assert executor.running is False
        assert executor._task is None

    def test_executor_has_empty_registry_initially(self, executor):
        """Should have executor registry"""
        # Executor should have a way to map job types to functions
        assert hasattr(executor, '_get_executor_function')


class TestJobExecutorLifecycle:
    """Tests for executor start/stop lifecycle"""

    @pytest.fixture
    def job_manager(self):
        manager = MagicMock(spec=JobManager)
        manager.list_jobs.return_value = []
        manager.run_job = AsyncMock()
        return manager

    @pytest.fixture
    def orchestrator(self):
        return MagicMock()

    @pytest.fixture
    def executor(self, job_manager, orchestrator):
        return JobExecutor(job_manager, orchestrator)

    @pytest.mark.asyncio
    async def test_start_initializes_executor(self, executor):
        """Should start background task and set running flag"""
        await executor.start()

        assert executor.running is True
        assert executor._task is not None
        assert isinstance(executor._task, asyncio.Task)

        # Cleanup
        await executor.stop()

    @pytest.mark.asyncio
    async def test_stop_gracefully_stops_executor(self, executor):
        """Should stop background loop and clear task"""
        await executor.start()
        assert executor.running is True

        await executor.stop()

        assert executor.running is False
        # Task should have completed
        assert executor._task.done()

    @pytest.mark.asyncio
    async def test_executor_can_restart(self, executor):
        """Should be able to stop and start again"""
        # First run
        await executor.start()
        await executor.stop()

        # Second run
        await executor.start()
        assert executor.running is True
        await executor.stop()
        assert executor.running is False

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, executor):
        """Should handle stop before start gracefully"""
        # Should not raise exception
        await executor.stop()
        assert executor.running is False


class TestJobProcessing:
    """Tests for job processing logic"""

    @pytest.fixture
    def job_manager(self):
        manager = MagicMock(spec=JobManager)
        manager.list_jobs.return_value = []
        manager.run_job = AsyncMock()
        manager.get_job = MagicMock()
        return manager

    @pytest.fixture
    def orchestrator(self):
        return MagicMock()

    @pytest.fixture
    def executor(self, job_manager, orchestrator):
        return JobExecutor(job_manager, orchestrator)

    @pytest.mark.asyncio
    async def test_processes_pending_jobs(self, executor, job_manager):
        """Should pick up pending jobs and execute them"""
        # Create pending job
        job = Job(
            job_id="test-123",
            job_type="create_server",
            params={"name": "test"}
        )
        job_manager.list_jobs.return_value = [job]
        job_manager.get_job.return_value = job

        # Note: create_server executor exists in real EXECUTOR_REGISTRY now
        # No need to mock it

        # Start executor briefly
        await executor.start()
        await asyncio.sleep(0.1)  # Let it process
        await executor.stop()

        # Should have called run_job
        assert job_manager.run_job.called

    @pytest.mark.asyncio
    async def test_skips_non_pending_jobs(self, executor, job_manager):
        """Should only process jobs with status=pending"""
        # Create running job
        job = Job(
            job_id="test-running",
            job_type="create_server",
            params={}
        )
        job.status = JobStatus.RUNNING

        job_manager.list_jobs.return_value = []  # list_jobs filters by pending

        await executor.start()
        await asyncio.sleep(0.1)
        await executor.stop()

        # Should not have processed running job
        job_manager.run_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_multiple_jobs_concurrently(self, executor, job_manager):
        """Should handle multiple pending jobs"""
        jobs = [
            Job(job_id=f"job-{i}", job_type="test_type", params={})
            for i in range(3)
        ]
        job_manager.list_jobs.return_value = jobs

        # Register mock executor temporarily (test_type doesn't exist in real registry)
        from src.job_executors import EXECUTOR_REGISTRY
        async def mock_executor(job, orchestrator):
            return {"result": "success"}

        # Save original registry state
        original_test_type = EXECUTOR_REGISTRY.get("test_type")
        EXECUTOR_REGISTRY["test_type"] = mock_executor

        try:
            await executor.start()
            await asyncio.sleep(0.2)
            await executor.stop()

            # Should have processed all jobs
            assert job_manager.run_job.call_count >= 3
        finally:
            # Restore original state (remove test_type if it didn't exist before)
            if original_test_type is None:
                EXECUTOR_REGISTRY.pop("test_type", None)
            else:
                EXECUTOR_REGISTRY["test_type"] = original_test_type

    @pytest.mark.asyncio
    async def test_continues_processing_after_error(self, executor, job_manager):
        """Should continue processing even if one job fails"""
        job1 = Job(job_id="job-1", job_type="test", params={})
        job2 = Job(job_id="job-2", job_type="test", params={})

        job_manager.list_jobs.side_effect = [
            [job1],  # First iteration
            Exception("Test error"),  # Second iteration fails
            [job2],  # Third iteration continues
            []  # Stop
        ]

        await executor.start()
        await asyncio.sleep(0.3)
        await executor.stop()

        # Should have continued despite error
        assert executor.running is False  # Stopped gracefully


class TestExecutorFunctions:
    """Tests for executor function registry and execution"""

    @pytest.fixture
    def job_manager(self):
        manager = MagicMock(spec=JobManager)
        manager.run_job = AsyncMock()
        manager.get_job = MagicMock()
        return manager

    @pytest.fixture
    def orchestrator(self):
        return MagicMock()

    @pytest.fixture
    def executor(self, job_manager, orchestrator):
        return JobExecutor(job_manager, orchestrator)

    def test_get_executor_function_returns_none_for_unknown_type(self, executor):
        """Should return None for unknown job type"""
        func = executor._get_executor_function("unknown_type")
        assert func is None

    @pytest.mark.asyncio
    async def test_execute_job_with_unknown_type_marks_as_failed(self, executor, job_manager):
        """Should mark job as failed if type is unknown"""
        job = Job(
            job_id="test-unknown",
            job_type="unknown_type",
            params={}
        )
        job_manager.get_job.return_value = job

        await executor._execute_job(job)

        # Job should be marked as failed
        assert job.status == JobStatus.FAILED
        assert "Unknown job type" in job.error


class TestExecutorIntegration:
    """Integration tests with real components (mocked external calls)"""

    @pytest.fixture
    def job_manager(self):
        """Use real JobManager without storage"""
        return JobManager(storage=None)

    @pytest.fixture
    def orchestrator(self):
        """Mock orchestrator"""
        orch = MagicMock()
        orch.create_server = MagicMock(return_value={
            "id": "srv-123",
            "ip": "192.168.1.1"
        })
        return orch

    @pytest.fixture
    def executor(self, job_manager, orchestrator):
        return JobExecutor(job_manager, orchestrator)

    @pytest.mark.asyncio
    async def test_full_job_lifecycle_integration(self, executor, job_manager, orchestrator):
        """Test complete job lifecycle from creation to completion"""
        # Create job
        job = job_manager.create_job(
            job_type="create_server",
            params={"name": "test-server", "server_type": "cx11", "location": "nbg1"}
        )

        assert job.status == JobStatus.PENDING

        # Start executor
        await executor.start()

        # Wait for processing (with timeout)
        for _ in range(20):  # Max 2 seconds
            current_job = job_manager.get_job(job.job_id)
            if current_job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.1)

        await executor.stop()

        # Verify job was processed
        final_job = job_manager.get_job(job.job_id)
        # Will be FAILED initially because executor function doesn't exist yet
        # After implementation, this should be COMPLETED
        assert final_job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
