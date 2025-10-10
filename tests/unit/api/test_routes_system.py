"""
Unit tests for system routes

Following TDD: Write tests FIRST

Tests for:
- GET /
- GET /health
- POST /api/init
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.routes.system import router
from src.api.dependencies import reset_orchestrator
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestRootEndpoint:
    """Test GET / endpoint"""

    def test_root_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200

    def test_root_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.get("/")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_root_contains_message(self):
        """Should contain welcome message"""
        # Act
        response = client.get("/")
        data = response.json()

        # Assert
        assert "message" in data
        assert "LivChatSetup" in data["message"]

    def test_root_contains_version(self):
        """Should contain API version"""
        # Act
        response = client.get("/")
        data = response.json()

        # Assert
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_root_contains_docs_url(self):
        """Should contain documentation URL"""
        # Act
        response = client.get("/")
        data = response.json()

        # Assert
        assert "docs" in data
        assert data["docs"] == "/docs"


class TestHealthEndpoint:
    """Test GET /health endpoint"""

    def test_health_returns_200(self):
        """Should return 200 OK when healthy"""
        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200

    def test_health_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.get("/health")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_health_contains_status_ok(self):
        """Should contain status: ok"""
        # Act
        response = client.get("/health")
        data = response.json()

        # Assert
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_contains_timestamp(self):
        """Should contain timestamp"""
        # Act
        response = client.get("/health")
        data = response.json()

        # Assert
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)


class TestInitEndpoint:
    """Test POST /api/init endpoint"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_init_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.post("/api/init")

        # Assert
        assert response.status_code == 200

    def test_init_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.post("/api/init")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_init_returns_success(self):
        """Should return success response"""
        # Act
        response = client.post("/api/init")
        data = response.json()

        # Assert
        assert "success" in data
        assert data["success"] is True

    def test_init_returns_message(self):
        """Should return success message"""
        # Act
        response = client.post("/api/init")
        data = response.json()

        # Assert
        assert "message" in data
        assert "initialized" in data["message"].lower()

    def test_init_returns_config_dir(self):
        """Should return config directory path"""
        # Act
        response = client.post("/api/init")
        data = response.json()

        # Assert
        assert "data" in data
        assert "config_dir" in data["data"]
        assert ".livchat" in data["data"]["config_dir"]

    def test_init_creates_orchestrator(self):
        """Should initialize orchestrator"""
        # Arrange
        reset_orchestrator()

        # Act
        response = client.post("/api/init")

        # Assert
        assert response.status_code == 200
        # Orchestrator should be created and initialized
        from src.api.dependencies import get_orchestrator
        orch = get_orchestrator()
        assert orch is not None

    def test_init_idempotent(self):
        """Should be idempotent - safe to call multiple times"""
        # Act
        response1 = client.post("/api/init")
        response2 = client.post("/api/init")

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Both should return same config_dir
        assert response1.json()["data"]["config_dir"] == response2.json()["data"]["config_dir"]


class TestRouteIntegration:
    """Test routes work together"""

    def test_all_routes_accessible(self):
        """All routes should be accessible without errors"""
        # Arrange
        routes = [
            ("GET", "/"),
            ("GET", "/health"),
            ("POST", "/api/init"),
        ]

        # Act & Assert
        for method, path in routes:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path)

            assert response.status_code == 200, f"{method} {path} failed"

    def test_routes_return_valid_json(self):
        """All routes should return valid JSON"""
        # Arrange
        routes = ["/", "/health", "/api/init"]

        # Act & Assert
        for route in routes:
            if route == "/api/init":
                response = client.post(route)
            else:
                response = client.get(route)

            # Should be valid JSON
            data = response.json()
            assert isinstance(data, dict)
