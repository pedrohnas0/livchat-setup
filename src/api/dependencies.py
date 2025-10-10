"""
Dependency injection for FastAPI

Provides singleton instances shared across all API requests:
- Orchestrator: Core orchestration logic
- JobManager: Async job management
"""

from typing import Optional
import logging

try:
    from ..orchestrator import Orchestrator
    from ..job_manager import JobManager
except ImportError:
    from src.orchestrator import Orchestrator
    from src.job_manager import JobManager

logger = logging.getLogger(__name__)

# Global singleton instances
_orchestrator: Optional[Orchestrator] = None
_job_manager: Optional[JobManager] = None


def get_orchestrator() -> Orchestrator:
    """
    Get or create Orchestrator singleton

    This function is used as a FastAPI dependency via Depends(get_orchestrator).
    Returns the same Orchestrator instance for all API requests.

    Returns:
        Orchestrator: Singleton orchestrator instance
    """
    global _orchestrator

    if _orchestrator is None:
        logger.info("Initializing Orchestrator singleton for API")

        # Create new orchestrator instance
        _orchestrator = Orchestrator()

        # Initialize (creates ~/.livchat if needed)
        _orchestrator.init()

        # Try to load existing configuration
        # This allows API to work with CLI-configured system
        try:
            _orchestrator.storage.config.load()
            _orchestrator.storage.state.load()
            logger.info("Loaded existing configuration and state")
        except Exception as e:
            logger.debug(f"No existing config to load (this is OK): {e}")
            # Not an error - system might not be initialized yet

    return _orchestrator


def reset_orchestrator() -> None:
    """
    Reset the orchestrator singleton

    Used for testing to ensure clean state between tests.
    Should NOT be used in production code.
    """
    global _orchestrator
    _orchestrator = None
    logger.debug("Orchestrator singleton reset")


def get_job_manager() -> JobManager:
    """
    Get or create JobManager singleton

    This function is used as a FastAPI dependency via Depends(get_job_manager).
    Returns the same JobManager instance for all API requests.

    Returns:
        JobManager: Singleton job manager instance
    """
    global _job_manager

    if _job_manager is None:
        logger.info("Initializing JobManager singleton for API")

        # Get orchestrator (creates storage if needed)
        orchestrator = get_orchestrator()

        # Create job manager with orchestrator's storage
        _job_manager = JobManager(storage=orchestrator.storage)

        logger.info(f"JobManager initialized with {len(_job_manager.jobs)} loaded jobs")

    return _job_manager


def reset_job_manager() -> None:
    """
    Reset the job manager singleton

    Used for testing to ensure clean state between tests.
    Should NOT be used in production code.
    """
    global _job_manager
    _job_manager = None
    logger.debug("JobManager singleton reset")
