"""Unit tests for SSH Key Manager"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.ssh_manager import SSHKeyManager


class TestSSHKeyManager:
    """Test suite for SSH Key Manager"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def mock_storage(self, temp_dir):
        """Mock storage manager"""
        storage = Mock()
        storage.secrets = Mock()
        storage.secrets.set_secret = Mock(return_value=True)
        storage.secrets.get_secret = Mock(return_value="mock_private_key")
        # Properly mock config_dir as a Path object
        storage.config_dir = temp_dir / ".livchat"
        return storage

    @pytest.fixture
    def ssh_manager(self, mock_storage, temp_dir):
        """Create SSH manager with mocked dependencies"""
        # No need to patch Path.home since we're using storage.config_dir
        manager = SSHKeyManager(mock_storage)
        return manager

    def test_generate_ed25519_key_pair(self, ssh_manager):
        """Test Ed25519 key pair generation"""
        # Generate key pair
        result = ssh_manager.generate_key_pair("test-server")

        # Verify result structure
        assert "private_key" in result
        assert "public_key" in result
        assert "fingerprint" in result

        # Verify key format
        assert result["private_key"].startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
        assert result["public_key"].startswith("ssh-ed25519")

        # Verify key was saved
        assert ssh_manager.has_key("test-server")

    def test_generate_rsa_key_pair_fallback(self, ssh_manager):
        """Test RSA key pair generation as fallback"""
        # Generate RSA key pair
        result = ssh_manager.generate_key_pair("test-server", key_type="rsa")

        # Verify result structure
        assert "private_key" in result
        assert "public_key" in result

        # Verify key format
        assert result["private_key"].startswith("-----BEGIN RSA PRIVATE KEY-----") or \
               result["private_key"].startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
        assert result["public_key"].startswith("ssh-rsa")

    def test_store_key_in_vault(self, ssh_manager, mock_storage):
        """Test secure key storage in vault"""
        # Generate and store key
        result = ssh_manager.generate_key_pair("vault-test")

        # Verify vault was called
        mock_storage.secrets.set_secret.assert_called()

        # Verify the key name format
        call_args = mock_storage.secrets.set_secret.call_args
        assert "ssh_key_vault-test" in call_args[0][0]

    def test_key_permissions(self, ssh_manager, temp_dir):
        """Test that private key files have correct permissions (600)"""
        # Generate key
        ssh_manager.generate_key_pair("perm-test")

        # Check private key permissions
        private_key_path = ssh_manager.keys_dir / "perm-test"
        assert private_key_path.exists()

        # Get file permissions (last 3 digits)
        permissions = oct(private_key_path.stat().st_mode)[-3:]
        assert permissions == "600", f"Expected 600, got {permissions}"

    def test_get_public_key_format(self, ssh_manager):
        """Test retrieving public key in correct format"""
        # Generate key first
        ssh_manager.generate_key_pair("format-test")

        # Get public key
        public_key = ssh_manager.get_public_key("format-test")

        # Verify format
        assert public_key.startswith("ssh-ed25519") or public_key.startswith("ssh-rsa")
        assert "format-test" in public_key  # Should contain key comment

    def test_list_keys(self, ssh_manager):
        """Test listing available keys"""
        # Generate multiple keys
        ssh_manager.generate_key_pair("key1")
        ssh_manager.generate_key_pair("key2")
        ssh_manager.generate_key_pair("key3")

        # List keys
        keys = ssh_manager.list_keys()

        # Verify all keys are listed
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
        assert len(keys) >= 3

    def test_delete_key(self, ssh_manager):
        """Test key deletion"""
        # Generate key
        ssh_manager.generate_key_pair("delete-test")
        assert ssh_manager.has_key("delete-test")

        # Delete key
        result = ssh_manager.delete_key("delete-test")
        assert result is True

        # Verify key is gone
        assert not ssh_manager.has_key("delete-test")
        assert "delete-test" not in ssh_manager.list_keys()

    def test_delete_nonexistent_key(self, ssh_manager):
        """Test deleting a key that doesn't exist"""
        result = ssh_manager.delete_key("nonexistent")
        assert result is False

    @patch('hcloud.Client')
    def test_add_key_to_hetzner(self, mock_hcloud_client, ssh_manager):
        """Test adding SSH key to Hetzner"""
        # Mock Hetzner client
        mock_client = Mock()
        mock_hcloud_client.return_value = mock_client
        mock_client.ssh_keys.get_list = Mock(return_value=[])
        mock_client.ssh_keys.create = Mock(return_value=Mock(ssh_key=Mock(id=123)))

        # Generate key
        ssh_manager.generate_key_pair("hetzner-test")

        # Add to Hetzner
        result = ssh_manager.add_to_hetzner(
            "hetzner-test",
            api_token="fake_token"
        )

        # Verify
        assert result is True
        mock_client.ssh_keys.create.assert_called_once()

    def test_key_with_passphrase_not_supported(self, ssh_manager):
        """Test that passphrases are not supported (for automation)"""
        with pytest.raises(NotImplementedError):
            ssh_manager.generate_key_pair("test", passphrase="secret")

    def test_get_private_key_path(self, ssh_manager):
        """Test getting private key file path"""
        ssh_manager.generate_key_pair("path-test")

        path = ssh_manager.get_private_key_path("path-test")
        assert path.exists()
        assert path.name == "path-test"

    def test_ssh_config_entry_generation(self, ssh_manager):
        """Test generating SSH config entry for a key"""
        ssh_manager.generate_key_pair("config-test")

        config = ssh_manager.get_ssh_config_entry(
            "config-test",
            host="192.168.1.1",
            user="root"
        )

        assert "Host config-test" in config
        assert "HostName 192.168.1.1" in config
        assert "User root" in config
        assert "IdentityFile" in config
        assert str(ssh_manager.keys_dir / "config-test") in config