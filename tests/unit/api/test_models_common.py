"""
Unit tests for common API models

Following TDD: Write tests FIRST
"""

import pytest
from pydantic import ValidationError
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.models.common import (
    ErrorResponse,
    SuccessResponse,
    MessageResponse
)


class TestErrorResponse:
    """Test ErrorResponse model"""

    def test_error_response_minimal(self):
        """Should create ErrorResponse with just error message"""
        # Arrange & Act
        response = ErrorResponse(error="Something went wrong")

        # Assert
        assert response.error == "Something went wrong"
        assert response.details is None
        assert response.code is None

    def test_error_response_with_code(self):
        """Should create ErrorResponse with error code"""
        # Arrange & Act
        response = ErrorResponse(
            error="Server not found",
            code="SERVER_NOT_FOUND"
        )

        # Assert
        assert response.error == "Server not found"
        assert response.code == "SERVER_NOT_FOUND"

    def test_error_response_with_details(self):
        """Should create ErrorResponse with details dict"""
        # Arrange & Act
        response = ErrorResponse(
            error="Validation failed",
            code="VALIDATION_ERROR",
            details={"field": "name", "issue": "too short"}
        )

        # Assert
        assert response.error == "Validation failed"
        assert response.code == "VALIDATION_ERROR"
        assert response.details == {"field": "name", "issue": "too short"}

    def test_error_response_serialization(self):
        """Should serialize to JSON correctly"""
        # Arrange
        response = ErrorResponse(
            error="Test error",
            code="TEST_ERROR",
            details={"key": "value"}
        )

        # Act
        json_data = response.model_dump()

        # Assert
        assert json_data["error"] == "Test error"
        assert json_data["code"] == "TEST_ERROR"
        assert json_data["details"] == {"key": "value"}

    def test_error_response_requires_error_field(self):
        """Should require error field"""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse()

        assert "error" in str(exc_info.value)


class TestSuccessResponse:
    """Test SuccessResponse model"""

    def test_success_response_minimal(self):
        """Should create SuccessResponse with success flag and message"""
        # Arrange & Act
        response = SuccessResponse(
            success=True,
            message="Operation completed"
        )

        # Assert
        assert response.success is True
        assert response.message == "Operation completed"
        assert response.data is None

    def test_success_response_with_data(self):
        """Should create SuccessResponse with data dict"""
        # Arrange & Act
        response = SuccessResponse(
            success=True,
            message="Server created",
            data={"server_id": "123", "ip": "1.2.3.4"}
        )

        # Assert
        assert response.success is True
        assert response.message == "Server created"
        assert response.data == {"server_id": "123", "ip": "1.2.3.4"}

    def test_success_response_false(self):
        """Should allow success=False for partial success cases"""
        # Arrange & Act
        response = SuccessResponse(
            success=False,
            message="Partially completed"
        )

        # Assert
        assert response.success is False

    def test_success_response_serialization(self):
        """Should serialize to JSON correctly"""
        # Arrange
        response = SuccessResponse(
            success=True,
            message="Test",
            data={"key": "value"}
        )

        # Act
        json_data = response.model_dump()

        # Assert
        assert json_data["success"] is True
        assert json_data["message"] == "Test"
        assert json_data["data"] == {"key": "value"}


class TestMessageResponse:
    """Test MessageResponse model"""

    def test_message_response_simple(self):
        """Should create MessageResponse with just message"""
        # Arrange & Act
        response = MessageResponse(message="Hello")

        # Assert
        assert response.message == "Hello"

    def test_message_response_requires_message(self):
        """Should require message field"""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            MessageResponse()

        assert "message" in str(exc_info.value)

    def test_message_response_serialization(self):
        """Should serialize to JSON correctly"""
        # Arrange
        response = MessageResponse(message="Test message")

        # Act
        json_data = response.model_dump()

        # Assert
        assert json_data["message"] == "Test message"


class TestModelIntegration:
    """Test that models work with FastAPI"""

    def test_models_are_json_serializable(self):
        """All models should be JSON serializable"""
        # Arrange
        models = [
            ErrorResponse(error="test"),
            SuccessResponse(success=True, message="test"),
            MessageResponse(message="test")
        ]

        # Act & Assert
        for model in models:
            json_data = model.model_dump_json()
            assert isinstance(json_data, str)
            assert len(json_data) > 0

    def test_models_have_schema(self):
        """All models should generate JSON schema"""
        # Arrange
        models = [ErrorResponse, SuccessResponse, MessageResponse]

        # Act & Assert
        for model_class in models:
            schema = model_class.model_json_schema()
            assert "properties" in schema
            assert "title" in schema
