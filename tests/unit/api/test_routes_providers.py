"""
Unit tests for Provider API routes (TDD approach)

Tests all provider-related endpoints:
- GET /api/providers - List providers
- GET /api/providers/{name} - Get provider details
- GET /api/providers/{name}/regions - List regions
- GET /api/providers/{name}/server-types - List server types
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.server import app
from src.api.dependencies import reset_orchestrator


class TestListProvidersEndpoint:
    """Tests for GET /api/providers"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def test_list_providers_returns_available_providers(self):
        """Should return list of available providers"""
        client = TestClient(app)
        response = client.get("/api/providers")

        assert response.status_code == 200
        data = response.json()

        assert "providers" in data
        assert "total" in data
        assert isinstance(data["providers"], list)
        assert data["total"] == len(data["providers"])

    def test_list_providers_includes_hetzner(self):
        """Should include Hetzner provider"""
        client = TestClient(app)
        response = client.get("/api/providers")

        assert response.status_code == 200
        data = response.json()

        provider_names = [p["name"] for p in data["providers"]]
        assert "hetzner" in provider_names

    def test_list_providers_shows_configuration_status(self):
        """Should show if provider is configured"""
        client = TestClient(app)
        response = client.get("/api/providers")

        assert response.status_code == 200
        data = response.json()

        # At least one provider should be present
        assert len(data["providers"]) > 0

        # Each provider should have required fields
        for provider in data["providers"]:
            assert "name" in provider
            assert "display_name" in provider
            assert "available" in provider
            assert "configured" in provider
            assert "status" in provider

    def test_list_providers_when_no_credentials(self):
        """Should still list providers even without credentials"""
        client = TestClient(app)

        # Clear any existing credentials
        from src.api.dependencies import get_orchestrator
        orch = get_orchestrator()
        orch.storage.config._config = {}

        response = client.get("/api/providers")

        assert response.status_code == 200
        data = response.json()

        # Providers should be listed but marked as unconfigured
        assert data["total"] > 0


class TestGetProviderDetailsEndpoint:
    """Tests for GET /api/providers/{name}"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def test_get_provider_returns_details(self):
        """Should return provider details"""
        client = TestClient(app)
        response = client.get("/api/providers/hetzner")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "hetzner"
        assert "display_name" in data
        assert "available" in data
        assert "configured" in data
        assert "status" in data
        assert "regions_count" in data
        assert "server_types_count" in data
        assert "capabilities" in data

    def test_get_provider_not_found(self):
        """Should return 404 for unknown provider"""
        client = TestClient(app)
        response = client.get("/api/providers/unknown")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_provider_includes_capabilities(self):
        """Should list provider capabilities"""
        client = TestClient(app)
        response = client.get("/api/providers/hetzner")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["capabilities"], list)
        # Hetzner should support server creation at minimum
        assert len(data["capabilities"]) > 0


class TestListRegionsEndpoint:
    """Tests for GET /api/providers/{name}/regions"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    @patch('src.providers.hetzner.HetznerProvider.get_available_locations')
    def test_list_regions_returns_regions(self, mock_get_locations):
        """Should return list of regions for provider"""
        mock_get_locations.return_value = [
            {
                "id": "nbg1",
                "name": "Nuremberg 1",
                "country": "DE",
                "city": "Nuremberg",
                "available": True
            },
            {
                "id": "fsn1",
                "name": "Falkenstein 1",
                "country": "DE",
                "city": "Falkenstein",
                "available": True
            }
        ]

        client = TestClient(app)
        response = client.get("/api/providers/hetzner/regions")

        assert response.status_code == 200
        data = response.json()

        assert data["provider"] == "hetzner"
        assert "regions" in data
        assert data["total"] == 2
        assert len(data["regions"]) == 2

        # Verify region structure
        region = data["regions"][0]
        assert "id" in region
        assert "name" in region
        assert "country" in region
        assert "available" in region

    def test_list_regions_provider_not_found(self):
        """Should return 404 for unknown provider"""
        client = TestClient(app)
        response = client.get("/api/providers/unknown/regions")

        assert response.status_code == 404

    @patch('src.providers.hetzner.HetznerProvider.get_available_locations')
    def test_list_regions_when_unconfigured(self, mock_get_locations):
        """Should return error when provider not configured"""
        mock_get_locations.side_effect = Exception("API token not configured")

        client = TestClient(app)
        response = client.get("/api/providers/hetzner/regions")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestListServerTypesEndpoint:
    """Tests for GET /api/providers/{name}/server-types"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    @patch('src.providers.hetzner.HetznerProvider.get_available_server_types')
    def test_list_server_types_returns_types(self, mock_get_types):
        """Should return list of server types"""
        mock_get_types.return_value = [
            {
                "id": "cx11",
                "name": "CX11",
                "description": "1 vCPU, 2 GB RAM, 20 GB SSD",
                "cores": 1,
                "memory": 2048,  # Memory in MB (2 GB)
                "disk": 20,
                "prices": [{"price_monthly": {"gross": "4.15"}}],
                "available": True
            },
            {
                "id": "cx21",
                "name": "CX21",
                "description": "2 vCPU, 4 GB RAM, 40 GB SSD",
                "cores": 2,
                "memory": 4096,  # Memory in MB (4 GB)
                "disk": 40,
                "prices": [{"price_monthly": {"gross": "7.90"}}],
                "available": True
            }
        ]

        client = TestClient(app)
        response = client.get("/api/providers/hetzner/server-types")

        assert response.status_code == 200
        data = response.json()

        assert data["provider"] == "hetzner"
        assert "server_types" in data
        assert data["total"] == 2
        assert len(data["server_types"]) == 2

        # Verify server type structure
        server_type = data["server_types"][0]
        assert server_type["id"] == "cx11"
        assert server_type["cores"] == 1
        assert server_type["memory_gb"] == 2.0
        assert server_type["disk_gb"] == 20

    def test_list_server_types_provider_not_found(self):
        """Should return 404 for unknown provider"""
        client = TestClient(app)
        response = client.get("/api/providers/unknown/server-types")

        assert response.status_code == 404

    @patch('src.providers.hetzner.HetznerProvider.get_available_server_types')
    def test_list_server_types_when_unconfigured(self, mock_get_types):
        """Should return error when provider not configured"""
        mock_get_types.side_effect = Exception("API token not configured")

        client = TestClient(app)
        response = client.get("/api/providers/hetzner/server-types")

        assert response.status_code == 500


class TestProviderIntegration:
    """Integration tests for provider endpoints"""

    def setup_method(self):
        """Reset orchestrator before each test"""
        reset_orchestrator()

    def test_workflow_discover_provider_and_regions(self):
        """Should be able to discover provider and list its regions"""
        client = TestClient(app)

        # Step 1: List providers
        response = client.get("/api/providers")
        assert response.status_code == 200
        providers = response.json()["providers"]

        # Step 2: Get details for first provider
        provider_name = providers[0]["name"]
        response = client.get(f"/api/providers/{provider_name}")
        assert response.status_code == 200
        details = response.json()
        assert details["name"] == provider_name

    @patch('src.providers.hetzner.HetznerProvider.get_available_locations')
    @patch('src.providers.hetzner.HetznerProvider.get_available_server_types')
    def test_workflow_get_all_provider_info(self, mock_types, mock_locations):
        """Should be able to get complete provider information"""
        # Mock data
        mock_locations.return_value = [
            {"id": "nbg1", "name": "Nuremberg", "country": "DE", "available": True}
        ]
        mock_types.return_value = [
            {
                "id": "cx11",
                "name": "CX11",
                "description": "Small",
                "cores": 1,
                "memory": 2048,  # MB
                "disk": 20,
                "prices": [],
                "available": True
            }
        ]

        client = TestClient(app)

        # Get provider details
        response = client.get("/api/providers/hetzner")
        assert response.status_code == 200

        # Get regions
        response = client.get("/api/providers/hetzner/regions")
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Get server types
        response = client.get("/api/providers/hetzner/server-types")
        assert response.status_code == 200
        assert response.json()["total"] == 1
