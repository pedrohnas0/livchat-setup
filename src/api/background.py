"""
Background Tasks Management for FastAPI

Provides lifespan context manager that starts/stops the JobExecutor
during FastAPI application startup/shutdown.

Usage:
    from src.api.background import lifespan

    app = FastAPI(lifespan=lifespan)
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src.job_executor import JobExecutor
from src.api.dependencies import get_orchestrator, get_job_manager

logger = logging.getLogger(__name__)

# Global reference to executor (managed by lifespan)
_executor: JobExecutor | None = None


async def log_cleanup_loop(job_manager):
    """
    Background task to cleanup old log files periodically

    Runs every hour and removes log files older than 72 hours.

    Args:
        job_manager: JobManager instance with log_manager
    """
    while True:
        try:
            # Sleep for 1 hour
            await asyncio.sleep(3600)

            # Cleanup logs older than 72 hours
            removed = job_manager.log_manager.cleanup_old_logs(max_age_hours=72)

            if removed > 0:
                logger.info(f"Cleaned up {removed} old log files (>72h)")

        except asyncio.CancelledError:
            logger.info("Log cleanup task cancelled")
            break

        except Exception as e:
            logger.error(f"Error in log cleanup: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager

    Startup:
    - Initialize JobExecutor
    - Start background job processing
    - Start log cleanup task

    Shutdown:
    - Stop JobExecutor gracefully
    - Cancel log cleanup task
    - Wait for running jobs to complete

    Args:
        app: FastAPI application instance

    Yields:
        None (during application runtime)
    """
    global _executor

    # ==========================================
    # STARTUP
    # ==========================================
    logger.info("🚀 Starting LivChat Setup API...")

    try:
        # Get singleton instances
        orchestrator = get_orchestrator()
        job_manager = get_job_manager()

        # Create and start JobExecutor
        _executor = JobExecutor(job_manager, orchestrator)
        await _executor.start()
        logger.info("✅ JobExecutor started successfully")

        # Start log cleanup background task
        cleanup_task = asyncio.create_task(log_cleanup_loop(job_manager))
        logger.info("✅ Log cleanup task started")

        logger.info("✅ LivChat Setup API ready!")

    except Exception as e:
        logger.error(f"❌ Failed to start API: {e}", exc_info=True)
        raise

    # ==========================================
    # YIELD - Application running
    # ==========================================
    yield

    # ==========================================
    # SHUTDOWN
    # ==========================================
    logger.info("🛑 Shutting down LivChat Setup API...")

    try:
        # Cancel cleanup task
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # Stop executor
        if _executor:
            logger.info("Stopping JobExecutor...")
            await _executor.stop()
            logger.info("✅ JobExecutor stopped gracefully")

        logger.info("✅ LivChat Setup API shutdown complete")

    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}", exc_info=True)


def get_executor() -> JobExecutor | None:
    """
    Get the global JobExecutor instance

    Returns:
        JobExecutor instance if started, None otherwise

    Note:
        This is primarily for debugging/monitoring.
        Most operations should go through the API, not directly to the executor.
    """
    return _executor
