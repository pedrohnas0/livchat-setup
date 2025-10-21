"""Unit tests for remote command execution via SSH"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from src.orchestrator.core import Orchestrator


class TestRemoteCommandExecution:
    """Test execute_remote_command() method"""

    @pytest.fixture
    def mock_storage(self, tmp_path):
        """Create mock storage with temp directory"""
        storage = Mock()
        storage.state = Mock()
        storage.state.get_server = Mock(return_value={
            "name": "test-server",
            "ip": "1.2.3.4",
            "status": "running"
        })
        return storage

    @pytest.fixture
    def mock_ssh_manager(self, tmp_path):
        """Create mock SSH manager"""
        ssh_manager = Mock()
        # Create a fake key file
        key_file = tmp_path / "test-server"
        key_file.write_text("fake_ssh_key")
        key_file.chmod(0o600)
        ssh_manager.get_private_key_path = Mock(return_value=key_file)
        ssh_manager.keys_dir = tmp_path
        return ssh_manager

    @pytest.fixture
    def orchestrator(self, tmp_path, mock_storage, mock_ssh_manager):
        """Create Orchestrator with mocked dependencies"""
        orch = Orchestrator(config_dir=tmp_path)
        orch.storage = mock_storage
        orch.ssh_manager = mock_ssh_manager
        return orch

    @pytest.mark.asyncio
    async def test_execute_simple_command_success(self, orchestrator):
        """Should execute simple command and return output"""
        # Mock asyncssh connection
        mock_result = Mock()
        mock_result.stdout = "total 48K\ndrwxr-xr-x 12 root root 4.0K"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            result = await orchestrator.execute_remote_command(
                server_name="test-server",
                command="ls -lah",
                timeout=30
            )

            assert result["success"] is True
            assert "total 48K" in result["stdout"]
            assert result["stderr"] == ""
            assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_execute_command_with_error(self, orchestrator):
        """Should handle command execution with non-zero exit code"""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = "command not found: badcmd"
        mock_result.exit_status = 127

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            result = await orchestrator.execute_remote_command(
                server_name="test-server",
                command="badcmd",
                timeout=10
            )

            assert result["success"] is False
            assert result["exit_code"] == 127
            assert "command not found" in result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, orchestrator):
        """Should raise TimeoutError on command timeout"""
        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            # Simulate long-running command
            async def long_run(*args, **kwargs):
                await asyncio.sleep(100)
                return Mock(stdout="", stderr="", exit_status=0)

            mock_conn.run = long_run
            mock_connect.return_value.__aenter__.return_value = mock_conn

            with pytest.raises(asyncio.TimeoutError):
                await orchestrator.execute_remote_command(
                    server_name="test-server",
                    command="sleep 100",
                    timeout=1
                )

    @pytest.mark.asyncio
    async def test_execute_command_with_working_directory(self, orchestrator):
        """Should execute command in specified working directory"""
        mock_result = Mock()
        mock_result.stdout = "/var/log"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            result = await orchestrator.execute_remote_command(
                server_name="test-server",
                command="pwd",
                working_dir="/var/log",
                timeout=10
            )

            # Verify command was wrapped with cd
            call_args = mock_conn.run.call_args
            executed_command = call_args[0][0]
            assert "cd /var/log" in executed_command
            assert "pwd" in executed_command

    @pytest.mark.asyncio
    async def test_execute_truncates_large_output(self, orchestrator):
        """Should truncate output larger than 10KB"""
        # Create output larger than 10KB
        large_output = "x" * 15000

        mock_result = Mock()
        mock_result.stdout = large_output
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            result = await orchestrator.execute_remote_command(
                server_name="test-server",
                command="cat large_file.txt",
                timeout=10
            )

            # Should truncate to 10KB
            assert len(result["stdout"]) <= 10240 + 100  # 10KB + truncation message
            assert "[OUTPUT TRUNCATED" in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_rejects_dangerous_command(self, orchestrator):
        """Should reject dangerous commands via security validator"""
        from src.security import is_dangerous_command

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.execute_remote_command(
                server_name="test-server",
                command="rm -rf /",
                timeout=10
            )

        assert "dangerous" in str(exc_info.value).lower() or "rejected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_server_not_found(self, orchestrator):
        """Should raise error if server not found"""
        orchestrator.storage.state.get_server = Mock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.execute_remote_command(
                server_name="nonexistent",
                command="ls",
                timeout=10
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_ssh_key_not_found(self, orchestrator):
        """Should raise error if SSH key not found"""
        orchestrator.ssh_manager.get_private_key_path = Mock(
            side_effect=FileNotFoundError("SSH key not found")
        )

        with pytest.raises(FileNotFoundError):
            await orchestrator.execute_remote_command(
                server_name="test-server",
                command="ls",
                timeout=10
            )

    @pytest.mark.asyncio
    async def test_execute_connection_refused(self, orchestrator):
        """Should handle SSH connection errors"""
        with patch('asyncssh.connect') as mock_connect:
            mock_connect.side_effect = OSError("Connection refused")

            with pytest.raises(OSError) as exc_info:
                await orchestrator.execute_remote_command(
                    server_name="test-server",
                    command="ls",
                    timeout=10
                )

            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_with_default_timeout(self, orchestrator):
        """Should use default timeout if not specified"""
        mock_result = Mock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            # Call without timeout parameter
            result = await orchestrator.execute_remote_command(
                server_name="test-server",
                command="echo hello"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_uses_correct_ssh_params(self, orchestrator):
        """Should connect with correct SSH parameters"""
        mock_result = Mock()
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            await orchestrator.execute_remote_command(
                server_name="test-server",
                command="uptime",
                timeout=10
            )

            # Verify connect was called with correct params
            mock_connect.assert_called_once()
            call_args = mock_connect.call_args
            assert call_args[0][0] == "1.2.3.4"  # Server IP
            assert call_args[1]["username"] == "root"
            assert "client_keys" in call_args[1]
            assert call_args[1]["known_hosts"] is None  # Accept any host key


class TestRemoteCommandEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create basic orchestrator"""
        return Orchestrator(config_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_empty_command(self, orchestrator, tmp_path):
        """Should handle empty command gracefully"""
        orchestrator.storage = Mock()
        orchestrator.storage.state = Mock()
        orchestrator.storage.state.get_server = Mock(return_value={
            "name": "test", "ip": "1.2.3.4"
        })
        orchestrator.ssh_manager = Mock()
        key_file = tmp_path / "test"
        key_file.write_text("key")
        orchestrator.ssh_manager.get_private_key_path = Mock(return_value=key_file)

        with pytest.raises((ValueError, TypeError)):
            await orchestrator.execute_remote_command(
                server_name="test",
                command="",
                timeout=10
            )

    @pytest.mark.asyncio
    async def test_command_with_unicode(self, orchestrator, tmp_path):
        """Should handle unicode in commands"""
        orchestrator.storage = Mock()
        orchestrator.storage.state = Mock()
        orchestrator.storage.state.get_server = Mock(return_value={
            "name": "test", "ip": "1.2.3.4"
        })
        orchestrator.ssh_manager = Mock()
        key_file = tmp_path / "test"
        key_file.write_text("key")
        key_file.chmod(0o600)
        orchestrator.ssh_manager.get_private_key_path = Mock(return_value=key_file)

        mock_result = Mock()
        mock_result.stdout = "Olá mundo"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            result = await orchestrator.execute_remote_command(
                server_name="test",
                command="echo 'Olá mundo'",
                timeout=10
            )

            assert "Olá" in result["stdout"]

    @pytest.mark.asyncio
    async def test_uses_ssh_key_from_server_state_not_server_name(self, tmp_path):
        """Should use ssh_key field from server state, not server_name"""
        # Setup storage with server that has custom ssh_key
        storage = Mock()
        storage.state = Mock()
        storage.state.get_server = Mock(return_value={
            "name": "prod-server",
            "ip": "5.161.239.220",
            "ssh_key": "prod-server_key",  # ← Custom key name
            "status": "running"
        })

        # Setup SSH manager
        ssh_manager = Mock()
        key_file = tmp_path / "prod-server_key"
        key_file.write_text("key")
        key_file.chmod(0o600)
        ssh_manager.get_private_key_path = Mock(return_value=key_file)

        # Create orchestrator
        orch = Orchestrator(config_dir=tmp_path)
        orch.storage = storage
        orch.ssh_manager = ssh_manager

        mock_result = Mock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        with patch('asyncssh.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            await orch.execute_remote_command(
                server_name="prod-server",
                command="uname -a"
            )

            # ✅ Should call get_private_key_path with ssh_key from state
            ssh_manager.get_private_key_path.assert_called_once_with("prod-server_key")

            # ❌ Should NOT call with server_name
            # (this is the bug we're fixing)
