"""LivChat Setup - Automated server setup and application deployment"""

# Configure logging at module level
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Public API imports
from .orchestrator_old import Orchestrator, LivChatSetup
from .storage import StorageManager, StateStore, SecretsStore

# Version info
__version__ = "0.2.5"  # v0.2.5: Removed ConfigStore, settings in state.json

# Public exports
__all__ = [
    "Orchestrator",
    "StorageManager",
    "StateStore",
    "SecretsStore",
    # Compatibility exports
    "LivChatSetup",  # Alias for Orchestrator
]
