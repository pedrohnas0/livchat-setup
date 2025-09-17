"""Secrets management using Ansible Vault"""

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Optional

from ansible.parsing.vault import VaultLib, VaultSecret
from ansible.constants import DEFAULT_VAULT_ID_MATCH

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manages encrypted secrets using Ansible Vault"""

    def __init__(self, config_dir: Path):
        """
        Initialize SecretsManager

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