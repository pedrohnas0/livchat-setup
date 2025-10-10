"""
Unit tests for server routes

Following TDD: Write tests FIRST

Tests for:
- POST /api/servers - Create server (async job)
- GET /api/servers - List servers
- GET /api/servers/{name} - Get server details
- DELETE /api/servers/{name} - Delete server (async job)
- POST /api/servers/{name}/setup - Setup server (async job)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.routes.servers import router
from src.api.dependencies import reset_job_manager, reset_orchestrator
from src.job_manager import JobStatus
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestCreateServerEndpoint:
    """Test POST /api/servers endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        # Clear jobs and servers
        from src.api.dependencies import get_job_manager, get_orchestrator
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()
        orchestrator = get_orchestrator()
        orchestrator.storage.state._state["servers"] = {}
        orchestrator.storage.state.save()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_create_server_returns_202(self):
        """Should return 202 Accepted (job created)"""
        # Arrange
        request_data = {
            "name": "test-server",
            "server_type": "cx21",
            "region": "nbg1"
        }

        # Act
        response = client.post("/api/servers", json=request_data)

        # Assert
        assert response.status_code == 202

    def test_create_server_returns_job_id(self):
        """Should return job_id for tracking"""
        # Arrange
        request_data = {
            "name": "test-server",
            "server_type": "cx21",
            "region": "nbg1"
        }

        # Act
        response = client.post("/api/servers", json=request_data)

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "message" in data
        assert "server_name" in data
        assert data["server_name"] == "test-server"

    def test_create_server_creates_job(self):
        """Should create a job in JobManager"""
        # Arrange
        request_data = {
            "name": "test-server",
            "server_type": "cx21",
            "region": "nbg1"
        }

        # Act
        response = client.post("/api/servers", json=request_data)

        # Assert
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        data = response.json()
        job = manager.get_job(data["job_id"])

        assert job is not None
        assert job.job_type == "create_server"
        assert job.params["name"] == "test-server"
        assert job.params["server_type"] == "cx21"
        assert job.params["region"] == "nbg1"
        assert job.status == JobStatus.PENDING

    def test_create_server_validates_name(self):
        """Should validate server name"""
        # Arrange - empty name
        request_data = {
            "name": "",
            "server_type": "cx21",
            "region": "nbg1"
        }

        # Act
        response = client.post("/api/servers", json=request_data)

        # Assert
        assert response.status_code == 422  # Validation error

    def test_create_server_returns_json(self):
        """Should return JSON response"""
        # Arrange
        request_data = {
            "name": "test-server",
            "server_type": "cx21",
            "region": "nbg1"
        }

        # Act
        response = client.post("/api/servers", json=request_data)

        # Assert
        assert "application/json" in response.headers["content-type"]


class TestListServersEndpoint:
    """Test GET /api/servers endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_list_servers_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.get("/api/servers")

        # Assert
        assert response.status_code == 200

    def test_list_servers_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.get("/api/servers")

        # Assert
        assert "application/json" in response.headers["content-type"]

    def test_list_servers_returns_list_structure(self):
        """Should return servers list structure"""
        # Act
        response = client.get("/api/servers")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "servers" in data
        assert "total" in data
        assert isinstance(data["servers"], list)

    def test_list_servers_empty(self):
        """Should return empty list when no servers"""
        # Act
        response = client.get("/api/servers")

        # Assert
        data = response.json()
        assert data["servers"] == []
        assert data["total"] == 0

    def test_list_servers_with_servers(self):
        """Should return servers from state"""
        # Arrange - add server to state
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server-1", {
            "provider": "hetzner",
            "server_type": "cx21",
            "region": "nbg1",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers")

        # Assert
        data = response.json()
        assert len(data["servers"]) == 1
        assert data["total"] == 1
        assert data["servers"][0]["name"] == "test-server-1"


class TestGetServerEndpoint:
    """Test GET /api/servers/{name} endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_get_server_returns_200(self):
        """Should return 200 for existing server"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "server_type": "cx21",
            "region": "nbg1",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server")

        # Assert
        assert response.status_code == 200

    def test_get_server_returns_404_for_nonexistent(self):
        """Should return 404 for non-existent server"""
        # Act
        response = client.get("/api/servers/nonexistent")

        # Assert
        assert response.status_code == 404

    def test_get_server_returns_server_info(self):
        """Should return complete server information"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "server_type": "cx21",
            "region": "nbg1",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server")

        # Assert
        data = response.json()
        assert data["name"] == "test-server"
        assert data["provider"] == "hetzner"
        assert data["server_type"] == "cx21"
        assert data["region"] == "nbg1"
        assert data["ip_address"] == "1.2.3.4"
        assert data["status"] == "running"

    def test_get_server_returns_json(self):
        """Should return JSON response"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server")

        # Assert
        assert "application/json" in response.headers["content-type"]


class TestDeleteServerEndpoint:
    """Test DELETE /api/servers/{name} endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_delete_server_returns_202(self):
        """Should return 202 Accepted (job created)"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.delete("/api/servers/test-server")

        # Assert
        assert response.status_code == 202

    def test_delete_server_returns_404_for_nonexistent(self):
        """Should return 404 for non-existent server"""
        # Act
        response = client.delete("/api/servers/nonexistent")

        # Assert
        assert response.status_code == 404

    def test_delete_server_returns_job_id(self):
        """Should return job_id for tracking"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.delete("/api/servers/test-server")

        # Assert
        data = response.json()
        assert "job_id" in data
        assert "message" in data
        assert "server_name" in data
        assert data["server_name"] == "test-server"

    def test_delete_server_creates_job(self):
        """Should create a job in JobManager"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.delete("/api/servers/test-server")

        # Assert
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        data = response.json()
        job = manager.get_job(data["job_id"])

        assert job is not None
        assert job.job_type == "delete_server"
        assert job.params["name"] == "test-server"
        assert job.status == JobStatus.PENDING


class TestSetupServerEndpoint:
    """Test POST /api/servers/{name}/setup endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_setup_server_returns_202(self):
        """Should return 202 Accepted (job created)"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # Act
        response = client.post("/api/servers/test-server/setup")

        # Assert
        assert response.status_code == 202

    def test_setup_server_returns_404_for_nonexistent(self):
        """Should return 404 for non-existent server"""
        # Act
        response = client.post("/api/servers/nonexistent/setup")

        # Assert
        assert response.status_code == 404

    def test_setup_server_returns_job_id(self):
        """Should return job_id for tracking"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # Act
        response = client.post("/api/servers/test-server/setup")

        # Assert
        data = response.json()
        assert "job_id" in data
        assert "message" in data
        assert "server_name" in data
        assert data["server_name"] == "test-server"

    def test_setup_server_creates_job(self):
        """Should create a job in JobManager"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # Act
        response = client.post("/api/servers/test-server/setup")

        # Assert
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        data = response.json()
        job = manager.get_job(data["job_id"])

        assert job is not None
        assert job.job_type == "setup_server"
        assert job.params["name"] == "test-server"
        assert job.status == JobStatus.PENDING

    def test_setup_server_accepts_options(self):
        """Should accept setup options"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        setup_options = {
            "install_docker": True,
            "init_swarm": True,
            "deploy_traefik": False,
            "deploy_portainer": True
        }

        # Act
        response = client.post("/api/servers/test-server/setup", json=setup_options)

        # Assert
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        data = response.json()
        job = manager.get_job(data["job_id"])

        assert job.params["install_docker"] is True
        assert job.params["deploy_traefik"] is False


class TestServerRoutesIntegration:
    """Integration tests for server routes"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager, get_orchestrator
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()
        # Clear servers from state
        orchestrator = get_orchestrator()
        orchestrator.storage.state._state["servers"] = {}
        orchestrator.storage.state.save()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_server_lifecycle_via_api(self):
        """Test complete server lifecycle via API"""
        # Create server (async)
        response = client.post("/api/servers", json={
            "name": "lifecycle-test",
            "server_type": "cx21",
            "region": "nbg1"
        })
        assert response.status_code == 202
        create_job_id = response.json()["job_id"]

        # Simulate server created by adding to state
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("lifecycle-test", {
            "provider": "hetzner",
            "server_type": "cx21",
            "region": "nbg1",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # List servers
        response = client.get("/api/servers")
        assert response.status_code == 200
        assert len(response.json()["servers"]) == 1

        # Get server details
        response = client.get("/api/servers/lifecycle-test")
        assert response.status_code == 200
        assert response.json()["name"] == "lifecycle-test"

        # Setup server (async)
        response = client.post("/api/servers/lifecycle-test/setup")
        assert response.status_code == 202

        # Delete server (async)
        response = client.delete("/api/servers/lifecycle-test")
        assert response.status_code == 202

    def test_all_routes_return_valid_json(self):
        """All routes should return valid JSON"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        routes = [
            ("POST", "/api/servers", {"name": "new-server", "server_type": "cx21", "region": "nbg1"}),
            ("GET", "/api/servers", None),
            ("GET", "/api/servers/test-server", None),
            ("POST", "/api/servers/test-server/setup", None),
            ("DELETE", "/api/servers/test-server", None),
        ]

        # Act & Assert
        for method, path, json_data in routes:
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json=json_data)
            else:
                response = client.delete(path)

            # Should return JSON
            assert "application/json" in response.headers["content-type"]
