"""
TDD Tests for ServerManager

Tests written FIRST before implementation (Red-Green-Refactor cycle).
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


class TestServerManager:
    """Test server management functionality"""

    @pytest.fixture
    def storage_mock(self):
        """Mock storage manager"""
        storage = Mock()
        storage.state = Mock()
        storage.secrets = Mock()
        return storage

    @pytest.fixture
    def ssh_manager_mock(self):
        """Mock SSH key manager"""
        ssh_mgr = Mock()
        ssh_mgr.key_exists = Mock(return_value=False)
        ssh_mgr.generate_key_pair = Mock(return_value={"public_key": "ssh-rsa AAAA...", "private_key": "-----BEGIN..."})
        ssh_mgr.add_to_hetzner = Mock(return_value=True)
        return ssh_mgr

    @pytest.fixture
    def provider_manager_mock(self):
        """Mock provider manager"""
        prov_mgr = Mock()
        # Mock provider instance
        provider = Mock()
        provider.create_server = Mock(return_value={
            "id": "12345",
            "name": "test-server",
            "ip": "1.2.3.4",
            "provider": "hetzner"
        })
        provider.delete_server = Mock(return_value=True)
        prov_mgr.get_provider = Mock(return_value=provider)
        return prov_mgr

    @pytest.fixture
    def server_manager(self, storage_mock, ssh_manager_mock, provider_manager_mock):
        """Create ServerManager instance for testing"""
        # Import here to avoid import errors before implementation
        from src.orchestrator.server_manager import ServerManager
        return ServerManager(storage_mock, ssh_manager_mock, provider_manager_mock)

    # TDD Test 1: Create server generates SSH key if not exists
    def test_create_server_generates_ssh_key_when_missing(self, server_manager, ssh_manager_mock):
        """Should generate SSH key when creating server if key doesn't exist"""
        ssh_manager_mock.key_exists.return_value = False

        server_manager.create("test-server", "cx21", "nbg1")

        ssh_manager_mock.generate_key_pair.assert_called_once_with("test-server_key")

    # TDD Test 2: Create server adds SSH key to Hetzner
    def test_create_server_adds_ssh_key_to_hetzner(self, server_manager, ssh_manager_mock, storage_mock):
        """Should add SSH key to Hetzner before creating server"""
        storage_mock.secrets.get_secret.return_value = "test-token"

        server_manager.create("test-server", "cx21", "nbg1")

        ssh_manager_mock.add_to_hetzner.assert_called_once_with("test-server_key", "test-token")

    # TDD Test 3: Create server calls provider with correct parameters
    def test_create_server_calls_provider_correctly(self, server_manager, provider_manager_mock):
        """Should call provider.create_server with correct parameters"""
        provider = provider_manager_mock.get_provider()

        server_manager.create("test-server", "cx21", "nbg1", image="debian-12")

        provider.create_server.assert_called_once_with(
            "test-server",
            "cx21",
            "nbg1",
            image="debian-12",
            ssh_keys=["test-server_key"]
        )

    # TDD Test 4: Create server saves to state
    def test_create_server_saves_to_state(self, server_manager, storage_mock):
        """Should save created server to state"""
        server_manager.create("test-server", "cx21", "nbg1")

        # Should call add_server on state
        storage_mock.state.add_server.assert_called_once()
        call_args = storage_mock.state.add_server.call_args
        assert call_args[0][0] == "test-server"  # server name
        assert "ssh_key" in call_args[0][1]  # server data has ssh_key

    # TDD Test 5: Create server returns server info
    def test_create_server_returns_server_info(self, server_manager):
        """Should return server information dict"""
        result = server_manager.create("test-server", "cx21", "nbg1")

        assert isinstance(result, dict)
        assert result["id"] == "12345"
        assert result["name"] == "test-server"
        assert result["ip"] == "1.2.3.4"
        assert result["ssh_key"] == "test-server_key"

    # TDD Test 6: Create server raises error if SSH key add fails
    def test_create_server_raises_error_when_ssh_key_add_fails(self, server_manager, ssh_manager_mock):
        """Should raise RuntimeError if SSH key cannot be added to Hetzner"""
        ssh_manager_mock.add_to_hetzner.return_value = False

        with pytest.raises(RuntimeError, match="Cannot add SSH key to Hetzner"):
            server_manager.create("test-server", "cx21", "nbg1")

    # TDD Test 7: List servers returns all servers from state
    def test_list_servers_returns_all_from_state(self, server_manager, storage_mock):
        """Should return all servers from state"""
        expected_servers = {
            "server1": {"id": "1", "name": "server1"},
            "server2": {"id": "2", "name": "server2"}
        }
        storage_mock.state.list_servers.return_value = expected_servers

        result = server_manager.list()

        assert result == expected_servers
        storage_mock.state.list_servers.assert_called_once()

    # TDD Test 8: Get server returns specific server from state
    def test_get_server_returns_specific_server(self, server_manager, storage_mock):
        """Should return specific server by name"""
        expected_server = {"id": "123", "name": "test-server", "ip": "1.2.3.4"}
        storage_mock.state.get_server.return_value = expected_server

        result = server_manager.get("test-server")

        assert result == expected_server
        storage_mock.state.get_server.assert_called_once_with("test-server")

    # TDD Test 9: Get server returns None if not found
    def test_get_server_returns_none_when_not_found(self, server_manager, storage_mock):
        """Should return None when server not found"""
        storage_mock.state.get_server.return_value = None

        result = server_manager.get("nonexistent")

        assert result is None

    # TDD Test 10: Delete server returns False if not found
    def test_delete_server_returns_false_when_not_found(self, server_manager, storage_mock):
        """Should return False when server not in state"""
        storage_mock.state.get_server.return_value = None

        result = server_manager.delete("nonexistent")

        assert result is False

    # TDD Test 11: Delete server calls provider delete
    def test_delete_server_calls_provider_delete(self, server_manager, storage_mock, provider_manager_mock):
        """Should call provider.delete_server"""
        storage_mock.state.get_server.return_value = {
            "id": "12345",
            "name": "test-server",
            "provider": "hetzner"
        }
        provider = provider_manager_mock.get_provider()

        server_manager.delete("test-server")

        provider.delete_server.assert_called_once_with("12345")

    # TDD Test 12: Delete server removes from state
    def test_delete_server_removes_from_state(self, server_manager, storage_mock):
        """Should remove server from state after deletion"""
        storage_mock.state.get_server.return_value = {
            "id": "12345",
            "name": "test-server"
        }

        server_manager.delete("test-server")

        storage_mock.state.remove_server.assert_called_once_with("test-server")

    # TDD Test 13: Delete server returns True on success
    def test_delete_server_returns_true_on_success(self, server_manager, storage_mock):
        """Should return True when deletion succeeds"""
        storage_mock.state.get_server.return_value = {
            "id": "12345",
            "name": "test-server"
        }

        result = server_manager.delete("test-server")

        assert result is True

    # TDD Test 14: Delete handles provider deletion error gracefully
    def test_delete_handles_provider_error_gracefully(self, server_manager, storage_mock, provider_manager_mock):
        """Should continue with state removal even if provider deletion fails"""
        storage_mock.state.get_server.return_value = {
            "id": "12345",
            "name": "test-server"
        }
        provider = provider_manager_mock.get_provider()
        provider.delete_server.side_effect = Exception("Provider error")

        # Should still remove from state and return True
        result = server_manager.delete("test-server")

        assert result is True
        storage_mock.state.remove_server.assert_called_once()
