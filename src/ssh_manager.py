"""SSH Key Management for LivChat Setup"""

import os
import stat
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class SSHKeyManager:
    """Manages SSH keys for server access"""

    def __init__(self, storage_manager: Any = None):
        """
        Initialize SSH Key Manager

        Args:
            storage_manager: Storage manager for vault integration
        """
        self.storage = storage_manager

        # Use storage manager's config_dir if available, otherwise use default
        if storage_manager and hasattr(storage_manager, 'config_dir'):
            self.keys_dir = storage_manager.config_dir / "ssh_keys"
            logger.info(f"Using storage manager's SSH key directory: {self.keys_dir}")
        else:
            self.keys_dir = Path.home() / ".livchat" / "ssh_keys"
            logger.info(f"Using default SSH key directory: {self.keys_dir}")

        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Set directory permissions to 700
        self.keys_dir.chmod(0o700)

    def generate_key_pair(self, name: str, key_type: str = "ed25519",
                         passphrase: Optional[str] = None) -> Dict[str, str]:
        """
        Generate a new SSH key pair

        Args:
            name: Name for the key pair
            key_type: Type of key (ed25519 or rsa)
            passphrase: Passphrase for key (not supported for automation)

        Returns:
            Dictionary with private_key, public_key, and fingerprint
        """
        if passphrase:
            raise NotImplementedError("Passphrase-protected keys are not supported for automation")

        logger.info(f"Generating {key_type} key pair: {name}")

        if key_type == "ed25519":
            private_key_obj = ed25519.Ed25519PrivateKey.generate()

            # Serialize private key
            private_key = private_key_obj.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')

            # Serialize public key
            public_key_obj = private_key_obj.public_key()
            public_key = public_key_obj.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            ).decode('utf-8')

        elif key_type == "rsa":
            private_key_obj = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
                backend=default_backend()
            )

            # Serialize private key
            private_key = private_key_obj.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')

            # Serialize public key
            public_key_obj = private_key_obj.public_key()
            public_key = public_key_obj.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            ).decode('utf-8')

        else:
            raise ValueError(f"Unsupported key type: {key_type}")

        # Add comment to public key
        public_key = f"{public_key.strip()} {name}"

        # Calculate fingerprint
        key_data = public_key.split()[1].encode('utf-8')
        fingerprint = hashlib.sha256(key_data).hexdigest()

        # Save keys
        self._save_key(name, private_key, public_key)

        return {
            "private_key": private_key,
            "public_key": public_key,
            "fingerprint": fingerprint
        }

    def _save_key(self, name: str, private_key: str, public_key: str):
        """
        Save key pair to filesystem and vault

        Args:
            name: Key name
            private_key: Private key content
            public_key: Public key content
        """
        # Save private key
        private_path = self.keys_dir / name
        private_path.write_text(private_key)
        # Set permissions to 600 (owner read/write only)
        private_path.chmod(0o600)

        # Save public key
        public_path = self.keys_dir / f"{name}.pub"
        public_path.write_text(public_key)
        public_path.chmod(0o644)

        # Store in vault if available
        if self.storage and hasattr(self.storage, 'secrets'):
            self.storage.secrets.set_secret(
                f"ssh_key_{name}",
                private_key
            )

        logger.info(f"SSH key pair saved: {name}")

    def has_key(self, name: str) -> bool:
        """
        Check if a key exists

        Args:
            name: Key name

        Returns:
            True if key exists
        """
        private_path = self.keys_dir / name
        return private_path.exists()

    def key_exists(self, name: str) -> bool:
        """
        Check if a key exists (alias for has_key)

        Args:
            name: Key name

        Returns:
            True if key exists
        """
        return self.has_key(name)

    def get_public_key(self, name: str) -> str:
        """
        Get public key content

        Args:
            name: Key name

        Returns:
            Public key content
        """
        public_path = self.keys_dir / f"{name}.pub"
        if not public_path.exists():
            raise FileNotFoundError(f"Public key not found: {name}")

        return public_path.read_text().strip()

    def get_private_key_path(self, name: str) -> Path:
        """
        Get path to private key file

        Args:
            name: Key name

        Returns:
            Path to private key file
        """
        private_path = self.keys_dir / name
        if not private_path.exists():
            raise FileNotFoundError(f"Private key not found: {name}")

        return private_path

    def list_keys(self) -> List[str]:
        """
        List all available SSH keys

        Returns:
            List of key names
        """
        keys = []
        for key_file in self.keys_dir.glob("*"):
            if not key_file.name.endswith(".pub") and key_file.is_file():
                keys.append(key_file.name)

        return sorted(keys)

    def delete_key(self, name: str) -> bool:
        """
        Delete a key pair

        Args:
            name: Key name

        Returns:
            True if deleted successfully
        """
        private_path = self.keys_dir / name
        public_path = self.keys_dir / f"{name}.pub"

        deleted = False

        if private_path.exists():
            private_path.unlink()
            deleted = True
            logger.info(f"Deleted private key: {name}")

        if public_path.exists():
            public_path.unlink()
            logger.info(f"Deleted public key: {name}")

        # Remove from vault if available
        if self.storage and hasattr(self.storage, 'secrets'):
            try:
                # Note: Assuming delete_secret method exists
                # If not, we'll just log and continue
                if hasattr(self.storage.secrets, 'delete_secret'):
                    self.storage.secrets.delete_secret(f"ssh_key_{name}")
            except Exception as e:
                logger.warning(f"Could not remove key from vault: {e}")

        return deleted

    def add_to_hetzner(self, name: str, api_token: str) -> bool:
        """
        Add SSH key to Hetzner Cloud

        Args:
            name: Key name
            api_token: Hetzner API token

        Returns:
            True if added successfully
        """
        try:
            from hcloud import Client
            from hcloud.ssh_keys.domain import SSHKey

            # Get public key
            public_key = self.get_public_key(name)
            logger.debug(f"Got public key for {name}: {public_key[:50]}...")

            # Create Hetzner client
            client = Client(token=api_token)
            logger.debug(f"Created Hetzner client")

            # Check if key already exists
            existing_result = client.ssh_keys.get_list(name=name)
            if existing_result and existing_result.ssh_keys and len(existing_result.ssh_keys) > 0:
                existing_key = existing_result.ssh_keys[0]

                # Check if the existing key matches our current public key
                current_public_key = self.get_public_key(name).strip()
                existing_public_key = existing_key.public_key.strip()

                if current_public_key == existing_public_key:
                    logger.info(f"SSH key already exists in Hetzner with same public key: {name} (ID: {existing_key.id})")
                    return True
                else:
                    logger.warning(f"SSH key exists in Hetzner but with different public key, deleting old key...")
                    client.ssh_keys.delete(existing_key)
                    logger.info(f"Deleted old SSH key: {name} (ID: {existing_key.id})")
                    # Continue to create new key below

            # Create new key
            logger.info(f"Creating new SSH key in Hetzner: {name}")
            response = client.ssh_keys.create(
                name=name,
                public_key=public_key,
                labels={"managed_by": "livchat-setup"}
            )

            # The response is a BoundSSHKey object
            if response and response.id:
                logger.info(f"✅ SSH key successfully added to Hetzner: {name} (ID: {response.id})")

                # Verify it was created
                verification = client.ssh_keys.get_by_name(name)
                if verification:
                    logger.debug(f"Verified SSH key exists: {verification.name} (ID: {verification.id})")
                    return True
                else:
                    logger.error(f"SSH key was created but cannot be found: {name}")
                    return False
            else:
                logger.error(f"Failed to create SSH key - no response from Hetzner")
                return False

        except ImportError as e:
            logger.error(f"Hetzner Cloud library not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to add key to Hetzner: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def get_ssh_config_entry(self, name: str, host: str, user: str = "root",
                           port: int = 22) -> str:
        """
        Generate SSH config entry for a key

        Args:
            name: Key name
            host: Server hostname/IP
            user: SSH user (default: root)
            port: SSH port (default: 22)

        Returns:
            SSH config entry string
        """
        private_key_path = self.get_private_key_path(name)

        config = f"""Host {name}
    HostName {host}
    User {user}
    Port {port}
    IdentityFile {private_key_path}
    IdentitiesOnly yes
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null"""

        return config