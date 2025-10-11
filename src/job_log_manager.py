"""
Job Log Manager - Observability System

Captures logs from Python logging system using handlers.
NO CODE CHANGES needed in orchestrator, server_setup, etc.

Architecture:
- RecentLogsHandler: Keeps last N logs in memory (fast API responses)
- FileHandler: Writes all logs to disk (complete history)
- Handlers attached to monitored modules (src.orchestrator, src.server_setup, etc.)

Usage:
    manager = JobLogManager(logs_dir)
    manager.start_job_logging(job_id)
    # Logs are automatically captured!
    manager.stop_job_logging(job_id)
"""

import logging
import os
import time
from collections import deque
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RecentLogsHandler(logging.Handler):
    """
    Custom logging handler that keeps recent log records in memory

    Stores last N log records in a deque for fast retrieval.
    Perfect for API responses that need recent logs without disk I/O.

    Attributes:
        max_records: Maximum number of records to keep (default: 100)
        records: Deque of log records
    """

    def __init__(self, max_records: int = 100):
        """
        Initialize handler

        Args:
            max_records: Maximum number of records to keep
        """
        super().__init__()
        self.max_records = max_records
        self.records = deque(maxlen=max_records)

    def emit(self, record: logging.LogRecord):
        """
        Store log record in memory

        Args:
            record: LogRecord from Python logging system
        """
        try:
            self.records.append({
                "timestamp": self._format_time(record),
                "level": record.levelname,
                "message": record.getMessage()
            })
        except Exception:
            self.handleError(record)

    def _format_time(self, record: logging.LogRecord) -> str:
        """Format timestamp as ISO 8601"""
        return datetime.fromtimestamp(record.created).isoformat()

    def get_recent_logs(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get recent logs (newest first)

        Args:
            limit: Maximum number of logs to return (None = all)

        Returns:
            List of log dicts with timestamp, level, message
        """
        logs = list(self.records)
        logs.reverse()  # Newest first

        if limit and limit < len(logs):
            logs = logs[:limit]

        return logs

    def clear(self):
        """Clear all logs from memory"""
        self.records.clear()


class JobLogManager:
    """
    Manages log capture for jobs using Python logging handlers

    Features:
    - Captures logs to file (complete, rotated at 10MB)
    - Keeps last 100 lines in memory (fast API access)
    - Logs expire automatically after 72h
    - Thread-safe (Python logging is)
    - Zero code changes needed in monitored modules

    The magic: When a job starts, we add handlers to relevant loggers.
    All existing logger.info() calls are automatically captured!
    """

    # Modules to monitor (add handlers to these loggers)
    MONITORED_MODULES = [
        'src.orchestrator',
        'src.server_setup',
        'src.ansible_executor',
        'src.app_deployer',
        'src.providers',
        'src.integrations'
    ]

    def __init__(self, logs_dir: Path):
        """
        Initialize JobLogManager

        Args:
            logs_dir: Base directory for logs (usually ~/.livchat/logs)
        """
        self.logs_dir = logs_dir / "jobs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Track active handlers by job_id
        self.handlers: Dict[str, List[logging.Handler]] = {}
        self.memory_handlers: Dict[str, RecentLogsHandler] = {}

        logger.debug(f"JobLogManager initialized with logs_dir: {self.logs_dir}")

    def start_job_logging(self, job_id: str) -> Path:
        """
        Start capturing logs for a job

        Creates file and memory handlers and attaches them to monitored modules.
        From this point, ALL logs from those modules are captured.

        Args:
            job_id: Unique job identifier

        Returns:
            Path to the log file
        """
        log_file = self.logs_dir / f"{job_id}.log"

        # If already logging this job, return existing file
        if job_id in self.handlers:
            logger.debug(f"Job {job_id} already has active logging")
            return log_file

        # Create FileHandler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB max
            backupCount=0,  # No backup, logs expire
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # Create MemoryHandler for fast access
        memory_handler = RecentLogsHandler(max_records=100)
        memory_handler.setLevel(logging.DEBUG)

        # Add handlers to monitored modules
        handlers = [file_handler, memory_handler]
        for module_name in self.MONITORED_MODULES:
            module_logger = logging.getLogger(module_name)
            # Set logger level to DEBUG (otherwise it filters before handlers)
            module_logger.setLevel(logging.DEBUG)
            for handler in handlers:
                module_logger.addHandler(handler)

        # Store references
        self.handlers[job_id] = handlers
        self.memory_handlers[job_id] = memory_handler

        logger.info(f"Started log capture for job {job_id} → {log_file}")

        return log_file

    def stop_job_logging(self, job_id: str):
        """
        Stop capturing logs and remove handlers

        Args:
            job_id: Job identifier
        """
        if job_id not in self.handlers:
            logger.debug(f"No active logging for job {job_id}")
            return

        handlers = self.handlers[job_id]

        # Remove handlers from all monitored modules
        for module_name in self.MONITORED_MODULES:
            module_logger = logging.getLogger(module_name)
            for handler in handlers:
                try:
                    module_logger.removeHandler(handler)
                except ValueError:
                    # Handler not in logger (ok)
                    pass

        # Close handlers (flush and close files)
        for handler in handlers:
            try:
                handler.close()
            except Exception as e:
                logger.warning(f"Error closing handler for job {job_id}: {e}")

        # Remove references
        del self.handlers[job_id]
        del self.memory_handlers[job_id]

        logger.info(f"Stopped log capture for job {job_id}")

    def get_recent_logs(self, job_id: str, limit: int = 50) -> List[Dict[str, str]]:
        """
        Get recent logs from memory (O(1), no disk I/O)

        Args:
            job_id: Job identifier
            limit: Maximum number of logs to return (default: 50)

        Returns:
            List of log dicts with timestamp, level, message
        """
        if job_id not in self.memory_handlers:
            return []

        return self.memory_handlers[job_id].get_recent_logs(limit)

    def read_log_file(
        self,
        job_id: str,
        tail: int = 100,
        level_filter: Optional[str] = None
    ) -> List[str]:
        """
        Read log file from disk (last N lines)

        Args:
            job_id: Job identifier
            tail: Number of lines from end to read (default: 100)
            level_filter: Filter by log level (DEBUG, INFO, WARNING, ERROR)

        Returns:
            List of log lines
        """
        log_file = self.logs_dir / f"{job_id}.log"

        if not log_file.exists():
            return []

        # Read last N lines efficiently
        lines = self._tail_file(log_file, tail)

        # Filter by level if specified
        if level_filter:
            lines = [line for line in lines if level_filter in line]

        return lines

    def _tail_file(self, file_path: Path, n: int) -> List[str]:
        """
        Read last N lines from file efficiently

        Uses reverse reading to avoid loading entire file into memory.

        Args:
            file_path: Path to file
            n: Number of lines to read

        Returns:
            List of last N lines
        """
        try:
            with open(file_path, 'rb') as f:
                # Seek to end
                f.seek(0, 2)
                file_size = f.tell()

                if file_size == 0:
                    return []

                # Read in chunks from end
                buffer_size = 8192
                buffer = b''
                position = file_size

                while True:
                    # Calculate how much to read
                    read_size = min(buffer_size, position)
                    if read_size == 0:
                        break

                    position -= read_size
                    f.seek(position)

                    # Read chunk and prepend to buffer
                    chunk = f.read(read_size)
                    buffer = chunk + buffer

                    # Count lines
                    lines = buffer.decode('utf-8', errors='ignore').splitlines()
                    if len(lines) >= n:
                        return lines[-n:]

                    if position == 0:
                        break

                # Return all lines if file smaller than n
                return buffer.decode('utf-8', errors='ignore').splitlines()

        except Exception as e:
            logger.error(f"Error reading log file {file_path}: {e}")
            return []

    def cleanup_old_logs(self, max_age_hours: int = 72) -> int:
        """
        Remove log files older than threshold

        Args:
            max_age_hours: Maximum age in hours (default: 72)

        Returns:
            Number of files removed
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed = 0

        try:
            for log_file in self.logs_dir.glob("*.log"):
                try:
                    # Check file modification time
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        removed += 1
                        logger.debug(f"Removed old log file: {log_file.name}")

                except Exception as e:
                    logger.warning(f"Failed to delete {log_file}: {e}")

            if removed > 0:
                logger.info(f"Cleaned up {removed} old log files (>{max_age_hours}h)")

        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")

        return removed
