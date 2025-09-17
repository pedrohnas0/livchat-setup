"""State management for LivChat Setup"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import shutil

logger = logging.getLogger(__name__)


class StateManager:
    """Manages state persistence"""

    def __init__(self, config_dir: Path):
        """
        Initialize StateManager

        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.state_file = config_dir / "state.json"
        self._state = {"servers": {}}

    def init(self) -> None:
        """Initialize state file"""
        if not self.state_file.exists():
            logger.info("Creating initial state file")
            self.save_state()
        else:
            logger.info("State file already exists")
            self.load_state()

    def load_state(self) -> dict:
        """
        Load state from file

        Returns:
            State dictionary
        """
        if self.state_file.exists():
            logger.debug(f"Loading state from {self.state_file}")
            with open(self.state_file, 'r') as f:
                self._state = json.load(f)
        else:
            logger.warning("State file not found, using empty state")
            self._state = {"servers": {}}

        return self._state

    def save_state(self) -> None:
        """Save state to file with backup"""
        # Create backup if file exists
        if self.state_file.exists():
            backup_file = self.state_file.with_suffix('.json.backup')
            shutil.copy2(self.state_file, backup_file)
            logger.debug(f"Created backup at {backup_file}")

        logger.debug(f"Saving state to {self.state_file}")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, 'w') as f:
            json.dump(self._state, f, indent=2, default=str)

    def add_server(self, name: str, server_data: Dict[str, Any]) -> None:
        """
        Add a server to state

        Args:
            name: Server name
            server_data: Server information
        """
        if not self._state:
            self.load_state()

        # Add timestamp
        server_data["created_at"] = datetime.now().isoformat()

        # Ensure servers key exists
        if "servers" not in self._state:
            self._state["servers"] = {}

        self._state["servers"][name] = server_data
        self.save_state()
        logger.info(f"Added server {name} to state")

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get server by name

        Args:
            name: Server name

        Returns:
            Server data or None
        """
        if not self._state:
            self.load_state()

        return self._state.get("servers", {}).get(name)

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """
        List all servers

        Returns:
            Dictionary of all servers
        """
        if not self._state:
            self.load_state()

        return self._state.get("servers", {})

    def remove_server(self, name: str) -> bool:
        """
        Remove server from state

        Args:
            name: Server name

        Returns:
            True if removed, False if not found
        """
        if not self._state:
            self.load_state()

        if "servers" in self._state and name in self._state["servers"]:
            del self._state["servers"][name]
            self.save_state()
            logger.info(f"Removed server {name} from state")
            return True

        logger.warning(f"Server {name} not found in state")
        return False

    def update_server(self, name: str, updates: Dict[str, Any]) -> bool:
        """
        Update server data

        Args:
            name: Server name
            updates: Dictionary of updates

        Returns:
            True if updated, False if not found
        """
        if not self._state:
            self.load_state()

        if "servers" in self._state and name in self._state["servers"]:
            # Add update timestamp
            updates["updated_at"] = datetime.now().isoformat()

            self._state["servers"][name].update(updates)
            self.save_state()
            logger.info(f"Updated server {name} in state")
            return True

        logger.warning(f"Server {name} not found in state")
        return False

    def add_deployment(self, deployment_data: Dict[str, Any]) -> None:
        """
        Add a deployment record

        Args:
            deployment_data: Deployment information
        """
        if not self._state:
            self.load_state()

        # Ensure deployments key exists
        if "deployments" not in self._state:
            self._state["deployments"] = []

        # Add timestamp
        deployment_data["timestamp"] = datetime.now().isoformat()

        self._state["deployments"].append(deployment_data)
        self.save_state()
        logger.info("Added deployment to state")

    def get_deployments(self, server_name: Optional[str] = None) -> list:
        """
        Get deployment history

        Args:
            server_name: Filter by server name (optional)

        Returns:
            List of deployments
        """
        if not self._state:
            self.load_state()

        deployments = self._state.get("deployments", [])

        if server_name:
            deployments = [d for d in deployments if d.get("server") == server_name]

        return deployments