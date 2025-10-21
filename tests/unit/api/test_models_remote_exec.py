"""
Unit tests for remote exec API models

Following TDD: Write tests FIRST
"""

import pytest
from pydantic import ValidationError
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.models.remote_exec import (
    RemoteExecRequest,
    RemoteExecResponse,
    RemoteExecErrorResponse
)


class TestRemoteExecRequest:
    """Test RemoteExecRequest model"""

    def test_remote_exec_request_minimal(self):
        """Should create RemoteExecRequest with just command"""
        # Arrange & Act
        request = RemoteExecRequest(command="docker ps")

        # Assert
        assert request.command == "docker ps"
        assert request.timeout == 30  # default
        assert request.working_dir is None
        assert request.use_job is False  # default

    def test_remote_exec_request_with_use_job_true(self):
        """Should create RemoteExecRequest with use_job=True"""
        # Arrange & Act
        request = RemoteExecRequest(
            command="docker logs container-id",
            timeout=120,
            use_job=True
        )

        # Assert
        assert request.command == "docker logs container-id"
        assert request.timeout == 120
        assert request.use_job is True

    def test_remote_exec_request_with_use_job_false(self):
        """Should create RemoteExecRequest with use_job=False"""
        # Arrange & Act
        request = RemoteExecRequest(
            command="uname -a",
            use_job=False
        )

        # Assert
        assert request.command == "uname -a"
        assert request.use_job is False

    def test_remote_exec_request_with_all_parameters(self):
        """Should create RemoteExecRequest with all parameters"""
        # Arrange & Act
        request = RemoteExecRequest(
            command="ls -la",
            timeout=60,
            working_dir="/var/log",
            use_job=True
        )

        # Assert
        assert request.command == "ls -la"
        assert request.timeout == 60
        assert request.working_dir == "/var/log"
        assert request.use_job is True

    def test_remote_exec_request_serialization_with_use_job(self):
        """Should serialize to JSON correctly with use_job field"""
        # Arrange
        request = RemoteExecRequest(
            command="docker ps",
            timeout=45,
            use_job=True
        )

        # Act
        json_data = request.model_dump()

        # Assert
        assert json_data["command"] == "docker ps"
        assert json_data["timeout"] == 45
        assert json_data["use_job"] is True

    def test_remote_exec_request_requires_command(self):
        """Should require command field"""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            RemoteExecRequest()

        assert "command" in str(exc_info.value)

    def test_remote_exec_request_command_not_empty(self):
        """Should reject empty or whitespace-only commands"""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            RemoteExecRequest(command="   ")

        assert "cannot be empty" in str(exc_info.value).lower()

    def test_remote_exec_request_strips_whitespace(self):
        """Should strip whitespace from command"""
        # Arrange & Act
        request = RemoteExecRequest(command="  docker ps  ")

        # Assert
        assert request.command == "docker ps"

    def test_remote_exec_request_timeout_constraints(self):
        """Should enforce timeout constraints (1-300 seconds)"""
        # Valid timeouts
        valid_request = RemoteExecRequest(command="test", timeout=150)
        assert valid_request.timeout == 150

        # Too small
        with pytest.raises(ValidationError):
            RemoteExecRequest(command="test", timeout=0)

        # Too large
        with pytest.raises(ValidationError):
            RemoteExecRequest(command="test", timeout=301)


class TestRemoteExecResponse:
    """Test RemoteExecResponse model"""

    def test_remote_exec_response_success(self):
        """Should create successful RemoteExecResponse"""
        # Arrange & Act
        response = RemoteExecResponse(
            success=True,
            server_name="test-server",
            command="uname -a",
            stdout="Linux test-server 5.10.0",
            stderr="",
            exit_code=0,
            timeout_seconds=30
        )

        # Assert
        assert response.success is True
        assert response.server_name == "test-server"
        assert response.command == "uname -a"
        assert response.stdout == "Linux test-server 5.10.0"
        assert response.stderr == ""
        assert response.exit_code == 0
        assert response.timeout_seconds == 30
        assert response.working_dir is None

    def test_remote_exec_response_with_working_dir(self):
        """Should create RemoteExecResponse with working directory"""
        # Arrange & Act
        response = RemoteExecResponse(
            success=True,
            server_name="test-server",
            command="ls",
            stdout="file1.txt\nfile2.txt",
            stderr="",
            exit_code=0,
            timeout_seconds=30,
            working_dir="/var/log"
        )

        # Assert
        assert response.working_dir == "/var/log"


class TestRemoteExecErrorResponse:
    """Test RemoteExecErrorResponse model"""

    def test_remote_exec_error_response_minimal(self):
        """Should create RemoteExecErrorResponse with just error"""
        # Arrange & Act
        response = RemoteExecErrorResponse(error="Command failed")

        # Assert
        assert response.success is False
        assert response.error == "Command failed"
        assert response.detail is None
        assert response.server_name is None
        assert response.command is None

    def test_remote_exec_error_response_complete(self):
        """Should create RemoteExecErrorResponse with all fields"""
        # Arrange & Act
        response = RemoteExecErrorResponse(
            error="SSH connection failed",
            detail="Timeout after 30 seconds",
            server_name="test-server",
            command="docker ps"
        )

        # Assert
        assert response.success is False
        assert response.error == "SSH connection failed"
        assert response.detail == "Timeout after 30 seconds"
        assert response.server_name == "test-server"
        assert response.command == "docker ps"
