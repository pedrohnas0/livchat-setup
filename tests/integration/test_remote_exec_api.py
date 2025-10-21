"""Integration tests for remote command execution API endpoint"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import AsyncMock, patch
import asyncio

from src.api.server import app
from src.api.dependencies import get_orchestrator, reset_orchestrator
from src.orchestrator import Orchestrator


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory"""
    config_dir = tmp_path / ".livchat"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def orchestrator(temp_config_dir):
    """Create orchestrator with temp directory"""
    orch = Orchestrator(config_dir=temp_config_dir)

    # Add test server to state
    server_data = {
        "name": "test-server",
        "ip": "1.2.3.4",
        "provider": "hetzner",
        "status": "running",
        "type": "cx11",
        "region": "nbg1"
    }
    orch.storage.state.add_server("test-server", server_data)

    return orch


@pytest.fixture
def client(orchestrator):
    """Create test client with mocked orchestrator dependency"""
    # Override dependency
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator

    client = TestClient(app)
    yield client

    # Cleanup
    app.dependency_overrides.clear()
    reset_orchestrator()


class TestRemoteExecEndpoint:
    """Test POST /api/servers/{name}/exec endpoint"""

    def test_exec_simple_command_success(self, client, orchestrator):
        """Should execute simple command and return result"""
        # Mock execute_remote_command
        async def mock_exec(*args, **kwargs):
            return {
                "success": True,
                "stdout": "nginx is running",
                "stderr": "",
                "exit_code": 0
            }

        orchestrator.execute_remote_command = mock_exec

        # Make request
        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "docker ps | grep nginx",
                "timeout": 10
            }
        )

        # Validate response
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["server_name"] == "test-server"
        assert data["command"] == "docker ps | grep nginx"
        assert "nginx is running" in data["stdout"]
        assert data["stderr"] == ""
        assert data["exit_code"] == 0
        assert data["timeout_seconds"] == 10

    def test_exec_command_with_working_dir(self, client, orchestrator):
        """Should execute command in specified working directory"""
        async def mock_exec(*args, **kwargs):
            return {
                "success": True,
                "stdout": "/var/log",
                "stderr": "",
                "exit_code": 0
            }

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "pwd",
                "timeout": 5,
                "working_dir": "/var/log"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["working_dir"] == "/var/log"

    def test_exec_command_with_error_exit_code(self, client, orchestrator):
        """Should return non-zero exit code for failed commands"""
        async def mock_exec(*args, **kwargs):
            return {
                "success": False,
                "stdout": "",
                "stderr": "command not found: badcmd",
                "exit_code": 127
            }

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "badcmd",
                "timeout": 10
            }
        )

        # Still 200 OK (command executed, just failed)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["exit_code"] == 127
        assert "command not found" in data["stderr"]

    def test_exec_dangerous_command_rejected(self, client, orchestrator):
        """Should reject dangerous commands with 400 Bad Request"""
        async def mock_exec(*args, **kwargs):
            raise ValueError("Command rejected by security policy: rm -rf /")

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "rm -rf /",
                "timeout": 10
            }
        )

        assert response.status_code == 400
        assert "security" in response.json()["detail"].lower()

    def test_exec_empty_command_rejected(self, client, orchestrator):
        """Should reject empty commands with validation error"""
        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "",
                "timeout": 10
            }
        )

        # Pydantic validation error
        assert response.status_code == 422

    def test_exec_server_not_found(self, client, orchestrator):
        """Should return 404 if server doesn't exist"""
        response = client.post(
            "/api/servers/nonexistent-server/exec",
            json={
                "command": "ls",
                "timeout": 10
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_exec_ssh_key_not_found(self, client, orchestrator):
        """Should return 404 if SSH key missing"""
        async def mock_exec(*args, **kwargs):
            raise FileNotFoundError("SSH key not found for server test-server")

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "ls",
                "timeout": 10
            }
        )

        assert response.status_code == 404
        assert "ssh key" in response.json()["detail"].lower()

    def test_exec_timeout_error(self, client, orchestrator):
        """Should return 500 if command times out"""
        async def mock_exec(*args, **kwargs):
            raise TimeoutError()

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "sleep 100",
                "timeout": 1
            }
        )

        assert response.status_code == 500
        assert "timed out" in response.json()["detail"].lower()

    def test_exec_ssh_connection_error(self, client, orchestrator):
        """Should return 500 on SSH connection errors"""
        async def mock_exec(*args, **kwargs):
            raise OSError("Connection refused")

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "ls",
                "timeout": 10
            }
        )

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()

    def test_exec_default_timeout(self, client, orchestrator):
        """Should use default timeout if not specified"""
        async def mock_exec(*args, **kwargs):
            return {
                "success": True,
                "stdout": "ok",
                "stderr": "",
                "exit_code": 0
            }

        orchestrator.execute_remote_command = mock_exec

        # Don't specify timeout
        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "echo ok"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Default timeout is 30s (from RemoteExecRequest model)
        assert data["timeout_seconds"] == 30

    def test_exec_max_timeout_validation(self, client, orchestrator):
        """Should reject timeout > 300s"""
        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "sleep 1000",
                "timeout": 600  # 10 minutes - too long
            }
        )

        # Pydantic validation error (le=300)
        assert response.status_code == 422

    def test_exec_truncated_output(self, client, orchestrator):
        """Should indicate when output is truncated"""
        large_output = "x" * 15000

        async def mock_exec(*args, **kwargs):
            return {
                "success": True,
                "stdout": large_output[:10240] + "\n[OUTPUT TRUNCATED - exceeds 10KB limit]",
                "stderr": "",
                "exit_code": 0
            }

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "cat large_file.txt",
                "timeout": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "[OUTPUT TRUNCATED" in data["stdout"]
        # Should be around 10KB
        assert len(data["stdout"]) <= 10240 + 100

    def test_exec_response_schema_complete(self, client, orchestrator):
        """Should return all expected fields in response"""
        async def mock_exec(*args, **kwargs):
            return {
                "success": True,
                "stdout": "test output",
                "stderr": "test error",
                "exit_code": 0
            }

        orchestrator.execute_remote_command = mock_exec

        response = client.post(
            "/api/servers/test-server/exec",
            json={
                "command": "test command",
                "timeout": 15,
                "working_dir": "/tmp"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Validate all required fields present
        required_fields = [
            "success", "server_name", "command",
            "stdout", "stderr", "exit_code",
            "timeout_seconds", "working_dir"
        ]

        for field in required_fields:
            assert field in data

        # Validate field values
        assert data["success"] is True
        assert data["server_name"] == "test-server"
        assert data["command"] == "test command"
        assert data["stdout"] == "test output"
        assert data["stderr"] == "test error"
        assert data["exit_code"] == 0
        assert data["timeout_seconds"] == 15
        assert data["working_dir"] == "/tmp"


class TestRemoteExecIntegration:
    """Integration tests with real components"""

    def test_full_workflow_with_mocked_ssh(self, client, orchestrator, tmp_path):
        """Test complete workflow with mocked SSH connection"""
        # Create fake SSH key
        ssh_key_path = tmp_path / "ssh_keys" / "test-server"
        ssh_key_path.parent.mkdir(parents=True)
        ssh_key_path.write_text("fake_private_key")
        ssh_key_path.chmod(0o600)

        # Mock SSH manager
        orchestrator.ssh_manager.get_private_key_path = lambda name: ssh_key_path

        # Mock asyncssh connection
        with patch('asyncssh.connect') as mock_connect:
            mock_result = AsyncMock()
            mock_result.stdout = "Docker version 24.0.5"
            mock_result.stderr = ""
            mock_result.exit_status = 0

            mock_conn = AsyncMock()
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value.__aenter__.return_value = mock_conn

            # Execute request
            response = client.post(
                "/api/servers/test-server/exec",
                json={
                    "command": "docker --version",
                    "timeout": 10
                }
            )

            # Validate
            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "Docker version" in data["stdout"]

            # Verify SSH connection was called correctly
            mock_connect.assert_called_once()
            call_args = mock_connect.call_args
            assert call_args[0][0] == "1.2.3.4"  # Server IP
            assert call_args[1]["username"] == "root"
            assert call_args[1]["known_hosts"] is None
