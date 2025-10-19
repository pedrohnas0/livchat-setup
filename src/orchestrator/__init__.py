"""
Orchestrator module - Refactored structure

New modular architecture (PLAN-08 refactoring)
"""

# Main orchestrator (Facade pattern)
from .core import Orchestrator

# Individual managers (can be used independently)
from .provider_manager import ProviderManager
from .server_manager import ServerManager
from .deployment_manager import DeploymentManager
from .dns_manager import DNSManager

__all__ = [
    'Orchestrator',  # Main entry point
    'ProviderManager',
    'ServerManager',
    'DeploymentManager',
    'DNSManager'
]
