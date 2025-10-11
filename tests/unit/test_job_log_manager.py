"""
Unit tests for JobLogManager

Tests the log capture system using Python logging handlers.
No mocks needed - tests actual file and memory operations.
"""

import pytest
import logging
import tempfile
import time
import os
from pathlib import Path
from datetime import datetime, timedelta

from src.job_log_manager import JobLogManager, RecentLogsHandler


class TestRecentLogsHandler:
    """Test the memory-based log handler"""

    def test_handler_stores_logs_in_memory(self):
        """Should store log records in memory deque"""
        handler = RecentLogsHandler(max_records=10)
        handler.setLevel(logging.DEBUG)

        # Create logger and add handler
        logger = logging.getLogger("test.handler.basic")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False

        # Generate logs
        logger.info("Test message 1")
        logger.warning("Test message 2")
        logger.error("Test message 3")

        # Verify stored
        logs = handler.get_recent_logs()
        assert len(logs) == 3
        assert logs[0]["message"] == "Test message 3"  # Newest first
        assert logs[0]["level"] == "ERROR"
        assert logs[1]["message"] == "Test message 2"
        assert logs[2]["message"] == "Test message 1"

        # Cleanup
        logger.removeHandler(handler)
        handler.close()

    def test_handler_respects_max_records(self):
        """Should only keep last N records"""
        handler = RecentLogsHandler(max_records=3)
        logger = logging.getLogger("test.handler.maxrecords")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False

        # Generate more than max
        for i in range(10):
            logger.info(f"Message {i}")

        # Should only have last 3
        logs = handler.get_recent_logs()
        assert len(logs) == 3
        assert logs[0]["message"] == "Message 9"
        assert logs[1]["message"] == "Message 8"
        assert logs[2]["message"] == "Message 7"

        # Cleanup
        logger.removeHandler(handler)
        handler.close()

    def test_handler_get_recent_logs_with_limit(self):
        """Should return only requested number of logs"""
        handler = RecentLogsHandler(max_records=10)
        logger = logging.getLogger("test.handler.limit")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False

        for i in range(10):
            logger.info(f"Message {i}")

        # Get only 5
        logs = handler.get_recent_logs(limit=5)
        assert len(logs) == 5
        assert logs[0]["message"] == "Message 9"
        assert logs[4]["message"] == "Message 5"

        # Cleanup
        logger.removeHandler(handler)
        handler.close()

    def test_handler_clear_removes_all_logs(self):
        """Should clear all logs from memory"""
        handler = RecentLogsHandler(max_records=10)
        logger = logging.getLogger("test.handler.clear")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False

        logger.info("Message 1")
        logger.info("Message 2")

        assert len(handler.get_recent_logs()) == 2

        # Clear
        handler.clear()

        assert len(handler.get_recent_logs()) == 0

        # Cleanup
        logger.removeHandler(handler)
        handler.close()

    def test_handler_includes_timestamp_and_level(self):
        """Should include timestamp and level in each log entry"""
        handler = RecentLogsHandler(max_records=10)
        logger = logging.getLogger("test.handler.metadata")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.propagate = False

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        logs = handler.get_recent_logs()
        assert len(logs) == 4

        for log in logs:
            assert "timestamp" in log
            assert "level" in log
            assert "message" in log
            # Verify timestamp format (ISO 8601)
            datetime.fromisoformat(log["timestamp"])

        assert logs[0]["level"] == "ERROR"
        assert logs[1]["level"] == "WARNING"
        assert logs[2]["level"] == "INFO"
        assert logs[3]["level"] == "DEBUG"

        # Cleanup
        logger.removeHandler(handler)
        handler.close()


class TestJobLogManager:
    """Test the JobLogManager class"""

    @pytest.fixture
    def temp_logs_dir(self):
        """Create temporary logs directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def log_manager(self, temp_logs_dir):
        """Create JobLogManager instance"""
        return JobLogManager(temp_logs_dir)

    def test_init_creates_jobs_directory(self, temp_logs_dir):
        """Should create logs/jobs/ directory on init"""
        manager = JobLogManager(temp_logs_dir)
        assert (temp_logs_dir / "jobs").exists()
        assert (temp_logs_dir / "jobs").is_dir()

    def test_start_job_logging_creates_log_file(self, log_manager):
        """Should create log file when starting job logging"""
        job_id = "test-job-123"

        log_file = log_manager.start_job_logging(job_id)

        assert log_file.exists()
        assert log_file.name == f"{job_id}.log"
        assert job_id in log_manager.handlers
        assert job_id in log_manager.memory_handlers

        # Cleanup
        log_manager.stop_job_logging(job_id)

    def test_start_job_logging_captures_logs_to_file(self, log_manager):
        """Should capture logs to file"""
        job_id = "test-job-456"
        log_file = log_manager.start_job_logging(job_id)

        # Generate logs from monitored module
        logger = logging.getLogger("src.orchestrator")
        logger.info("Test message from orchestrator")
        logger.warning("Warning message")

        # Stop to flush
        log_manager.stop_job_logging(job_id)

        # Read file
        content = log_file.read_text()
        assert "Test message from orchestrator" in content
        assert "Warning message" in content
        assert "INFO" in content
        assert "WARNING" in content

    def test_start_job_logging_captures_logs_in_memory(self, log_manager):
        """Should capture logs in memory handler"""
        job_id = "test-job-789"
        log_manager.start_job_logging(job_id)

        # Generate logs
        logger = logging.getLogger("src.server_setup")
        logger.info("Setup started")
        logger.error("Setup failed")

        # Get recent logs
        recent = log_manager.get_recent_logs(job_id, limit=10)

        assert len(recent) == 2
        assert recent[0]["message"] == "Setup failed"
        assert recent[0]["level"] == "ERROR"
        assert recent[1]["message"] == "Setup started"
        assert recent[1]["level"] == "INFO"

        # Cleanup
        log_manager.stop_job_logging(job_id)

    def test_start_job_logging_captures_from_multiple_modules(self, log_manager):
        """Should capture logs from all monitored modules"""
        job_id = "test-multi-module"
        log_manager.start_job_logging(job_id)

        # Log from different modules
        logging.getLogger("src.orchestrator").info("From orchestrator")
        logging.getLogger("src.server_setup").info("From server_setup")
        logging.getLogger("src.ansible_executor").info("From ansible")
        logging.getLogger("src.providers").info("From providers")

        recent = log_manager.get_recent_logs(job_id)

        assert len(recent) == 4
        messages = [log["message"] for log in recent]
        assert "From orchestrator" in messages
        assert "From server_setup" in messages
        assert "From ansible" in messages
        assert "From providers" in messages

        # Cleanup
        log_manager.stop_job_logging(job_id)

    def test_start_job_logging_idempotent(self, log_manager):
        """Should handle multiple calls to start_job_logging for same job"""
        job_id = "test-idempotent"

        log_file1 = log_manager.start_job_logging(job_id)
        log_file2 = log_manager.start_job_logging(job_id)

        # Should return same file
        assert log_file1 == log_file2

        # Cleanup
        log_manager.stop_job_logging(job_id)

    def test_stop_job_logging_removes_handlers(self, log_manager):
        """Should remove handlers and close files"""
        job_id = "test-stop"
        log_file = log_manager.start_job_logging(job_id)

        assert job_id in log_manager.handlers
        assert job_id in log_manager.memory_handlers

        log_manager.stop_job_logging(job_id)

        assert job_id not in log_manager.handlers
        assert job_id not in log_manager.memory_handlers

    def test_stop_job_logging_no_more_capture(self, log_manager):
        """Should not capture logs after stopping"""
        job_id = "test-no-capture"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.orchestrator")
        logger.info("Before stop")

        log_manager.stop_job_logging(job_id)

        logger.info("After stop")

        # Should not have "After stop" in recent logs
        recent = log_manager.get_recent_logs(job_id)
        assert len(recent) == 0  # Memory handler was removed

    def test_get_recent_logs_returns_empty_for_unknown_job(self, log_manager):
        """Should return empty list for unknown job"""
        logs = log_manager.get_recent_logs("unknown-job")
        assert logs == []

    def test_get_recent_logs_respects_limit(self, log_manager):
        """Should return only requested number of logs"""
        job_id = "test-limit"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.orchestrator")
        for i in range(20):
            logger.info(f"Message {i}")

        # Request only 10
        recent = log_manager.get_recent_logs(job_id, limit=10)
        assert len(recent) == 10
        assert recent[0]["message"] == "Message 19"
        assert recent[9]["message"] == "Message 10"

        # Cleanup
        log_manager.stop_job_logging(job_id)

    def test_read_log_file_returns_lines(self, log_manager):
        """Should read log file and return lines"""
        job_id = "test-read-file"
        log_file = log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.server_setup")
        logger.info("Line 1")
        logger.info("Line 2")
        logger.info("Line 3")

        # Stop to flush
        log_manager.stop_job_logging(job_id)

        # Read file
        lines = log_manager.read_log_file(job_id, tail=10)

        assert len(lines) == 3
        assert "Line 1" in lines[0]
        assert "Line 2" in lines[1]
        assert "Line 3" in lines[2]

    def test_read_log_file_respects_tail(self, log_manager):
        """Should return only last N lines"""
        job_id = "test-tail"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.orchestrator")
        for i in range(100):
            logger.info(f"Line {i}")

        log_manager.stop_job_logging(job_id)

        # Read last 10
        lines = log_manager.read_log_file(job_id, tail=10)

        assert len(lines) == 10
        assert "Line 99" in lines[-1]
        assert "Line 90" in lines[0]

    def test_read_log_file_filters_by_level(self, log_manager):
        """Should filter lines by log level"""
        job_id = "test-filter"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.ansible_executor")
        logger.info("Info 1")
        logger.error("Error 1")
        logger.info("Info 2")
        logger.error("Error 2")
        logger.warning("Warning 1")

        log_manager.stop_job_logging(job_id)

        # Filter ERROR only
        lines = log_manager.read_log_file(job_id, tail=100, level_filter="ERROR")

        assert len(lines) == 2
        assert "Error 1" in lines[0]
        assert "Error 2" in lines[1]

    def test_read_log_file_returns_empty_for_nonexistent(self, log_manager):
        """Should return empty list for nonexistent file"""
        lines = log_manager.read_log_file("nonexistent-job")
        assert lines == []

    def test_cleanup_old_logs_removes_old_files(self, log_manager):
        """Should remove log files older than threshold"""
        # Create old log file
        old_job_id = "old-job"
        old_log = log_manager.logs_dir / f"{old_job_id}.log"
        old_log.write_text("old log content")

        # Set mtime to 80 hours ago
        old_time = time.time() - (80 * 3600)
        os.utime(old_log, (old_time, old_time))

        # Create recent log file
        recent_job_id = "recent-job"
        recent_log = log_manager.logs_dir / f"{recent_job_id}.log"
        recent_log.write_text("recent log content")

        # Cleanup (remove > 72h)
        removed = log_manager.cleanup_old_logs(max_age_hours=72)

        assert removed == 1
        assert not old_log.exists()
        assert recent_log.exists()

    def test_cleanup_old_logs_keeps_recent_files(self, log_manager):
        """Should not remove recent files"""
        job_id = "recent"
        log_file = log_manager.logs_dir / f"{job_id}.log"
        log_file.write_text("recent content")

        removed = log_manager.cleanup_old_logs(max_age_hours=72)

        assert removed == 0
        assert log_file.exists()

    def test_cleanup_old_logs_returns_count(self, log_manager):
        """Should return number of files removed"""
        # Create 3 old files
        for i in range(3):
            old_log = log_manager.logs_dir / f"old-{i}.log"
            old_log.write_text("old")
            old_time = time.time() - (80 * 3600)
            os.utime(old_log, (old_time, old_time))

        removed = log_manager.cleanup_old_logs(max_age_hours=72)

        assert removed == 3

    def test_multiple_jobs_concurrent_logging(self, log_manager):
        """Should handle multiple jobs logging concurrently"""
        job1 = "concurrent-1"
        job2 = "concurrent-2"

        log_manager.start_job_logging(job1)
        log_manager.start_job_logging(job2)

        logger1 = logging.getLogger("src.orchestrator")
        logger2 = logging.getLogger("src.server_setup")

        logger1.info("From job 1")
        logger2.info("From job 2")

        # Both should have logs
        logs1 = log_manager.get_recent_logs(job1)
        logs2 = log_manager.get_recent_logs(job2)

        # Job 1 should have both (orchestrator is monitored)
        assert any("From job 1" in log["message"] for log in logs1)

        # Job 2 should have both (server_setup is monitored)
        assert any("From job 2" in log["message"] for log in logs2)

        # Cleanup
        log_manager.stop_job_logging(job1)
        log_manager.stop_job_logging(job2)

    def test_log_file_rotation(self, log_manager):
        """Should rotate log file when exceeds max size"""
        job_id = "test-rotation"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.orchestrator")

        # Generate lots of logs to trigger rotation
        # RotatingFileHandler with 10MB max
        for i in range(1000):
            logger.info(f"Message {i} " * 100)  # ~1KB per message

        log_file = log_manager.logs_dir / f"{job_id}.log"
        file_size = log_file.stat().st_size

        # Should not exceed 10MB by much
        assert file_size < 11 * 1024 * 1024  # Allow 1MB overage

        # Cleanup
        log_manager.stop_job_logging(job_id)


class TestJobLogManagerEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def temp_logs_dir(self):
        """Create temporary logs directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def log_manager(self, temp_logs_dir):
        """Create JobLogManager instance"""
        return JobLogManager(temp_logs_dir)

    def test_handles_unicode_in_logs(self, log_manager):
        """Should handle unicode characters in log messages"""
        job_id = "unicode-test"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.orchestrator")
        logger.info("测试 тест ทดสอบ 🚀")

        recent = log_manager.get_recent_logs(job_id)
        assert len(recent) == 1
        assert "测试 тест ทดสอบ 🚀" in recent[0]["message"]

        log_manager.stop_job_logging(job_id)

    def test_handles_multiline_logs(self, log_manager):
        """Should handle multiline log messages"""
        job_id = "multiline-test"
        log_manager.start_job_logging(job_id)

        logger = logging.getLogger("src.ansible_executor")
        logger.info("Line 1\nLine 2\nLine 3")

        recent = log_manager.get_recent_logs(job_id)
        assert len(recent) == 1
        assert "Line 1" in recent[0]["message"]
        assert "Line 2" in recent[0]["message"]

        log_manager.stop_job_logging(job_id)

    def test_stop_nonexistent_job_no_error(self, log_manager):
        """Should handle stopping nonexistent job gracefully"""
        # Should not raise
        log_manager.stop_job_logging("nonexistent")

    def test_cleanup_with_no_old_logs(self, log_manager):
        """Should handle cleanup when no old logs exist"""
        removed = log_manager.cleanup_old_logs(max_age_hours=72)
        assert removed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
