"""Shared fixtures for tests"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary directory for test configuration"""
    config_dir = tmp_path / ".livchat_test"
    config_dir.mkdir(exist_ok=True)
    return config_dir


@pytest.fixture
def sample_server_data():
    """Sample server data for testing"""
    return {
        "id": "12345",
        "name": "test-server",
        "ip": "192.168.1.1",
        "provider": "hetzner",
        "type": "cx21",
        "region": "nbg1",
        "status": "running"
    }


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "version": 1,
        "provider": "hetzner",
        "region": "nbg1",
        "server_type": "cx21"
    }


@pytest.fixture
def sample_deployment_data():
    """Sample deployment data for testing"""
    return {
        "server": "test-server",
        "apps": ["postgres", "redis", "n8n"],
        "status": "completed"
    }


@pytest.fixture
def mock_hcloud_client():
    """Mock Hetzner Cloud client"""
    with patch('src.providers.hetzner.Client') as mock_client:
        # Setup mock responses
        mock_instance = Mock()
        mock_client.return_value = mock_instance

        # Mock server creation response
        mock_server = Mock()
        mock_server.id = 12345
        mock_server.name = "test-server"
        mock_server.status = "running"
        mock_server.public_net = Mock()
        mock_server.public_net.ipv4 = Mock(ip="1.2.3.4")
        mock_server.public_net.ipv6 = Mock(ip="2001:db8::1")
        mock_server.datacenter = Mock(name="nbg1-dc3")

        mock_response = Mock()
        mock_response.server = mock_server
        mock_response.action = Mock()

        mock_instance.servers.create.return_value = mock_response
        mock_instance.servers.get_list.return_value = [mock_server]
        mock_instance.servers.get.return_value = mock_server
        mock_instance.servers.delete.return_value = True

        yield mock_instance


@pytest.fixture
def mock_ansible_vault():
    """Mock Ansible Vault for testing secrets"""
    with patch('src.storage.VaultLib') as mock_vault:
        mock_vault_instance = Mock()
        mock_vault.return_value = mock_vault_instance

        # Mock encrypt/decrypt
        mock_vault_instance.encrypt.return_value = b"$ANSIBLE_VAULT;1.1;AES256\nencrypted_data"
        mock_vault_instance.decrypt.return_value = b'{"test_key": "test_value"}'

        yield mock_vault_instance


@pytest.fixture
def storage_with_data(temp_config_dir, sample_config, sample_server_data):
    """Create StorageManager with pre-populated data"""
    from src.storage import StorageManager

    storage = StorageManager(temp_config_dir)
    storage.init()

    # Add sample data
    storage.config.save(sample_config)
    storage.state.add_server("test-server", sample_server_data)
    storage.secrets.set_secret("test_token", "secret123")

    return storage


@pytest.fixture
def orchestrator_with_provider(temp_config_dir, mock_hcloud_client):
    """Create Orchestrator with mocked provider"""
    from src.orchestrator import Orchestrator

    orchestrator = Orchestrator(temp_config_dir)
    orchestrator.init()
    orchestrator.configure_provider("hetzner", "test_token")

    return orchestrator


@pytest.fixture
def dependency_apps():
    """Sample apps with dependencies for testing"""
    return {
        "simple": ["nginx"],  # No dependencies
        "single_dep": ["wordpress"],  # Needs mysql
        "multiple_deps": ["n8n", "chatwoot"],  # Both need postgres and redis
        "mixed": ["n8n", "wordpress", "nginx"]  # Mix of all
    }


@pytest.fixture(autouse=True)
def cleanup_env():
    """Clean up environment after each test"""
    yield
    # Remove any test files created
    import shutil
    test_dirs = [
        Path.home() / ".livchat_test",
        Path("/tmp") / ".livchat_test"
    ]
    for test_dir in test_dirs:
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)