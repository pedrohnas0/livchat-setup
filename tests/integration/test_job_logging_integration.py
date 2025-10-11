"""
Integration tests for JobLogManager + JobManager

Tests the complete log capture flow:
1. JobManager.run_job() starts log capture
2. Logs from monitored modules are captured
3. Recent logs available in memory
4. Full logs available in file
5. Cleanup works correctly
"""

import pytest
import asyncio
import logging
import tempfile
from pathlib import Path

from src.job_manager import JobManager, Job
from src.storage import StorageManager


class TestJobLoggingIntegration:
    """Integration tests for job logging system"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for storage"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def job_manager(self, temp_dir):
        """Create JobManager with temporary storage"""
        storage = StorageManager(temp_dir)
        manager = JobManager(storage)
        # Override logs_dir to use temp directory
        manager.log_manager.logs_dir = temp_dir / "logs" / "jobs"
        manager.log_manager.logs_dir.mkdir(parents=True, exist_ok=True)
        return manager

    @pytest.mark.asyncio
    async def test_job_execution_captures_logs(self, job_manager):
        """Should capture logs during job execution"""
        # Create job
        job = job_manager.create_job("test_job", {"param": "value"})

        # Define task that generates logs
        async def test_task(job: Job):
            # Generate logs from monitored module
            logger = logging.getLogger("src.orchestrator")
            logger.info("Task started")
            logger.info("Processing step 1")
            logger.warning("Warning during processing")
            logger.info("Task completed")

            return {"success": True, "result": "done"}

        # Run job (logs should be captured)
        await job_manager.run_job(job.job_id, test_task)

        # Verify job completed
        assert job.status.value == "completed"
        assert job.log_file is not None

        # Verify log file exists
        log_file = Path(job.log_file)
        assert log_file.exists()

        # Read log file
        content = log_file.read_text()
        assert "Task started" in content
        assert "Processing step 1" in content
        assert "Warning during processing" in content
        assert "Task completed" in content

        # Verify logs are in memory (should be empty after job stops)
        recent = job_manager.log_manager.get_recent_logs(job.job_id)
        assert len(recent) == 0  # Handlers removed after job completes

    @pytest.mark.asyncio
    async def test_recent_logs_available_during_execution(self, job_manager):
        """Should have recent logs available in memory during execution"""
        job = job_manager.create_job("test_job_2", {})

        logs_captured = []

        async def task_with_monitoring(job: Job):
            logger = logging.getLogger("src.server_setup")

            # Generate some logs
            for i in range(10):
                logger.info(f"Step {i}")
                await asyncio.sleep(0.01)

            # Check recent logs while job is running
            recent = job_manager.log_manager.get_recent_logs(job.job_id, limit=5)
            logs_captured.extend(recent)

            return {"success": True}

        await job_manager.run_job(job.job_id, task_with_monitoring)

        # Verify we captured logs during execution
        assert len(logs_captured) > 0
        assert any("Step" in log["message"] for log in logs_captured)

    @pytest.mark.asyncio
    async def test_error_logs_captured(self, job_manager):
        """Should capture error logs when job fails"""
        job = job_manager.create_job("failing_job", {})

        async def failing_task(job: Job):
            logger = logging.getLogger("src.ansible_executor")
            logger.info("Starting task")
            logger.error("Critical error occurred")
            raise RuntimeError("Task failed!")

        # Run job (should fail)
        await job_manager.run_job(job.job_id, failing_task)

        # Verify job failed
        assert job.status.value == "failed"
        assert "RuntimeError" in job.error

        # Verify error logs captured
        log_file = Path(job.log_file)
        content = log_file.read_text()
        assert "Starting task" in content
        assert "Critical error occurred" in content

    @pytest.mark.asyncio
    async def test_multiple_jobs_concurrent_logging(self, job_manager):
        """Should handle multiple jobs logging concurrently"""
        jobs = []
        for i in range(3):
            job = job_manager.create_job(f"concurrent_job_{i}", {"index": i})
            jobs.append(job)

        async def concurrent_task(job: Job):
            logger = logging.getLogger("src.orchestrator")
            job_index = job.params["index"]

            for step in range(5):
                logger.info(f"Job {job_index} - Step {step}")
                await asyncio.sleep(0.01)

            return {"job_index": job_index}

        # Run jobs concurrently
        tasks = [
            job_manager.run_job(job.job_id, concurrent_task)
            for job in jobs
        ]
        await asyncio.gather(*tasks)

        # Verify all jobs completed
        for job in jobs:
            assert job.status.value == "completed"
            assert job.log_file is not None

            # Verify each job has its own log file
            log_file = Path(job.log_file)
            assert log_file.exists()

            # Verify logs contain job-specific content
            content = log_file.read_text()
            job_index = job.params["index"]
            assert f"Job {job_index}" in content

    @pytest.mark.asyncio
    async def test_log_file_rotation(self, job_manager):
        """Should handle log rotation for large logs"""
        job = job_manager.create_job("large_log_job", {})

        async def large_log_task(job: Job):
            logger = logging.getLogger("src.providers")

            # Generate ~500KB of logs
            for i in range(500):
                logger.info(f"Large message {i}: " + ("X" * 1000))

            return {"success": True}

        await job_manager.run_job(job.job_id, large_log_task)

        # Verify log file exists and is reasonable size
        log_file = Path(job.log_file)
        assert log_file.exists()

        file_size = log_file.stat().st_size
        # Should be less than 10MB (rotation limit)
        assert file_size < 10 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_unicode_logs_handled_correctly(self, job_manager):
        """Should handle unicode characters in logs"""
        job = job_manager.create_job("unicode_job", {})

        async def unicode_task(job: Job):
            logger = logging.getLogger("src.orchestrator")
            logger.info("Testing unicode: 测试 тест ทดสอบ 🚀")
            logger.info("Emojis: 🎉 ✅ ❌ 🔧 🐘")
            return {"success": True}

        await job_manager.run_job(job.job_id, unicode_task)

        # Verify unicode saved correctly
        log_file = Path(job.log_file)
        content = log_file.read_text(encoding='utf-8')
        assert "测试 тест ทดสอบ 🚀" in content
        assert "🎉 ✅ ❌" in content

    @pytest.mark.asyncio
    async def test_log_cleanup_integration(self, job_manager):
        """Should cleanup old log files"""
        import time
        import os

        # Create job and run it
        job = job_manager.create_job("cleanup_test", {})

        async def simple_task(job: Job):
            logger = logging.getLogger("src.orchestrator")
            logger.info("Test log")
            return {"success": True}

        await job_manager.run_job(job.job_id, simple_task)

        # Verify log file created
        log_file = Path(job.log_file)
        assert log_file.exists()

        # Set file mtime to 80 hours ago
        old_time = time.time() - (80 * 3600)
        os.utime(log_file, (old_time, old_time))

        # Run cleanup
        removed = job_manager.log_manager.cleanup_old_logs(max_age_hours=72)

        # Verify file was removed
        assert removed == 1
        assert not log_file.exists()


class TestJobLoggingWithRealModules:
    """Test log capture from actual orchestrator/server_setup modules"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def job_manager(self, temp_dir):
        storage = StorageManager(temp_dir)
        manager = JobManager(storage)
        manager.log_manager.logs_dir = temp_dir / "logs" / "jobs"
        manager.log_manager.logs_dir.mkdir(parents=True, exist_ok=True)
        return manager

    @pytest.mark.asyncio
    async def test_captures_logs_from_orchestrator_module(self, job_manager):
        """Should capture logs from actual src.orchestrator module"""
        job = job_manager.create_job("orchestrator_test", {})

        async def task_using_orchestrator(job: Job):
            # Import and use actual orchestrator logger
            from src.orchestrator import logger as orch_logger

            orch_logger.info("Orchestrator: Starting operation")
            orch_logger.debug("Orchestrator: Debug info")
            orch_logger.warning("Orchestrator: Warning message")

            return {"success": True}

        await job_manager.run_job(job.job_id, task_using_orchestrator)

        # Verify logs captured
        log_file = Path(job.log_file)
        content = log_file.read_text()

        assert "Orchestrator: Starting operation" in content
        assert "Orchestrator: Debug info" in content
        assert "Orchestrator: Warning message" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
