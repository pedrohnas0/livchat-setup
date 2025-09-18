"""Unit tests for Server Setup module"""

from pathlib import Path
from unittest.mock import Mock, patch, call
from dataclasses import dataclass

import pytest

from src.server_setup import ServerSetup, SetupResult


class TestServerSetup:
    """Test suite for Server Setup"""

    @pytest.fixture
    def mock_ansible_runner(self):
        """Mock Ansible Runner"""
        runner = Mock()
        # Default successful result
        runner.run_playbook = Mock(return_value=Mock(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr=""
        ))
        return runner

    @pytest.fixture
    def server_setup(self, mock_ansible_runner):
        """Create ServerSetup with mocked dependencies"""
        return ServerSetup(mock_ansible_runner)

    def test_setup_base(self, server_setup, mock_ansible_runner):
        """Test base server setup"""
        server = {
            "name": "test-server",
            "ip": "192.168.1.100",
            "ssh_key": "test-key"
        }

        result = server_setup.setup_base(server)

        assert result.success is True
        assert result.step == "base-setup"
        mock_ansible_runner.run_playbook.assert_called_once()

        # Check playbook path
        call_args = mock_ansible_runner.run_playbook.call_args
        assert "base-setup.yml" in str(call_args.args[0]) if call_args.args else str(call_args.kwargs.get("playbook_path", ""))

        # Check inventory
        inventory = call_args.kwargs["inventory"]
        assert "all" in inventory
        assert "test-server" in inventory["all"]["hosts"]

    def test_install_docker(self, server_setup, mock_ansible_runner):
        """Test Docker installation"""
        server = {
            "name": "docker-test",
            "ip": "192.168.1.101",
            "ssh_key": "test-key"
        }

        result = server_setup.install_docker(server)

        assert result.success is True
        assert result.step == "docker-install"
        mock_ansible_runner.run_playbook.assert_called_once()

        # Check correct playbook was used
        call_args = mock_ansible_runner.run_playbook.call_args
        assert "docker-install.yml" in str(call_args.kwargs.get("playbook_path", ""))

    def test_init_swarm(self, server_setup, mock_ansible_runner):
        """Test Swarm initialization"""
        server = {
            "name": "swarm-test",
            "ip": "192.168.1.102",
            "ssh_key": "test-key"
        }

        result = server_setup.init_swarm(server, network_name="test_network")

        assert result.success is True
        assert result.step == "swarm-init"

        # Check extra vars were passed
        call_args = mock_ansible_runner.run_playbook.call_args
        extra_vars = call_args.kwargs.get("extra_vars", {})
        assert extra_vars.get("swarm_network") == "test_network"

    def test_deploy_traefik(self, server_setup, mock_ansible_runner):
        """Test Traefik deployment"""
        server = {
            "name": "traefik-test",
            "ip": "192.168.1.103",
            "ssh_key": "test-key"
        }

        config = {
            "ssl_email": "test@example.com",
            "network_name": "test_network"
        }

        result = server_setup.deploy_traefik(server, config)

        assert result.success is True
        assert result.step == "traefik-deploy"

        # Check extra vars
        call_args = mock_ansible_runner.run_playbook.call_args
        extra_vars = call_args.kwargs.get("extra_vars", {})
        assert extra_vars.get("ssl_email") == "test@example.com"
        assert extra_vars.get("swarm_network") == "test_network"

    def test_full_setup_success(self, server_setup, mock_ansible_runner):
        """Test complete server setup flow"""
        server = {
            "name": "full-test",
            "ip": "192.168.1.104",
            "ssh_key": "test-key"
        }

        # Mock wait_for_ssh to return True immediately
        with patch.object(server_setup, 'wait_for_ssh', return_value=True):
            result = server_setup.full_setup(server)

            assert result.success is True
            assert result.step == "complete"

            # Should call all 4 playbooks
            assert mock_ansible_runner.run_playbook.call_count == 4

            # Verify order of calls
            calls = mock_ansible_runner.run_playbook.call_args_list
            playbooks = [str(call.kwargs.get("playbook_path", "")) for call in calls]

            assert "base-setup.yml" in playbooks[0]
            assert "docker-install.yml" in playbooks[1]
            assert "swarm-init.yml" in playbooks[2]
            assert "traefik-deploy.yml" in playbooks[3]

    def test_full_setup_with_failure(self, server_setup, mock_ansible_runner):
        """Test full setup stops on failure"""
        # Make docker installation fail
        results = [
            Mock(success=True, exit_code=0),   # base-setup succeeds
            Mock(success=False, exit_code=1),  # docker-install fails
        ]
        mock_ansible_runner.run_playbook.side_effect = results

        server = {
            "name": "fail-test",
            "ip": "192.168.1.105",
            "ssh_key": "test-key"
        }

        # Mock wait_for_ssh to return True immediately
        with patch.object(server_setup, 'wait_for_ssh', return_value=True):
            result = server_setup.full_setup(server)

            assert result.success is False
            assert result.step == "docker-install"
            assert "Failed" in result.message

            # Should only call 2 playbooks (stopped after failure)
            assert mock_ansible_runner.run_playbook.call_count == 2

    def test_setup_with_custom_config(self, server_setup, mock_ansible_runner):
        """Test setup with custom configuration"""
        server = {
            "name": "custom-test",
            "ip": "192.168.1.106",
            "ssh_key": "custom-key"
        }

        config = {
            "ssl_email": "custom@domain.com",
            "network_name": "custom_network",
            "timezone": "Europe/London",
            "hostname": "custom-hostname"
        }

        # Mock wait_for_ssh to return True immediately
        with patch.object(server_setup, 'wait_for_ssh', return_value=True):
            result = server_setup.full_setup(server, config)

            assert result.success is True

            # Check custom config was passed
            last_call = mock_ansible_runner.run_playbook.call_args_list[-1]
            extra_vars = last_call.kwargs.get("extra_vars", {})
            assert extra_vars.get("ssl_email") == "custom@domain.com"

    def test_get_setup_status(self, server_setup):
        """Test getting setup status for a server"""
        server_name = "status-test"

        # Initially no status
        status = server_setup.get_setup_status(server_name)
        assert status["completed_steps"] == []
        assert status["current_step"] is None

        # After base setup
        server_setup.update_status(server_name, "base-setup", True)
        status = server_setup.get_setup_status(server_name)
        assert "base-setup" in status["completed_steps"]

    def test_retry_on_failure(self, server_setup, mock_ansible_runner):
        """Test retry logic on setup failure"""
        # First attempt fails, second succeeds
        mock_ansible_runner.run_playbook.side_effect = [
            Mock(success=False, exit_code=1),
            Mock(success=True, exit_code=0)
        ]

        server = {"name": "retry-test", "ip": "192.168.1.107", "ssh_key": "test"}

        result = server_setup.setup_base(server, retries=2)

        assert result.success is True
        assert mock_ansible_runner.run_playbook.call_count == 2

    def test_validate_server_config(self, server_setup):
        """Test server configuration validation"""
        # Valid config
        valid_server = {
            "name": "valid",
            "ip": "192.168.1.100",
            "ssh_key": "key"
        }
        assert server_setup.validate_server_config(valid_server) is True

        # Missing required fields
        invalid_configs = [
            {"name": "missing-ip", "ssh_key": "key"},
            {"ip": "192.168.1.100", "ssh_key": "key"},
            {"name": "missing-key", "ip": "192.168.1.100"}
        ]

        for config in invalid_configs:
            assert server_setup.validate_server_config(config) is False

    def test_create_inventory_from_server(self, server_setup):
        """Test inventory creation from server config"""
        server = {
            "name": "inv-test",
            "ip": "192.168.1.200",
            "ssh_key": "test-key",
            "user": "ubuntu"
        }

        inventory = server_setup.create_inventory(server)

        assert "all" in inventory
        assert "inv-test" in inventory["all"]["hosts"]

        host_config = inventory["all"]["hosts"]["inv-test"]
        assert host_config["ansible_host"] == "192.168.1.200"
        assert host_config["ansible_user"] == "ubuntu"

    @patch('socket.socket')
    def test_check_port_open_success(self, mock_socket, server_setup):
        """Test checking if port is open - success case"""
        mock_sock_instance = Mock()
        mock_sock_instance.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock_instance

        result = server_setup.check_port_open("192.168.1.100", 22)

        assert result is True
        mock_sock_instance.connect_ex.assert_called_once_with(("192.168.1.100", 22))
        mock_sock_instance.close.assert_called_once()

    @patch('socket.socket')
    def test_check_port_open_closed(self, mock_socket, server_setup):
        """Test checking if port is open - closed port"""
        mock_sock_instance = Mock()
        mock_sock_instance.connect_ex.return_value = 1  # Non-zero = connection failed
        mock_socket.return_value = mock_sock_instance

        result = server_setup.check_port_open("192.168.1.100", 22)

        assert result is False

    @patch('time.sleep')
    def test_wait_for_ssh_success(self, mock_sleep, server_setup):
        """Test waiting for SSH - success"""
        # Use mock.patch for time.time with more values for logging
        with patch('time.time') as mock_time:
            # Provide enough values for time checks and logging
            mock_time.side_effect = [
                0,    # Start time
                0,    # First while check
                0.1,  # Logging timestamp
                5,    # After first failed check
                5,    # Second while check
                5.1,  # Logging timestamp
                10    # After successful check
            ]

            # Mock port check to succeed on second attempt
            with patch.object(server_setup, 'check_port_open') as mock_check:
                mock_check.side_effect = [False, True]

                server = {"name": "test", "ip": "192.168.1.100"}
                result = server_setup.wait_for_ssh(server, timeout=30)

                assert result is True
                assert mock_check.call_count == 2

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_ssh_timeout(self, mock_time, mock_sleep, server_setup):
        """Test waiting for SSH - timeout"""
        # Simulate timeout - provide enough values for all time checks
        times = []
        for i in range(20):  # Provide plenty of values
            times.append(i * 10)  # 0, 10, 20, 30, 40...
        mock_time.side_effect = times

        with patch.object(server_setup, 'check_port_open', return_value=False):
            server = {"name": "test", "ip": "192.168.1.100"}
            result = server_setup.wait_for_ssh(server, timeout=30)

            assert result is False