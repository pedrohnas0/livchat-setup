"""Unit tests for Ansible Runner"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.ansible_executor import AnsibleRunner


class TestAnsibleRunner:
    """Test suite for Ansible Runner"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def mock_ssh_manager(self):
        """Mock SSH manager"""
        ssh_manager = Mock()
        ssh_manager.get_private_key_path = Mock(return_value=Path("/tmp/test_key"))
        ssh_manager.has_key = Mock(return_value=True)
        return ssh_manager

    @pytest.fixture
    def ansible_runner(self, mock_ssh_manager, temp_dir):
        """Create Ansible runner with mocked dependencies"""
        with patch('src.ansible_executor.Path.home', return_value=temp_dir):
            runner = AnsibleRunner(mock_ssh_manager)
            return runner

    def test_create_inventory_single_host(self, ansible_runner):
        """Test creating inventory for single host"""
        servers = [
            {
                "name": "test-server",
                "ip": "192.168.1.100",
                "ssh_key": "test_key"
            }
        ]

        inventory = ansible_runner.create_inventory(servers)

        # Verify inventory structure
        assert "all" in inventory
        assert "hosts" in inventory["all"]
        assert "test-server" in inventory["all"]["hosts"]

        # Verify host configuration
        host_config = inventory["all"]["hosts"]["test-server"]
        assert host_config["ansible_host"] == "192.168.1.100"
        assert host_config["ansible_user"] == "root"
        assert "ansible_ssh_private_key_file" in host_config

    def test_create_inventory_multiple_hosts(self, ansible_runner):
        """Test creating inventory for multiple hosts"""
        servers = [
            {"name": "server1", "ip": "192.168.1.1", "ssh_key": "key1"},
            {"name": "server2", "ip": "192.168.1.2", "ssh_key": "key2"},
            {"name": "server3", "ip": "192.168.1.3", "ssh_key": "key3"},
        ]

        inventory = ansible_runner.create_inventory(servers)

        # Verify all hosts are present
        hosts = inventory["all"]["hosts"]
        assert len(hosts) == 3
        assert "server1" in hosts
        assert "server2" in hosts
        assert "server3" in hosts

    @patch('src.ansible_executor.ansible_runner.run')
    def test_run_playbook(self, mock_ansible_run, ansible_runner):
        """Test running an Ansible playbook"""
        # Setup mock
        mock_result = Mock()
        mock_result.rc = 0
        mock_result.status = "successful"
        mock_result.stdout = Mock()
        mock_result.stdout.read = Mock(return_value="Success output")
        mock_result.stderr = ""
        mock_result.stats = {}
        mock_ansible_run.return_value = mock_result

        # Run playbook
        result = ansible_runner.run_playbook(
            playbook_path="test.yml",
            inventory={"all": {"hosts": {"test": {}}}},
            extra_vars={"test_var": "value"}
        )

        # Verify
        assert result.success is True
        assert result.exit_code == 0
        mock_ansible_run.assert_called_once()

    @patch('src.ansible_executor.ansible_runner.run')
    def test_run_playbook_with_failure(self, mock_ansible_run, ansible_runner):
        """Test handling playbook failure"""
        # Setup mock for failure
        mock_result = Mock()
        mock_result.rc = 1
        mock_result.status = "failed"
        mock_result.stdout = Mock()
        mock_result.stdout.read = Mock(return_value="")
        mock_result.stderr = "Error occurred"
        mock_result.stats = {"failures": {"host1": 1}}
        mock_ansible_run.return_value = mock_result

        # Run playbook
        result = ansible_runner.run_playbook(
            playbook_path="test.yml",
            inventory={"all": {"hosts": {"test": {}}}}
        )

        # Verify failure handling
        assert result.success is False
        assert result.exit_code == 1

    @patch('src.ansible_executor.ansible_runner.run')
    def test_run_adhoc_command(self, mock_ansible_run, ansible_runner):
        """Test running ad-hoc Ansible command"""
        # Setup mock
        mock_result = Mock()
        mock_result.rc = 0
        mock_result.status = "successful"
        mock_result.stdout = Mock()
        mock_result.stdout.read = Mock(return_value="pong")
        mock_result.stderr = ""
        mock_result.stats = {}
        mock_ansible_run.return_value = mock_result

        # Run ad-hoc command
        result = ansible_runner.run_adhoc(
            host="192.168.1.100",
            module="ping",
            args=""
        )

        # Verify
        assert result.success is True
        mock_ansible_run.assert_called_once()

        # Check that module was specified correctly
        call_kwargs = mock_ansible_run.call_args.kwargs
        assert call_kwargs["module"] == "ping"

    def test_save_inventory_to_file(self, ansible_runner):
        """Test saving inventory to file"""
        inventory = {
            "all": {
                "hosts": {
                    "test-host": {
                        "ansible_host": "192.168.1.1",
                        "ansible_user": "root"
                    }
                }
            }
        }

        # Save inventory
        inventory_path = ansible_runner.save_inventory(inventory, "test_inv")

        # Verify file exists
        assert inventory_path.exists()

        # Verify content
        content = json.loads(inventory_path.read_text())
        assert content == inventory

    def test_get_playbook_path(self, ansible_runner):
        """Test getting playbook path"""
        # Test with absolute path
        abs_path = Path("/absolute/path/playbook.yml")
        result = ansible_runner.get_playbook_path(str(abs_path))
        assert result == abs_path

        # Test with relative path (should look in ansible/playbooks)
        rel_path = "base-setup.yml"
        result = ansible_runner.get_playbook_path(rel_path)
        assert "ansible/playbooks" in str(result)
        assert result.name == "base-setup.yml"

    def test_validate_playbook_exists(self, ansible_runner, temp_dir):
        """Test playbook validation"""
        # Create a fake playbook
        playbook_dir = temp_dir / "ansible" / "playbooks"
        playbook_dir.mkdir(parents=True)
        playbook_file = playbook_dir / "test.yml"
        playbook_file.write_text("---\n- hosts: all\n  tasks: []")

        # Test valid playbook
        result = ansible_runner.validate_playbook(str(playbook_file))
        assert result is True

        # Test non-existent playbook
        result = ansible_runner.validate_playbook("nonexistent.yml")
        assert result is False

    @patch('ansible_runner.run')
    def test_run_with_ssh_config(self, mock_ansible_run, ansible_runner):
        """Test that SSH configuration is properly set"""
        mock_result = Mock()
        mock_result.rc = 0
        mock_ansible_run.return_value = mock_result

        # Run playbook
        ansible_runner.run_playbook(
            playbook_path="test.yml",
            inventory={"all": {"hosts": {"test": {"ansible_host": "192.168.1.1"}}}}
        )

        # Verify SSH args were set
        call_kwargs = mock_ansible_run.call_args.kwargs
        assert "envvars" in call_kwargs
        assert "ANSIBLE_HOST_KEY_CHECKING" in call_kwargs["envvars"]
        assert call_kwargs["envvars"]["ANSIBLE_HOST_KEY_CHECKING"] == "False"

    def test_parse_ansible_output(self, ansible_runner):
        """Test parsing Ansible output for results"""
        # Mock successful output
        output = {
            "stats": {
                "test-host": {
                    "ok": 5,
                    "changed": 2,
                    "failures": 0,
                    "skipped": 1
                }
            }
        }

        stats = ansible_runner.parse_output(output)

        assert stats["test-host"]["ok"] == 5
        assert stats["test-host"]["changed"] == 2
        assert stats["test-host"]["failures"] == 0

    def test_get_ansible_config(self, ansible_runner):
        """Test getting Ansible configuration"""
        config = ansible_runner.get_ansible_config()

        # Verify essential settings
        assert config["host_key_checking"] is False
        assert config["timeout"] == 30
        assert config["gathering"] == "smart"
        assert "pipelining" in config

    @pytest.mark.integration
    @patch('ansible_runner.run')
    def test_integration_ping_module(self, mock_ansible_run, ansible_runner):
        """Integration test with ping module"""
        mock_result = Mock()
        mock_result.rc = 0
        mock_result.status = "successful"
        mock_ansible_run.return_value = mock_result

        result = ansible_runner.run_adhoc(
            host="localhost",
            module="ping",
            args=""
        )

        assert result.success is True