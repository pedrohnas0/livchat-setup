"""
Unit tests for API secrets routes

Tests for secrets management endpoints:
- GET /api/secrets - List secret keys
- GET /api/secrets/{key} - Get secret value
- PUT /api/secrets/{key} - Set secret value
- DELETE /api/secrets/{key} - Delete secret
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.routes.secrets import router
from src.api.dependencies import reset_orchestrator, get_orchestrator
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestSecretsRoutes:
    """Test secrets management routes"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

        # Clear all secrets from vault to ensure clean state
        orchestrator = get_orchestrator()
        for key in orchestrator.storage.secrets.list_secret_keys():
            orchestrator.storage.secrets.remove_secret(key)

    def teardown_method(self):
        """Cleanup after each test"""
        reset_orchestrator()

    def test_list_secret_keys(self):
        """Should list all secret keys without values"""
        # Arrange
        orchestrator = get_orchestrator()
        orchestrator.storage.secrets.set_secret("hetzner_token", "test_token_123")
        orchestrator.storage.secrets.set_secret("cloudflare_api_key", "test_key_456")

        # Act
        response = client.get("/api/secrets")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) == 2
        assert "hetzner_token" in data["keys"]
        assert "cloudflare_api_key" in data["keys"]
        assert "total" in data
        assert data["total"] == 2

    def test_get_secret_value(self):
        """Should get secret value for existing key"""
        # Arrange
        orchestrator = get_orchestrator()
        orchestrator.storage.secrets.set_secret("hetzner_token", "test_secret_value")

        # Act
        response = client.get("/api/secrets/hetzner_token")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "hetzner_token"
        assert data["value"] == "test_secret_value"

    def test_get_secret_not_found(self):
        """Should return 404 for non-existent secret"""
        # Act
        response = client.get("/api/secrets/invalid_key")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_set_secret_value(self):
        """Should set secret value"""
        # Act
        response = client.put(
            "/api/secrets/hetzner_token",
            json={"value": "new_token_value_123"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        assert data["key"] == "hetzner_token"

        # Verify secret was actually set
        orchestrator = get_orchestrator()
        saved_value = orchestrator.storage.secrets.get_secret("hetzner_token")
        assert saved_value == "new_token_value_123"

    def test_set_secret_with_empty_value(self):
        """Should reject empty secret value"""
        # Act
        response = client.put(
            "/api/secrets/hetzner_token",
            json={"value": ""}
        )

        # Assert
        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert "detail" in data

    def test_delete_secret(self):
        """Should delete existing secret"""
        # Arrange
        orchestrator = get_orchestrator()
        orchestrator.storage.secrets.set_secret("hetzner_token", "test_value")

        # Act
        response = client.delete("/api/secrets/hetzner_token")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

        # Verify secret was actually deleted
        deleted_value = orchestrator.storage.secrets.get_secret("hetzner_token")
        assert deleted_value is None

    def test_delete_secret_not_found(self):
        """Should return 404 when deleting non-existent secret"""
        # Act
        response = client.delete("/api/secrets/invalid_key")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_set_secret_updates_provider_if_hetzner_token(self):
        """Should note that hetzner_token is critical for provider"""
        # Act
        response = client.put(
            "/api/secrets/hetzner_token",
            json={"value": "hetzner_api_token_123"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        # Should include hint about provider configuration
        assert data["success"] is True
        assert "hetzner" in data["message"].lower()

    def test_list_secrets_returns_empty_array_when_no_secrets(self):
        """Should return empty array when vault has no secrets"""
        # Act
        response = client.get("/api/secrets")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["keys"] == []
        assert data["total"] == 0

    def test_set_secret_with_special_characters(self):
        """Should handle secrets with special characters"""
        # Arrange
        special_value = "token_with_@#$%&*()_+-=[]{}|;:,.<>?"

        # Act
        response = client.put(
            "/api/secrets/test_key",
            json={"value": special_value}
        )

        # Assert
        assert response.status_code == 200

        # Verify secret was saved correctly
        orchestrator = get_orchestrator()
        saved_value = orchestrator.storage.secrets.get_secret("test_key")
        assert saved_value == special_value
