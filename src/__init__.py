"""LivChat Setup - Automated server setup and application deployment"""

# Configure logging at module level
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Public API imports
from .orchestrator import Orchestrator
from .storage import StorageManager, StateStore, SecretsStore

# Compatibility alias
LivChatSetup = Orchestrator

# Version info
__version__ = "0.2.7"

# Public exports
__all__ = [
    "Orchestrator",
    "StorageManager",
    "StateStore",
    "SecretsStore",
    # Compatibility exports
    "LivChatSetup",  # Alias for Orchestrator
]
