"""LivChat Setup - Automated server setup and application deployment"""

# Configure logging at module level
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Public API imports
from .orchestrator import Orchestrator, LivChatSetup
from .storage import StorageManager, ConfigStore, StateStore, SecretsStore

# Version info
__version__ = "0.2.0"  # v0.2.0: DNS-first architecture, automatic dependencies

# Public exports
__all__ = [
    "Orchestrator",
    "StorageManager",
    "ConfigStore",
    "StateStore",
    "SecretsStore",
    # Compatibility exports
    "LivChatSetup",  # Alias for Orchestrator
]