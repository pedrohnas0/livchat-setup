"""
Unit tests for remote command execution with streaming

Testing execute_remote_command_streaming() method that provides
real-time log output via logger.info() for JobLogManager capture.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import logging

from src.orchestrator.core import Orchestrator


class TestRemoteCommandStreaming:
    """Test streaming execution method"""

    @pytest.fixture
    def mock_storage(self, tmp_path):
        """Create mock storage with server"""
        storage = Mock()
        storage.state = Mock()
        storage.state.get_server = Mock(return_value={
            "name": "test-server",
            "ip": "1.2.3.4",
            "status": "running",
            "ssh_key": "test-server_key"
        })
        return storage

    @pytest.fixture
    def mock_ssh_manager(self, tmp_path):
        """Create mock SSH manager"""
        ssh_manager = Mock()
        key_file = tmp_path / "test-server"
        key_file.write_text("fake_ssh_key")
        key_file.chmod(0o600)
        ssh_manager.get_private_key_path = Mock(return_value=key_file)
        return ssh_manager

    @pytest.fixture
    def orchestrator(self, tmp_path, mock_storage, mock_ssh_manager):
        """Create Orchestrator with mocked dependencies"""
        orch = Orchestrator(config_dir=tmp_path)
        orch.storage = mock_storage
        orch.ssh_manager = mock_ssh_manager
        return orch

    @pytest.mark.asyncio
    async def test_streaming_method_exists(self, orchestrator):
        """Should have execute_remote_command_streaming method"""
        assert hasattr(orchestrator, 'execute_remote_command_streaming')
        assert callable(orchestrator.execute_remote_command_streaming)

    @pytest.mark.asyncio
    async def test_streaming_logs_each_stdout_line(self, orchestrator, caplog):
        """Should log each line of stdout in real-time"""

        # Setup logging capture
        caplog.set_level(logging.INFO, logger='src.orchestrator.core')

        # Mock asyncssh connection with streaming process
        with patch('asyncssh.connect') as mock_connect:
            # Mock process that returns output line by line
            mock_proc = AsyncMock()

            # Simulate readline() returning lines one by one
            stdout_lines = [
                b"Line 1\n",
                b"Line 2\n",
                b"Line 3\n",
                b""  # EOF
            ]
            mock_proc.stdout.readline = AsyncMock(side_effect=stdout_lines)
            mock_proc.stderr.readline = AsyncMock(side_effect=[b""])  # No stderr
            mock_proc.returncode = 0
            mock_proc.close = Mock()
            mock_proc.wait = AsyncMock()

            # Mock connection
            mock_conn = AsyncMock()
            mock_conn.create_process = AsyncMock(return_value=mock_proc)

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await orchestrator.execute_remote_command_streaming(
                server_name="test-server",
                command="echo test"
            )

            # Assert logs contain each line
            log_messages = [record.message for record in caplog.records]

            assert any("Line 1" in msg for msg in log_messages), "Should log Line 1"
            assert any("Line 2" in msg for msg in log_messages), "Should log Line 2"
            assert any("Line 3" in msg for msg in log_messages), "Should log Line 3"

            # Assert result contains full output
            assert result["stdout"] == "Line 1\nLine 2\nLine 3"
            assert result["exit_code"] == 0
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_streaming_logs_stderr_separately(self, orchestrator, caplog):
        """Should log stderr lines with warning level"""

        caplog.set_level(logging.WARNING, logger='src.orchestrator.core')

        with patch('asyncssh.connect') as mock_connect:
            mock_proc = AsyncMock()

            # No stdout, only stderr
            mock_proc.stdout.readline = AsyncMock(side_effect=[b""])
            mock_proc.stderr.readline = AsyncMock(side_effect=[
                b"Error line 1\n",
                b"Error line 2\n",
                b""
            ])
            mock_proc.returncode = 1  # Non-zero exit
            mock_proc.close = Mock()
            mock_proc.wait = AsyncMock()

            mock_conn = AsyncMock()
            mock_conn.create_process = AsyncMock(return_value=mock_proc)

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await orchestrator.execute_remote_command_streaming(
                server_name="test-server",
                command="failing-command"
            )

            # Assert stderr logged as warnings
            log_messages = [record.message for record in caplog.records]
            assert any("Error line 1" in msg for msg in log_messages)
            assert any("Error line 2" in msg for msg in log_messages)

            # Assert result
            assert result["stderr"] == "Error line 1\nError line 2"
            assert result["exit_code"] == 1
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_streaming_handles_timeout(self, orchestrator):
        """Should kill process and raise TimeoutError on timeout"""

        with patch('asyncssh.connect') as mock_connect:
            mock_proc = AsyncMock()

            # Simulate never-ending readline (hangs)
            async def hang_forever():
                await asyncio.sleep(999)
                return b"never"

            mock_proc.stdout.readline = hang_forever
            mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
            mock_proc.kill = Mock()  # Track kill() calls
            mock_proc.close = Mock()
            mock_proc.wait = AsyncMock()

            mock_conn = AsyncMock()
            mock_conn.create_process = AsyncMock(return_value=mock_proc)

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute with short timeout
            with pytest.raises(asyncio.TimeoutError):
                await orchestrator.execute_remote_command_streaming(
                    server_name="test-server",
                    command="long-command",
                    timeout=1  # 1 second timeout
                )

            # Should have called kill()
            mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_with_working_directory(self, orchestrator):
        """Should execute command in specified working directory"""

        with patch('asyncssh.connect') as mock_connect:
            mock_proc = AsyncMock()
            mock_proc.stdout.readline = AsyncMock(side_effect=[b"output\n", b""])
            mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
            mock_proc.returncode = 0
            mock_proc.close = Mock()
            mock_proc.wait = AsyncMock()

            mock_conn = AsyncMock()
            mock_conn.create_process = AsyncMock(return_value=mock_proc)

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute with working_dir
            await orchestrator.execute_remote_command_streaming(
                server_name="test-server",
                command="pwd",
                working_dir="/tmp"
            )

            # Should have called create_process with cd command
            call_args = mock_conn.create_process.call_args
            command_used = call_args[0][0]
            assert "cd /tmp" in command_used
            assert "pwd" in command_used

    @pytest.mark.asyncio
    async def test_streaming_validates_dangerous_commands(self, orchestrator):
        """Should reject dangerous commands before execution"""

        # Should raise ValueError for dangerous command
        with pytest.raises(ValueError, match="rejected by security policy"):
            await orchestrator.execute_remote_command_streaming(
                server_name="test-server",
                command="rm -rf /"
            )

    @pytest.mark.asyncio
    async def test_streaming_handles_unicode_output(self, orchestrator):
        """Should handle non-ASCII characters in output"""

        with patch('asyncssh.connect') as mock_connect:
            mock_proc = AsyncMock()

            # Unicode output
            mock_proc.stdout.readline = AsyncMock(side_effect=[
                "Hello 世界\n".encode('utf-8'),
                "Olá 🌍\n".encode('utf-8'),
                b""
            ])
            mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
            mock_proc.returncode = 0
            mock_proc.close = Mock()
            mock_proc.wait = AsyncMock()

            mock_conn = AsyncMock()
            mock_conn.create_process = AsyncMock(return_value=mock_proc)

            mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await orchestrator.execute_remote_command_streaming(
                server_name="test-server",
                command="echo"
            )

            # Should handle unicode correctly
            assert "世界" in result["stdout"]
            assert "🌍" in result["stdout"]
