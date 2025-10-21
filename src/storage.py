"""Unified storage management for LivChat Setup"""

import json
import logging
import os
import secrets
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from ansible.parsing.vault import VaultLib, VaultSecret
from ansible.constants import DEFAULT_VAULT_ID_MATCH

logger = logging.getLogger(__name__)


class StateStore:
    """Manages state persistence with thread-safe operations"""

    def __init__(self, config_dir: Path):
        """
        Initialize StateStore

        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.state_file = config_dir / "state.json"
        self._state = {"servers": {}}
        self._lock = threading.Lock()  # Thread-safe lock for all I/O operations
        self._loaded = False  # Track if we've loaded from disk

    def init(self) -> None:
        """Initialize state file"""
        if not self.state_file.exists():
            logger.info("Creating initial state file")
            self.save()
        else:
            logger.info("State file already exists")
            self.load()

    def load(self) -> dict:
        """
        Load state from file (thread-safe)

        Returns:
            State dictionary
        """
        with self._lock:
            try:
                if self.state_file.exists():
                    logger.debug(f"Loading state from {self.state_file}")
                    with open(self.state_file, 'r') as f:
                        self._state = json.load(f)
                else:
                    logger.warning("State file not found, using empty state")
                    self._state = {"servers": {}}

                self._loaded = True  # Mark as loaded
                return self._state
            except Exception as e:
                logger.error(f"Failed to load state: {e}", exc_info=True)
                # Return current state on error (don't crash)
                return self._state

    def save(self) -> None:
        """Save state to file with backup (thread-safe)"""
        with self._lock:
            try:
                # Create backup if file exists
                if self.state_file.exists():
                    backup_file = self.state_file.with_suffix('.json.backup')
                    shutil.copy2(self.state_file, backup_file)
                    logger.debug(f"Created backup at {backup_file}")

                logger.debug(f"Saving state to {self.state_file}")
                self.config_dir.mkdir(parents=True, exist_ok=True)

                # Write to temp file first, then atomic rename
                temp_file = self.state_file.with_suffix('.json.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(self._state, f, indent=2, default=str)

                # Atomic rename (prevents partial reads)
                temp_file.replace(self.state_file)

            except Exception as e:
                logger.error(f"Failed to save state: {e}", exc_info=True)
                raise

    def add_server(self, name: str, server_data: Dict[str, Any]) -> None:
        """
        Add a server to state

        Args:
            name: Server name
            server_data: Server information
        """
        if not self._loaded and self.state_file.exists():
            self.load()

        # Add timestamp
        server_data["created_at"] = datetime.now().isoformat()

        # Ensure servers key exists
        if "servers" not in self._state:
            self._state["servers"] = {}

        self._state["servers"][name] = server_data
        self.save()
        logger.info(f"Added server {name} to state")

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get server by name

        Args:
            name: Server name

        Returns:
            Server data or None
        """
        if not self._loaded and self.state_file.exists():
            self.load()

        return self._state.get("servers", {}).get(name)

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """
        List all servers

        Returns:
            Dictionary of all servers
        """
        if not self._loaded and self.state_file.exists():
            self.load()

        return self._state.get("servers", {})

    def remove_server(self, name: str) -> bool:
        """
        Remove server from state

        Args:
            name: Server name

        Returns:
            True if removed, False if not found
        """
        if not self._loaded and self.state_file.exists():
            self.load()

        if "servers" in self._state and name in self._state["servers"]:
            del self._state["servers"][name]
            self.save()
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
        if not self._loaded and self.state_file.exists():
            self.load()

        if "servers" in self._state and name in self._state["servers"]:
            # Add update timestamp
            updates["updated_at"] = datetime.now().isoformat()

            self._state["servers"][name].update(updates)
            self.save()
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
        if not self._loaded and self.state_file.exists():
            self.load()

        # Ensure deployments key exists
        if "deployments" not in self._state:
            self._state["deployments"] = []

        # Add timestamp
        deployment_data["timestamp"] = datetime.now().isoformat()

        self._state["deployments"].append(deployment_data)
        self.save()
        logger.info("Added deployment to state")

    def get_deployments(self, server_name: Optional[str] = None) -> list:
        """
        Get deployment history

        Args:
            server_name: Filter by server name (optional)

        Returns:
            List of deployments
        """
        if not self._loaded and self.state_file.exists():
            self.load()

        deployments = self._state.get("deployments", [])

        if server_name:
            deployments = [d for d in deployments if d.get("server") == server_name]

        return deployments

    def save_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Save jobs to state

        Args:
            jobs: List of job dictionaries
        """
        # CRITICAL: Always load fresh state before saving to prevent data loss
        # This ensures we don't overwrite servers/deployments with stale data
        if self.state_file.exists():
            self.load()
        elif not self._loaded:
            # File doesn't exist yet - initialize minimal state
            logger.warning("State file doesn't exist - initializing minimal state for jobs")

        self._state["jobs"] = jobs
        self.save()
        logger.debug(f"Saved {len(jobs)} jobs to state")

    def load_jobs(self) -> List[Dict[str, Any]]:
        """
        Load jobs from state

        Returns:
            List of job dictionaries
        """
        if not self._loaded and self.state_file.exists():
            self.load()

        return self._state.get("jobs", [])

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value from state

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        # Lazy load from disk on first access
        if not self._loaded and self.state_file.exists():
            self.load()

        settings = self._state.get("settings", {})
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """
        Set a setting value in state

        Args:
            key: Setting key
            value: Setting value
        """
        # Lazy load from disk on first access
        if not self._loaded and self.state_file.exists():
            self.load()

        # Ensure settings section exists
        if "settings" not in self._state:
            self._state["settings"] = {}

        self._state["settings"][key] = value
        self.save()
        logger.debug(f"Set setting {key} = {value}")

    def get_by_path(self, path: str) -> Any:
        """
        Get value from state using dot notation path

        Args:
            path: Dot notation path (e.g., "servers.prod.ip", "settings.admin_email")
                  Empty string returns entire state

        Returns:
            Value at the specified path

        Raises:
            KeyError: If path does not exist

        Examples:
            >>> state.get_by_path("servers.prod.ip")
            "1.2.3.4"
            >>> state.get_by_path("servers.prod.dns_config")
            {"zone_name": "example.com", "subdomain": "app"}
        """
        # Lazy load from disk on first access
        if not self._loaded and self.state_file.exists():
            self.load()

        # Empty path returns root
        if not path or path == "":
            return self._state

        # Split path and navigate
        parts = path.split('.')
        current = self._state

        for i, part in enumerate(parts):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Build partial path for error message
                partial_path = '.'.join(parts[:i+1])
                raise KeyError(f"Path not found: {partial_path}")

        return current

    def set_by_path(self, path: str, value: Any) -> None:
        """
        Set value in state using dot notation path

        Creates intermediate dictionaries if they don't exist.

        Args:
            path: Dot notation path (e.g., "servers.prod.ip")
            value: Value to set (can be any type: str, int, dict, list, etc.)

        Examples:
            >>> state.set_by_path("servers.prod.ip", "1.2.3.4")
            >>> state.set_by_path("servers.prod.dns_config", {"zone_name": "example.com"})
            >>> state.set_by_path("servers.staging.ip", "10.0.0.1")  # Creates 'staging' dict
        """
        # Lazy load from disk on first access
        if not self._loaded and self.state_file.exists():
            self.load()

        parts = path.split('.')
        current = self._state

        # Navigate to parent, creating intermediate dicts as needed
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set final value
        current[parts[-1]] = value
        self.save()
        logger.debug(f"Set value at path: {path}")

    def delete_by_path(self, path: str) -> None:
        """
        Delete key from state using dot notation path

        Args:
            path: Dot notation path (e.g., "servers.prod.status")

        Raises:
            KeyError: If path does not exist

        Examples:
            >>> state.delete_by_path("servers.prod.dns_config.subdomain")
            >>> state.delete_by_path("settings.admin_email")
        """
        # Lazy load from disk on first access
        if not self._loaded and self.state_file.exists():
            self.load()

        parts = path.split('.')
        current = self._state

        # Navigate to parent
        for part in parts[:-1]:
            current = current[part]  # Will raise KeyError if not found

        # Delete final key
        del current[parts[-1]]  # Will raise KeyError if not found
        self.save()
        logger.debug(f"Deleted value at path: {path}")

    def list_keys_at_path(self, path: Optional[str] = None) -> List[str]:
        """
        List keys at a specific path in state

        Args:
            path: Dot notation path (optional, None or empty string returns root keys)

        Returns:
            List of keys if path points to a dict, empty list otherwise

        Raises:
            KeyError: If path does not exist

        Examples:
            >>> state.list_keys_at_path()  # Root level
            ["servers", "settings", "deployments"]
            >>> state.list_keys_at_path("servers")
            ["prod", "dev", "staging"]
            >>> state.list_keys_at_path("servers.prod.ip")  # Non-dict value
            []
        """
        # Lazy load from disk on first access
        if not self._loaded and self.state_file.exists():
            self.load()

        # Get value at path
        if path and path != "":
            current = self.get_by_path(path)
        else:
            current = self._state

        # Return keys if dict, empty list otherwise
        if isinstance(current, dict):
            return list(current.keys())
        else:
            return []


class SecretsStore:
    """Manages encrypted secrets using Ansible Vault"""

    def __init__(self, config_dir: Path):
        """
        Initialize SecretsStore

        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.vault_file = config_dir / "credentials.vault"
        self.vault_password_file = config_dir / ".vault_password"
        self._vault = None
        self._secrets = {}

    def init(self) -> None:
        """Initialize vault with password"""
        if not self.vault_password_file.exists():
            logger.info("Creating new vault password")
            self._create_vault_password()
        else:
            logger.info("Vault password file already exists")

        self._init_vault()

        if not self.vault_file.exists():
            logger.info("Creating initial vault file")
            self._save_secrets({})

    def _create_vault_password(self) -> None:
        """Create a new vault password"""
        # Generate a secure random password
        password = secrets.token_urlsafe(32)

        # Save password file with restricted permissions
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.vault_password_file.write_text(password)
        # Set restrictive permissions (owner read/write only)
        os.chmod(self.vault_password_file, 0o600)

        logger.info(f"Vault password created at {self.vault_password_file}")
        logger.warning("⚠️  Keep the .vault_password file safe! It's needed to decrypt secrets.")

    def _init_vault(self) -> None:
        """Initialize Ansible Vault"""
        if not self.vault_password_file.exists():
            raise FileNotFoundError(f"Vault password file not found: {self.vault_password_file}")

        password = self.vault_password_file.read_text().strip()
        vault_secret = VaultSecret(password.encode())
        self._vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, vault_secret)])
        logger.debug("Ansible Vault initialized")

    def _load_secrets(self) -> dict:
        """Load and decrypt secrets from vault file"""
        if not self.vault_file.exists():
            logger.warning("Vault file not found, using empty secrets")
            return {}

        if not self._vault:
            self._init_vault()

        try:
            logger.debug(f"Loading secrets from {self.vault_file}")
            encrypted_data = self.vault_file.read_bytes()
            decrypted_data = self._vault.decrypt(encrypted_data)
            self._secrets = json.loads(decrypted_data)
            return self._secrets
        except Exception as e:
            logger.error(f"Failed to decrypt vault: {e}")
            raise

    def _save_secrets(self, secrets: Optional[dict] = None) -> None:
        """Encrypt and save secrets to vault file"""
        if secrets is not None:
            self._secrets = secrets

        if not self._vault:
            self._init_vault()

        try:
            logger.debug(f"Saving secrets to {self.vault_file}")
            json_data = json.dumps(self._secrets, indent=2)
            encrypted_data = self._vault.encrypt(json_data.encode())

            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.vault_file.write_bytes(encrypted_data)
            # Set restrictive permissions
            os.chmod(self.vault_file, 0o600)
        except Exception as e:
            logger.error(f"Failed to encrypt vault: {e}")
            raise

    def set_secret(self, key: str, value: Any) -> None:
        """
        Set a secret value

        Args:
            key: Secret key
            value: Secret value
        """
        if not self._secrets:
            self._load_secrets()

        self._secrets[key] = value
        self._save_secrets()
        logger.info(f"Secret '{key}' updated")

    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get a secret value

        Args:
            key: Secret key
            default: Default value if key not found

        Returns:
            Secret value
        """
        if not self._secrets:
            self._load_secrets()

        value = self._secrets.get(key, default)
        if value is None:
            logger.warning(f"Secret '{key}' not found")
        return value

    def remove_secret(self, key: str) -> bool:
        """
        Remove a secret

        Args:
            key: Secret key

        Returns:
            True if removed, False if not found
        """
        if not self._secrets:
            self._load_secrets()

        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
            logger.info(f"Secret '{key}' removed")
            return True

        logger.warning(f"Secret '{key}' not found")
        return False

    def list_secret_keys(self) -> list:
        """
        List all secret keys (not values)

        Returns:
            List of secret keys
        """
        if not self._secrets:
            self._load_secrets()

        return list(self._secrets.keys())

    def export_vault_password(self) -> str:
        """
        Export vault password (use with caution!)

        Returns:
            Vault password
        """
        if self.vault_password_file.exists():
            return self.vault_password_file.read_text().strip()
        raise FileNotFoundError("Vault password file not found")

    def rotate_vault_password(self, new_password: Optional[str] = None) -> None:
        """
        Rotate vault password

        Args:
            new_password: New password (generates random if not provided)
        """
        # Load current secrets
        secrets_data = self._load_secrets()

        # Generate new password if not provided
        if not new_password:
            new_password = secrets.token_urlsafe(32)

        # Save new password
        self.vault_password_file.write_text(new_password)
        os.chmod(self.vault_password_file, 0o600)

        # Re-initialize vault with new password
        self._init_vault()

        # Re-encrypt secrets with new password
        self._save_secrets(secrets_data)

        logger.info("Vault password rotated successfully")


class StorageManager:
    """Unified storage management interface"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize StorageManager

        Args:
            config_dir: Custom config directory (default: ~/.livchat)
        """
        self.config_dir = config_dir or Path.home() / ".livchat"
        self.state = StateStore(self.config_dir)
        self.secrets = SecretsStore(self.config_dir)

        logger.info(f"StorageManager initialized with config dir: {self.config_dir}")

    def init(self) -> None:
        """Initialize all storage components"""
        logger.info("Initializing storage components...")

        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize each component
        self.state.init()
        self.secrets.init()

        logger.info("Storage initialization complete")

    def load_all(self) -> Dict[str, Any]:
        """
        Load all storage data

        Returns:
            Dictionary with all storage data
        """
        return {
            "state": self.state.load(),
            "secrets": self.secrets.list_secret_keys()  # Only keys, not values
        }

    def backup(self, backup_dir: Optional[Path] = None) -> Path:
        """
        Create backup of all storage files

        Args:
            backup_dir: Directory for backup (default: ~/.livchat/backups)

        Returns:
            Path to backup directory
        """
        backup_dir = backup_dir or self.config_dir / "backups"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / timestamp

        logger.info(f"Creating backup at {backup_path}")
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copy all files
        for file in self.config_dir.glob("*"):
            if file.is_file() and file.name != ".vault_password":
                shutil.copy2(file, backup_path / file.name)

        logger.info("Backup created successfully")
        return backup_path


# Convenience exports
__all__ = ["StorageManager", "ConfigStore", "StateStore", "SecretsStore"]