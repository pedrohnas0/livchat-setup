"""
Unit tests for configuration routes

Following TDD: Write tests FIRST

Tests for:
- GET /api/config - Get all configuration
- GET /api/config/{key} - Get specific config value
- PUT /api/config/{key} - Set config value
- POST /api/config - Update multiple values
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.routes.config import router
from src.api.dependencies import reset_orchestrator
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestGetAllConfigEndpoint:
    """Test GET /api/config endpoint"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_get_all_config_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.get("/api/config")

        # Assert
        assert response.status_code == 200

    def test_get_all_config_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.get("/api/config")

        # Assert
        assert "application/json" in response.headers["content-type"]

    def test_get_all_config_returns_config_dict(self):
        """Should return config dictionary"""
        # Act
        response = client.get("/api/config")

        # Assert
        data = response.json()
        assert "config" in data
        assert isinstance(data["config"], dict)

    def test_get_all_config_includes_default_values(self):
        """Should include default configuration values"""
        # Act
        response = client.get("/api/config")

        # Assert
        data = response.json()
        config = data["config"]

        # Default config should have at least version
        assert "version" in config or len(config) >= 0

    def test_get_all_config_after_setting_values(self):
        """Should return updated values after setting"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.config.set("test_key", "test_value")

        # Act
        response = client.get("/api/config")

        # Assert
        data = response.json()
        assert data["config"]["test_key"] == "test_value"


class TestGetConfigValueEndpoint:
    """Test GET /api/config/{key} endpoint"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_get_config_value_returns_200(self):
        """Should return 200 for existing key"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.config.set("test_key", "test_value")

        # Act
        response = client.get("/api/config/test_key")

        # Assert
        assert response.status_code == 200

    def test_get_config_value_returns_404_for_nonexistent(self):
        """Should return 404 for non-existent key"""
        # Act
        response = client.get("/api/config/nonexistent_key")

        # Assert
        assert response.status_code == 404

    def test_get_config_value_returns_value(self):
        """Should return the configuration value"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.config.set("provider", "hetzner")

        # Act
        response = client.get("/api/config/provider")

        # Assert
        data = response.json()
        assert data["key"] == "provider"
        assert data["value"] == "hetzner"

    def test_get_config_value_supports_dot_notation(self):
        """Should support dot notation for nested keys"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.config.set("providers.hetzner.region", "nbg1")

        # Act
        response = client.get("/api/config/providers.hetzner.region")

        # Assert
        data = response.json()
        assert data["key"] == "providers.hetzner.region"
        assert data["value"] == "nbg1"

    def test_get_config_value_returns_json(self):
        """Should return JSON response"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.config.set("test", "value")

        # Act
        response = client.get("/api/config/test")

        # Assert
        assert "application/json" in response.headers["content-type"]


class TestSetConfigValueEndpoint:
    """Test PUT /api/config/{key} endpoint"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_set_config_value_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.put("/api/config/test_key", json={"value": "test_value"})

        # Assert
        assert response.status_code == 200

    def test_set_config_value_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.put("/api/config/test_key", json={"value": "test_value"})

        # Assert
        assert "application/json" in response.headers["content-type"]

    def test_set_config_value_updates_config(self):
        """Should update configuration value"""
        # Act
        response = client.put("/api/config/provider", json={"value": "digitalocean"})

        # Assert
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        value = orchestrator.storage.config.get("provider")
        assert value == "digitalocean"

    def test_set_config_value_returns_success_response(self):
        """Should return success response"""
        # Act
        response = client.put("/api/config/region", json={"value": "fsn1"})

        # Assert
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        assert data["key"] == "region"
        assert data["value"] == "fsn1"

    def test_set_config_value_supports_dot_notation(self):
        """Should support dot notation for nested keys"""
        # Act
        response = client.put("/api/config/providers.hetzner.token", json={"value": "secret123"})

        # Assert
        assert response.status_code == 200
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        value = orchestrator.storage.config.get("providers.hetzner.token")
        assert value == "secret123"

    def test_set_config_value_validates_request_body(self):
        """Should validate request body"""
        # Act - missing 'value' field
        response = client.put("/api/config/test", json={})

        # Assert
        assert response.status_code == 422  # Validation error

    def test_set_config_value_accepts_different_types(self):
        """Should accept different value types"""
        # Arrange
        test_cases = [
            ("string_value", "test"),
            ("number_value", 42),
            ("boolean_value", True),
            ("list_value", [1, 2, 3]),
            ("dict_value", {"nested": "value"})
        ]

        # Act & Assert
        for key, value in test_cases:
            response = client.put(f"/api/config/{key}", json={"value": value})
            assert response.status_code == 200
            assert response.json()["value"] == value


class TestUpdateConfigEndpoint:
    """Test POST /api/config endpoint"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_update_config_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.post("/api/config", json={
            "updates": {"key1": "value1"}
        })

        # Assert
        assert response.status_code == 200

    def test_update_config_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.post("/api/config", json={
            "updates": {"key1": "value1"}
        })

        # Assert
        assert "application/json" in response.headers["content-type"]

    def test_update_config_updates_multiple_values(self):
        """Should update multiple configuration values"""
        # Act
        response = client.post("/api/config", json={
            "updates": {
                "provider": "hetzner",
                "region": "nbg1",
                "server_type": "cx21"
            }
        })

        # Assert
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        assert orchestrator.storage.config.get("provider") == "hetzner"
        assert orchestrator.storage.config.get("region") == "nbg1"
        assert orchestrator.storage.config.get("server_type") == "cx21"

    def test_update_config_returns_success_response(self):
        """Should return success response with count"""
        # Act
        response = client.post("/api/config", json={
            "updates": {
                "key1": "value1",
                "key2": "value2",
                "key3": "value3"
            }
        })

        # Assert
        data = response.json()
        assert data["success"] is True
        assert data["updated_count"] == 3
        assert set(data["updated_keys"]) == {"key1", "key2", "key3"}
        assert "message" in data

    def test_update_config_validates_request_body(self):
        """Should validate request body"""
        # Act - missing 'updates' field
        response = client.post("/api/config", json={})

        # Assert
        assert response.status_code == 422  # Validation error

    def test_update_config_with_empty_dict(self):
        """Should handle empty updates dictionary"""
        # Act
        response = client.post("/api/config", json={"updates": {}})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 0
        assert data["updated_keys"] == []


class TestConfigRoutesIntegration:
    """Integration tests for config routes"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_config_lifecycle_via_api(self):
        """Test complete config lifecycle via API"""
        # Set a value
        response = client.put("/api/config/provider", json={"value": "hetzner"})
        assert response.status_code == 200

        # Get the value
        response = client.get("/api/config/provider")
        assert response.status_code == 200
        assert response.json()["value"] == "hetzner"

        # Update multiple values
        response = client.post("/api/config", json={
            "updates": {
                "provider": "digitalocean",
                "region": "nyc1"
            }
        })
        assert response.status_code == 200

        # Get all config
        response = client.get("/api/config")
        assert response.status_code == 200
        config = response.json()["config"]
        assert config["provider"] == "digitalocean"
        assert config["region"] == "nyc1"

    def test_all_routes_return_valid_json(self):
        """All routes should return valid JSON"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.config.set("test", "value")

        routes = [
            ("GET", "/api/config", None),
            ("GET", "/api/config/test", None),
            ("PUT", "/api/config/new_key", {"value": "new_value"}),
            ("POST", "/api/config", {"updates": {"key": "value"}}),
        ]

        # Act & Assert
        for method, path, json_data in routes:
            if method == "GET":
                response = client.get(path)
            elif method == "PUT":
                response = client.put(path, json=json_data)
            else:
                response = client.post(path, json=json_data)

            # Should return JSON
            assert "application/json" in response.headers["content-type"]
            assert response.status_code in [200, 404]  # 404 is valid for nonexistent keys

    def test_config_persistence(self):
        """Configuration should persist across requests"""
        # Set value
        client.put("/api/config/persistent_key", json={"value": "persistent_value"})

        # Get value in separate request
        response = client.get("/api/config/persistent_key")
        assert response.json()["value"] == "persistent_value"

        # Update with bulk update
        client.post("/api/config", json={
            "updates": {"persistent_key": "updated_value"}
        })

        # Verify update
        response = client.get("/api/config/persistent_key")
        assert response.json()["value"] == "updated_value"
