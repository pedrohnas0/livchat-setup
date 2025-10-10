"""
Unit tests for JobManager

Following TDD: Write tests FIRST

Tests for:
- Job class (creation, logging, progress, serialization)
- JobManager class (create, run, get, list, cancel, cleanup)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.job_manager import Job, JobManager, JobStatus


class TestJobClass:
    """Test Job class"""

    def test_job_creation(self):
        """Should create job with correct initial state"""
        # Act
        job = Job(
            job_id="test-123",
            job_type="create_server",
            params={"name": "test"}
        )

        # Assert
        assert job.job_id == "test-123"
        assert job.job_type == "create_server"
        assert job.params == {"name": "test"}
        assert job.status == JobStatus.PENDING
        assert job.progress == 0
        assert job.result is None
        assert job.error is None
        assert isinstance(job.created_at, datetime)
        assert job.started_at is None
        assert job.completed_at is None
        assert len(job.logs) == 0

    def test_job_add_log(self):
        """Should add log entry"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={})

        # Act
        job.add_log("Test message")

        # Assert
        assert len(job.logs) == 1
        assert job.logs[0]["message"] == "Test message"
        assert "timestamp" in job.logs[0]

    def test_job_update_progress(self):
        """Should update progress and current step"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={})

        # Act
        job.update_progress(50, "Half done")

        # Assert
        assert job.progress == 50
        assert job.current_step == "Half done"

    def test_job_mark_started(self):
        """Should mark job as started"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={})

        # Act
        job.mark_started()

        # Assert
        assert job.status == JobStatus.RUNNING
        assert isinstance(job.started_at, datetime)

    def test_job_mark_completed_success(self):
        """Should mark job as completed successfully"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={})
        job.mark_started()

        # Act
        job.mark_completed(result={"server_id": "123"})

        # Assert
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"server_id": "123"}
        assert job.error is None
        assert isinstance(job.completed_at, datetime)

    def test_job_mark_completed_failed(self):
        """Should mark job as failed with error"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={})
        job.mark_started()

        # Act
        job.mark_completed(error="Something went wrong")

        # Assert
        assert job.status == JobStatus.FAILED
        assert job.error == "Something went wrong"
        assert job.result is None
        assert isinstance(job.completed_at, datetime)

    def test_job_mark_cancelled(self):
        """Should mark job as cancelled"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={})

        # Act
        job.mark_cancelled()

        # Assert
        assert job.status == JobStatus.CANCELLED
        assert isinstance(job.completed_at, datetime)

    def test_job_to_dict(self):
        """Should serialize to dictionary"""
        # Arrange
        job = Job(job_id="test", job_type="test", params={"key": "value"})
        job.add_log("Log entry")
        job.update_progress(25, "Working")

        # Act
        data = job.to_dict()

        # Assert
        assert data["job_id"] == "test"
        assert data["job_type"] == "test"
        assert data["status"] == "pending"
        assert data["progress"] == 25
        assert data["current_step"] == "Working"
        assert data["params"] == {"key": "value"}
        assert len(data["logs"]) == 2  # add_log + update_progress both add logs
        assert "created_at" in data

    def test_job_from_dict(self):
        """Should deserialize from dictionary"""
        # Arrange
        data = {
            "job_id": "test",
            "job_type": "create_server",
            "status": "running",
            "progress": 50,
            "current_step": "Installing",
            "params": {"name": "server1"},
            "result": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "logs": [{"timestamp": datetime.utcnow().isoformat(), "message": "Test"}]
        }

        # Act
        job = Job.from_dict(data)

        # Assert
        assert job.job_id == "test"
        assert job.job_type == "create_server"
        assert job.status == JobStatus.RUNNING
        assert job.progress == 50
        assert job.current_step == "Installing"
        assert len(job.logs) == 1


class TestJobManager:
    """Test JobManager class"""

    @pytest.fixture
    def storage_mock(self):
        """Mock storage manager"""
        storage = Mock()
        storage.state = Mock()
        storage.state.load_jobs = Mock(return_value=[])
        storage.state.save_jobs = Mock()
        return storage

    @pytest.fixture
    def job_manager(self, storage_mock):
        """Create JobManager instance"""
        return JobManager(storage=storage_mock)

    def test_create_job(self, job_manager):
        """Should create new job"""
        # Act
        job = job_manager.create_job(
            job_type="create_server",
            params={"name": "test"}
        )

        # Assert
        assert job.job_type == "create_server"
        assert job.params == {"name": "test"}
        assert job.status == JobStatus.PENDING
        assert job.job_id in job_manager.jobs

    def test_create_job_with_custom_id(self, job_manager):
        """Should create job with custom ID"""
        # Act
        job = job_manager.create_job(
            job_type="test",
            params={},
            job_id="custom-123"
        )

        # Assert
        assert job.job_id == "custom-123"

    def test_get_job_exists(self, job_manager):
        """Should return job if exists"""
        # Arrange
        job = job_manager.create_job("test", {})

        # Act
        retrieved = job_manager.get_job(job.job_id)

        # Assert
        assert retrieved == job

    def test_get_job_not_exists(self, job_manager):
        """Should return None if job doesn't exist"""
        # Act
        job = job_manager.get_job("nonexistent")

        # Assert
        assert job is None

    def test_list_jobs_empty(self, job_manager):
        """Should return empty list when no jobs"""
        # Act
        jobs = job_manager.list_jobs()

        # Assert
        assert jobs == []

    def test_list_jobs_with_jobs(self, job_manager):
        """Should return all jobs"""
        # Arrange
        job1 = job_manager.create_job("test1", {})
        job2 = job_manager.create_job("test2", {})

        # Act
        jobs = job_manager.list_jobs()

        # Assert
        assert len(jobs) == 2
        assert job1 in jobs
        assert job2 in jobs

    def test_list_jobs_filter_by_status(self, job_manager):
        """Should filter jobs by status"""
        # Arrange
        job1 = job_manager.create_job("test1", {})
        job2 = job_manager.create_job("test2", {})
        job2.mark_started()

        # Act
        pending = job_manager.list_jobs(status=JobStatus.PENDING)
        running = job_manager.list_jobs(status=JobStatus.RUNNING)

        # Assert
        assert len(pending) == 1
        assert job1 in pending
        assert len(running) == 1
        assert job2 in running

    def test_list_jobs_filter_by_type(self, job_manager):
        """Should filter jobs by type"""
        # Arrange
        job1 = job_manager.create_job("create_server", {})
        job2 = job_manager.create_job("deploy_app", {})

        # Act
        create_jobs = job_manager.list_jobs(job_type="create_server")

        # Assert
        assert len(create_jobs) == 1
        assert job1 in create_jobs

    @pytest.mark.asyncio
    async def test_run_job_success(self, job_manager):
        """Should run job successfully"""
        # Arrange
        async def task_func(job: Job):
            job.update_progress(50, "Working")
            await asyncio.sleep(0.01)
            return {"result": "success"}

        job = job_manager.create_job("test", {})

        # Act
        await job_manager.run_job(job.job_id, task_func)

        # Assert
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"result": "success"}
        assert job.error is None

    @pytest.mark.asyncio
    async def test_run_job_failure(self, job_manager):
        """Should handle job failure"""
        # Arrange
        async def task_func(job: Job):
            raise ValueError("Test error")

        job = job_manager.create_job("test", {})

        # Act
        await job_manager.run_job(job.job_id, task_func)

        # Assert
        assert job.status == JobStatus.FAILED
        assert "Test error" in job.error
        assert job.result is None

    @pytest.mark.asyncio
    async def test_run_job_not_found(self, job_manager):
        """Should raise error if job not found"""
        # Arrange
        async def task_func(job: Job):
            return {}

        # Act & Assert
        with pytest.raises(ValueError, match="Job .* not found"):
            await job_manager.run_job("nonexistent", task_func)

    def test_cancel_job(self, job_manager):
        """Should cancel pending job"""
        # Arrange
        job = job_manager.create_job("test", {})

        # Act
        result = job_manager.cancel_job(job.job_id)

        # Assert
        assert result is True
        assert job.status == JobStatus.CANCELLED

    def test_cancel_job_already_running(self, job_manager):
        """Should not cancel running job"""
        # Arrange
        job = job_manager.create_job("test", {})
        job.mark_started()

        # Act
        result = job_manager.cancel_job(job.job_id)

        # Assert
        assert result is False
        assert job.status == JobStatus.RUNNING

    def test_cancel_job_not_found(self, job_manager):
        """Should return False if job not found"""
        # Act
        result = job_manager.cancel_job("nonexistent")

        # Assert
        assert result is False

    def test_cleanup_old_jobs(self, job_manager):
        """Should remove old completed jobs"""
        # Arrange
        old_job = job_manager.create_job("test1", {})
        old_job.mark_started()
        old_job.mark_completed(result={})
        old_job.completed_at = datetime.utcnow() - timedelta(days=8)

        recent_job = job_manager.create_job("test2", {})
        recent_job.mark_started()
        recent_job.mark_completed(result={})

        pending_job = job_manager.create_job("test3", {})

        # Act
        removed = job_manager.cleanup_old_jobs(max_age_days=7)

        # Assert
        assert removed == 1
        assert old_job.job_id not in job_manager.jobs
        assert recent_job.job_id in job_manager.jobs
        assert pending_job.job_id in job_manager.jobs

    def test_save_to_storage(self, job_manager, storage_mock):
        """Should save jobs to storage"""
        # Arrange
        job1 = job_manager.create_job("test1", {})
        job2 = job_manager.create_job("test2", {})

        # Act
        job_manager.save_to_storage()

        # Assert
        # save_jobs is called on each create_job + manual call = 3 times total
        assert storage_mock.state.save_jobs.call_count == 3
        # Check last call has both jobs
        call_args = storage_mock.state.save_jobs.call_args[0][0]
        assert len(call_args) == 2

    def test_load_from_storage(self, storage_mock):
        """Should load jobs from storage"""
        # Arrange
        job_data = {
            "job_id": "loaded-123",
            "job_type": "test",
            "status": "completed",
            "progress": 100,
            "current_step": "Done",
            "params": {},
            "result": {"success": True},
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "logs": []
        }
        storage_mock.state.load_jobs.return_value = [job_data]

        # Act
        manager = JobManager(storage=storage_mock)

        # Assert
        assert "loaded-123" in manager.jobs
        assert manager.jobs["loaded-123"].status == JobStatus.COMPLETED
