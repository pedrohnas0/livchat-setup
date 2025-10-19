"""Tests for storage module"""

import pytest
import json
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from src.storage import ConfigStore, StateStore, SecretsStore, StorageManager


class TestConfigStore:
    """Test configuration storage"""

    def test_init_creates_default_config(self, temp_config_dir):
        """Test that init creates default configuration"""
        config = ConfigStore(temp_config_dir)
        config.init()

        assert config.config_file.exists()
        with open(config.config_file) as f:
            data = yaml.safe_load(f)
            assert data["version"] == 1
            assert data["provider"] == "hetzner"

    def test_load_existing_config(self, temp_config_dir, sample_config):
        """Test loading existing configuration"""
        # Create config file
        config_file = temp_config_dir / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)

        config = ConfigStore(temp_config_dir)
        data = config.load()

        assert data == sample_config

    def test_save_config(self, temp_config_dir):
        """Test saving configuration"""
        config = ConfigStore(temp_config_dir)
        test_data = {"test": "value", "nested": {"key": "value"}}

        config.save(test_data)

        with open(config.config_file) as f:
            saved = yaml.safe_load(f)
            assert saved == test_data

    def test_get_simple_key(self, temp_config_dir, sample_config):
        """Test getting simple configuration value"""
        config = ConfigStore(temp_config_dir)
        config.save(sample_config)

        value = config.get("provider")
        assert value == "hetzner"

    def test_get_nested_key_with_dot_notation(self, temp_config_dir):
        """Test getting nested value with dot notation"""
        config = ConfigStore(temp_config_dir)
        config.save({"level1": {"level2": {"level3": "value"}}})

        value = config.get("level1.level2.level3")
        assert value == "value"

    def test_get_nonexistent_key_returns_default(self, temp_config_dir):
        """Test that nonexistent key returns default value"""
        config = ConfigStore(temp_config_dir)
        config.init()

        value = config.get("nonexistent", "default")
        assert value == "default"

    def test_set_and_persist(self, temp_config_dir):
        """Test setting value and persistence"""
        config = ConfigStore(temp_config_dir)
        config.init()

        config.set("new_key", "new_value")

        # Reload and check persistence
        config2 = ConfigStore(temp_config_dir)
        value = config2.get("new_key")
        assert value == "new_value"

    def test_set_creates_nested_structure(self, temp_config_dir):
        """Test that set creates nested structure with dot notation"""
        config = ConfigStore(temp_config_dir)
        config.init()

        config.set("deep.nested.key", "value")
        value = config.get("deep.nested.key")

        assert value == "value"

    def test_update_multiple_values(self, temp_config_dir):
        """Test updating multiple configuration values"""
        config = ConfigStore(temp_config_dir)
        config.init()

        updates = {"key1": "value1", "key2": "value2"}
        config.update(updates)

        assert config.get("key1") == "value1"
        assert config.get("key2") == "value2"


class TestStateStore:
    """Test state storage"""

    def test_init_creates_state_file(self, temp_config_dir):
        """Test that init creates state file"""
        state = StateStore(temp_config_dir)
        state.init()

        assert state.state_file.exists()
        with open(state.state_file) as f:
            data = json.load(f)
            assert "servers" in data

    def test_add_server(self, temp_config_dir, sample_server_data):
        """Test adding a server to state"""
        state = StateStore(temp_config_dir)
        state.init()

        state.add_server("test-server", sample_server_data)

        servers = state.list_servers()
        assert "test-server" in servers
        assert servers["test-server"]["ip"] == "192.168.1.1"

    def test_get_existing_server(self, temp_config_dir, sample_server_data):
        """Test getting existing server"""
        state = StateStore(temp_config_dir)
        state.init()
        state.add_server("test-server", sample_server_data)

        server = state.get_server("test-server")
        assert server["ip"] == "192.168.1.1"

    def test_get_nonexistent_server_returns_none(self, temp_config_dir):
        """Test getting nonexistent server returns None"""
        state = StateStore(temp_config_dir)
        state.init()

        server = state.get_server("nonexistent")
        assert server is None

    def test_list_all_servers(self, temp_config_dir):
        """Test listing all servers"""
        state = StateStore(temp_config_dir)
        state.init()

        # Add multiple servers
        state.add_server("server1", {"ip": "1.1.1.1"})
        state.add_server("server2", {"ip": "2.2.2.2"})

        servers = state.list_servers()
        assert len(servers) == 2
        assert "server1" in servers
        assert "server2" in servers

    def test_remove_existing_server(self, temp_config_dir, sample_server_data):
        """Test removing existing server"""
        state = StateStore(temp_config_dir)
        state.init()
        state.add_server("test-server", sample_server_data)

        result = state.remove_server("test-server")
        assert result is True
        assert state.get_server("test-server") is None

    def test_remove_nonexistent_server_returns_false(self, temp_config_dir):
        """Test removing nonexistent server returns False"""
        state = StateStore(temp_config_dir)
        state.init()

        result = state.remove_server("nonexistent")
        assert result is False

    def test_update_server_data(self, temp_config_dir, sample_server_data):
        """Test updating server data"""
        state = StateStore(temp_config_dir)
        state.init()
        state.add_server("test-server", sample_server_data)

        updates = {"status": "stopped", "ip": "3.3.3.3"}
        result = state.update_server("test-server", updates)

        assert result is True
        server = state.get_server("test-server")
        assert server["status"] == "stopped"
        assert server["ip"] == "3.3.3.3"

    def test_update_nonexistent_server_returns_false(self, temp_config_dir):
        """Test updating nonexistent server returns False"""
        state = StateStore(temp_config_dir)
        state.init()

        result = state.update_server("nonexistent", {"status": "stopped"})
        assert result is False

    def test_add_deployment_record(self, temp_config_dir, sample_deployment_data):
        """Test adding deployment record"""
        state = StateStore(temp_config_dir)
        state.init()

        state.add_deployment(sample_deployment_data)
        deployments = state.get_deployments()

        assert len(deployments) == 1
        assert deployments[0]["server"] == "test-server"

    def test_get_deployments_filtered_by_server(self, temp_config_dir):
        """Test getting deployments filtered by server"""
        state = StateStore(temp_config_dir)
        state.init()

        state.add_deployment({"server": "server1", "apps": ["app1"]})
        state.add_deployment({"server": "server2", "apps": ["app2"]})
        state.add_deployment({"server": "server1", "apps": ["app3"]})

        server1_deployments = state.get_deployments("server1")
        assert len(server1_deployments) == 2

    def test_backup_before_save(self, temp_config_dir, sample_server_data):
        """Test that backup is created before save"""
        state = StateStore(temp_config_dir)
        state.init()
        state.add_server("server1", sample_server_data)

        # Modify state again (should create backup)
        state.add_server("server2", sample_server_data)

        backup_file = state.state_file.with_suffix('.json.backup')
        assert backup_file.exists()


class TestSecretsStore:
    """Test secrets storage"""

    def test_init_creates_vault_password(self, temp_config_dir):
        """Test that init creates vault password"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        assert secrets.vault_password_file.exists()
        password = secrets.vault_password_file.read_text()
        assert len(password) > 20  # Should be secure password

    def test_set_and_get_secret(self, temp_config_dir):
        """Test setting and getting a secret"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        secrets.set_secret("api_key", "secret123")
        value = secrets.get_secret("api_key")

        assert value == "secret123"

    def test_get_nonexistent_secret_returns_default(self, temp_config_dir):
        """Test getting nonexistent secret returns default"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        value = secrets.get_secret("nonexistent", "default")
        assert value == "default"

    def test_remove_existing_secret(self, temp_config_dir):
        """Test removing existing secret"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()
        secrets.set_secret("test_key", "test_value")

        result = secrets.remove_secret("test_key")
        assert result is True
        assert secrets.get_secret("test_key") is None

    def test_remove_nonexistent_secret_returns_false(self, temp_config_dir):
        """Test removing nonexistent secret returns False"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        result = secrets.remove_secret("nonexistent")
        assert result is False

    def test_list_secret_keys(self, temp_config_dir):
        """Test listing secret keys"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        secrets.set_secret("key1", "value1")
        secrets.set_secret("key2", "value2")

        keys = secrets.list_secret_keys()
        assert "key1" in keys
        assert "key2" in keys
        assert len(keys) == 2

    def test_secrets_are_encrypted_on_disk(self, temp_config_dir):
        """Test that secrets are encrypted on disk"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        secrets.set_secret("sensitive_key", "sensitive_value")

        # Read raw vault file
        vault_content = secrets.vault_file.read_text()
        assert "sensitive_value" not in vault_content
        assert "$ANSIBLE_VAULT" in vault_content

    def test_export_vault_password(self, temp_config_dir):
        """Test exporting vault password"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        original_password = secrets.vault_password_file.read_text().strip()
        exported_password = secrets.export_vault_password()

        assert exported_password == original_password

    def test_rotate_vault_password(self, temp_config_dir):
        """Test rotating vault password"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        # Set a secret
        secrets.set_secret("test_key", "test_value")
        original_password = secrets.export_vault_password()

        # Rotate password
        secrets.rotate_vault_password()
        new_password = secrets.export_vault_password()

        # Check password changed
        assert new_password != original_password

        # Check secret still accessible
        value = secrets.get_secret("test_key")
        assert value == "test_value"

    def test_vault_password_permissions_600(self, temp_config_dir):
        """Test that vault password has restricted permissions"""
        secrets = SecretsStore(temp_config_dir)
        secrets.init()

        # Check file permissions (owner read/write only)
        import stat
        file_stat = secrets.vault_password_file.stat()
        file_mode = stat.filemode(file_stat.st_mode)
        assert file_mode == '-rw-------'


class TestStorageManager:
    """Test unified storage manager"""

    def test_init_all_components(self, temp_config_dir):
        """Test that init initializes all components"""
        storage = StorageManager(temp_config_dir)
        storage.init()

        assert storage.config.config_file.exists()
        assert storage.state.state_file.exists()
        assert storage.secrets.vault_file.exists()

    def test_load_all_data(self, storage_with_data):
        """Test loading all data from storage"""
        data = storage_with_data.load_all()

        assert "config" in data
        assert "state" in data
        assert "secrets" in data
        assert data["config"]["provider"] == "hetzner"
        assert "test-server" in data["state"]["servers"]

    def test_backup_creates_timestamped_copy(self, storage_with_data):
        """Test that backup creates timestamped copy"""
        backup_path = storage_with_data.backup()

        assert backup_path.exists()
        assert backup_path.is_dir()

        # Check backup contains expected files
        backed_up_files = list(backup_path.glob("*"))
        file_names = [f.name for f in backed_up_files]
        assert "config.yaml" in file_names
        assert "state.json" in file_names
        assert "credentials.vault" in file_names

    def test_backup_excludes_vault_password(self, storage_with_data):
        """Test that backup excludes vault password"""
        backup_path = storage_with_data.backup()

        # Check that vault password is NOT in backup
        backed_up_files = list(backup_path.glob("*"))
        file_names = [f.name for f in backed_up_files]
        assert ".vault_password" not in file_names

    def test_handle_missing_directory(self):
        """Test handling missing configuration directory"""
        non_existent = Path("/tmp/nonexistent_test_dir_12345")
        storage = StorageManager(non_existent)

        # Should create directory on init
        storage.init()
        assert non_existent.exists()

        # Cleanup
        import shutil
        shutil.rmtree(non_existent)