"""
Integration tests for State API

Tests the /api/state endpoints with real storage (temp filesystem)
and API client interactions.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from src.orchestrator import Orchestrator
from src.storage import StorageManager
from src.api.server import app
from src.api.dependencies import get_orchestrator


class TestStateAPIIntegration:
    """Integration tests for State API endpoints"""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary directory for storage"""
        temp_dir = tempfile.mkdtemp(prefix="livchat_state_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def orchestrator(self, temp_storage_dir):
        """Create Orchestrator with temp storage"""
        orch = Orchestrator(config_dir=Path(temp_storage_dir))

        # Initialize state with test data
        orch.storage.state._state = {
            "servers": {
                "prod": {
                    "ip": "1.2.3.4",
                    "dns_config": {
                        "zone_name": "example.com",
                        "subdomain": "app"
                    },
                    "status": "running"
                },
                "dev": {
                    "ip": "5.6.7.8"
                }
            },
            "settings": {
                "admin_email": "admin@example.com",
                "default_timezone": "America/Sao_Paulo"
            }
        }
        orch.storage.state._loaded = True
        orch.storage.state.save()

        return orch

    @pytest.fixture
    def client(self, orchestrator):
        """Create TestClient with dependency override"""
        # Override dependency
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator

        client = TestClient(app)
        yield client

        # Cleanup
        app.dependency_overrides.clear()

    def test_get_entire_state(self, client):
        """GET /api/state should return entire state when no path"""
        response = client.get("/api/state")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "get"
        assert "servers" in data["value"]
        assert "settings" in data["value"]

    def test_get_simple_path(self, client):
        """GET /api/state?path=servers.prod.ip should return IP"""
        response = client.get("/api/state?path=servers.prod.ip")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "get"
        assert data["path"] == "servers.prod.ip"
        assert data["value"] == "1.2.3.4"

    def test_get_nested_object(self, client):
        """GET /api/state?path=servers.prod.dns_config should return DNS object"""
        response = client.get("/api/state?path=servers.prod.dns_config")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["value"]["zone_name"] == "example.com"
        assert data["value"]["subdomain"] == "app"

    def test_get_nonexistent_path(self, client):
        """GET /api/state?path=nonexistent should return 404"""
        response = client.get("/api/state?path=nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_servers_collection(self, client):
        """GET /api/state?path=servers should return all servers"""
        response = client.get("/api/state?path=servers")

        assert response.status_code == 200
        data = response.json()
        assert "prod" in data["value"]
        assert "dev" in data["value"]

    def test_set_simple_value(self, client):
        """PUT /api/state should set value at path"""
        response = client.put(
            "/api/state",
            json={"path": "servers.prod.ip", "value": "10.20.30.40"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "set"
        assert data["path"] == "servers.prod.ip"
        assert data["value"] == "10.20.30.40"

        # Verify it was saved
        get_response = client.get("/api/state?path=servers.prod.ip")
        assert get_response.json()["value"] == "10.20.30.40"

    def test_set_creates_new_path(self, client):
        """PUT /api/state should create intermediate dicts"""
        response = client.put(
            "/api/state",
            json={"path": "servers.staging.ip", "value": "192.168.1.1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify new path exists
        get_response = client.get("/api/state?path=servers.staging.ip")
        assert get_response.json()["value"] == "192.168.1.1"

    def test_set_object_value(self, client):
        """PUT /api/state should handle object values"""
        new_dns = {"zone_name": "newdomain.com", "subdomain": "api"}

        response = client.put(
            "/api/state",
            json={"path": "servers.prod.dns_config", "value": new_dns}
        )

        assert response.status_code == 200

        # Verify object was set
        get_response = client.get("/api/state?path=servers.prod.dns_config")
        assert get_response.json()["value"] == new_dns

    def test_set_array_value(self, client):
        """PUT /api/state should handle array values"""
        apps = ["traefik", "portainer", "n8n"]

        response = client.put(
            "/api/state",
            json={"path": "servers.prod.applications", "value": apps}
        )

        assert response.status_code == 200

        # Verify array was set
        get_response = client.get("/api/state?path=servers.prod.applications")
        assert get_response.json()["value"] == apps

    def test_set_numeric_value(self, client):
        """PUT /api/state should handle numeric values"""
        response = client.put(
            "/api/state",
            json={"path": "servers.prod.port", "value": 8080}
        )

        assert response.status_code == 200

        # Verify number was set
        get_response = client.get("/api/state?path=servers.prod.port")
        assert get_response.json()["value"] == 8080

    def test_set_boolean_value(self, client):
        """PUT /api/state should handle boolean values"""
        response = client.put(
            "/api/state",
            json={"path": "servers.prod.enabled", "value": True}
        )

        assert response.status_code == 200

        # Verify boolean was set
        get_response = client.get("/api/state?path=servers.prod.enabled")
        assert get_response.json()["value"] is True

    def test_set_null_value(self, client):
        """PUT /api/state should handle null values"""
        response = client.put(
            "/api/state",
            json={"path": "servers.prod.metadata", "value": None}
        )

        assert response.status_code == 200

        # Verify null was set
        get_response = client.get("/api/state?path=servers.prod.metadata")
        assert get_response.json()["value"] is None

    def test_delete_simple_key(self, client):
        """DELETE /api/state?path=... should delete key"""
        response = client.delete("/api/state?path=settings.admin_email")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "delete"

        # Verify key was deleted
        get_response = client.get("/api/state?path=settings.admin_email")
        assert get_response.status_code == 404

        # But other keys remain
        get_response = client.get("/api/state?path=settings.default_timezone")
        assert get_response.status_code == 200

    def test_delete_nested_key(self, client):
        """DELETE /api/state should delete nested keys"""
        response = client.delete("/api/state?path=servers.prod.dns_config.subdomain")

        assert response.status_code == 200

        # Verify subdomain was deleted
        get_response = client.get("/api/state?path=servers.prod.dns_config")
        dns_config = get_response.json()["value"]
        assert "subdomain" not in dns_config
        assert "zone_name" in dns_config  # Other keys remain

    def test_delete_nonexistent_key(self, client):
        """DELETE /api/state should return 404 for nonexistent key"""
        response = client.delete("/api/state?path=servers.nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_root_keys(self, client):
        """GET /api/state/keys should list root keys"""
        response = client.get("/api/state/keys")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "list"
        assert set(data["keys"]) == {"servers", "settings"}

    def test_list_nested_keys(self, client):
        """GET /api/state/keys?path=servers should list server names"""
        response = client.get("/api/state/keys?path=servers")

        assert response.status_code == 200
        data = response.json()
        assert set(data["keys"]) == {"prod", "dev"}

    def test_list_deep_nested_keys(self, client):
        """GET /api/state/keys?path=servers.prod should list server fields"""
        response = client.get("/api/state/keys?path=servers.prod")

        assert response.status_code == 200
        data = response.json()
        assert "ip" in data["keys"]
        assert "dns_config" in data["keys"]
        assert "status" in data["keys"]

    def test_list_non_dict_value(self, client):
        """GET /api/state/keys?path=servers.prod.ip should return empty list"""
        response = client.get("/api/state/keys?path=servers.prod.ip")

        assert response.status_code == 200
        data = response.json()
        assert data["keys"] == []

    def test_list_nonexistent_path(self, client):
        """GET /api/state/keys?path=nonexistent should return 404"""
        response = client.get("/api/state/keys?path=nonexistent")

        assert response.status_code == 404

    def test_persistence_across_operations(self, client, temp_storage_dir):
        """State changes should persist to disk"""
        # Set a value
        client.put(
            "/api/state",
            json={"path": "test.key", "value": "test_value"}
        )

        # Verify state file was written
        state_file = Path(temp_storage_dir) / "state.json"
        assert state_file.exists()

        # Read file content
        import json
        with open(state_file, 'r') as f:
            state_data = json.load(f)

        assert state_data["test"]["key"] == "test_value"

    def test_complex_workflow(self, client):
        """Test a realistic workflow of operations"""
        # 1. List root keys
        response = client.get("/api/state/keys")
        assert "servers" in response.json()["keys"]

        # 2. Get all servers
        response = client.get("/api/state?path=servers")
        servers = response.json()["value"]
        assert "prod" in servers

        # 3. Add new server
        client.put(
            "/api/state",
            json={
                "path": "servers.staging.ip",
                "value": "192.168.1.100"
            }
        )

        # 4. Set DNS config for new server
        client.put(
            "/api/state",
            json={
                "path": "servers.staging.dns_config",
                "value": {"zone_name": "staging.example.com"}
            }
        )

        # 5. List servers again - should have 3 now
        response = client.get("/api/state/keys?path=servers")
        assert set(response.json()["keys"]) == {"prod", "dev", "staging"}

        # 6. Get new server details
        response = client.get("/api/state?path=servers.staging")
        staging = response.json()["value"]
        assert staging["ip"] == "192.168.1.100"
        assert staging["dns_config"]["zone_name"] == "staging.example.com"

        # 7. Delete staging server
        client.delete("/api/state?path=servers.staging")

        # 8. Verify deleted
        response = client.get("/api/state?path=servers.staging")
        assert response.status_code == 404
