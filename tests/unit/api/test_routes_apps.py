"""
Unit tests for application routes

Following TDD: Write tests FIRST

Tests for:
- GET /api/apps - List available apps
- GET /api/apps/{name} - Get app details
- POST /api/apps/{name}/deploy - Deploy app (async job)
- POST /api/apps/{name}/undeploy - Undeploy app (async job)
- GET /api/servers/{server_name}/apps - List deployed apps
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.routes.apps import router
from src.api.dependencies import reset_job_manager, reset_orchestrator
from src.job_manager import JobStatus
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestListAppsEndpoint:
    """Test GET /api/apps endpoint"""

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

    def test_list_apps_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.get("/api/apps")

        # Assert
        assert response.status_code == 200

    def test_list_apps_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.get("/api/apps")

        # Assert
        assert "application/json" in response.headers["content-type"]

    def test_list_apps_returns_list_structure(self):
        """Should return apps list structure"""
        # Act
        response = client.get("/api/apps")

        # Assert
        data = response.json()
        assert "apps" in data
        assert "total" in data
        assert isinstance(data["apps"], list)

    @patch('src.api.routes.apps.get_app_registry')
    def test_list_apps_includes_app_info(self, mock_registry):
        """Should include app information from registry"""
        # Arrange
        mock_registry.return_value.list_apps.return_value = [
            {
                "name": "n8n",
                "version": "latest",
                "description": "Workflow automation",
                "category": "applications",
                "dependencies": ["postgres", "redis"],
                "deploy_method": "portainer"
            }
        ]

        # Act
        response = client.get("/api/apps")

        # Assert
        data = response.json()
        assert len(data["apps"]) == 1
        assert data["total"] == 1
        assert data["apps"][0]["name"] == "n8n"
        assert data["apps"][0]["dependencies"] == ["postgres", "redis"]


class TestGetAppDetailsEndpoint:
    """Test GET /api/apps/{name} endpoint"""

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

    @patch('src.api.routes.apps.get_app_registry')
    def test_get_app_returns_200(self, mock_registry):
        """Should return 200 for existing app"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {
            "name": "n8n",
            "version": "latest",
            "description": "Workflow automation",
            "category": "applications",
            "dependencies": ["postgres"],
            "deploy_method": "portainer"
        }

        # Act
        response = client.get("/api/apps/n8n")

        # Assert
        assert response.status_code == 200

    @patch('src.api.routes.apps.get_app_registry')
    def test_get_app_returns_404_for_nonexistent(self, mock_registry):
        """Should return 404 for non-existent app"""
        # Arrange
        mock_registry.return_value.get_app.return_value = None

        # Act
        response = client.get("/api/apps/nonexistent")

        # Assert
        assert response.status_code == 404

    @patch('src.api.routes.apps.get_app_registry')
    def test_get_app_returns_app_info(self, mock_registry):
        """Should return complete app information"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {
            "name": "postgres",
            "version": "14",
            "description": "PostgreSQL database",
            "category": "databases",
            "dependencies": [],
            "deploy_method": "portainer"
        }

        # Act
        response = client.get("/api/apps/postgres")

        # Assert
        data = response.json()
        assert data["name"] == "postgres"
        assert data["version"] == "14"
        assert data["category"] == "databases"
        assert data["dependencies"] == []


class TestDeployAppEndpoint:
    """Test POST /api/apps/{name}/deploy endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager, get_orchestrator
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()
        orchestrator = get_orchestrator()
        orchestrator.storage.state._state["servers"] = {}
        orchestrator.storage.state._state["deployments"] = []
        orchestrator.storage.state.save()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    @patch('src.api.routes.apps.get_app_registry')
    def test_deploy_app_returns_202(self, mock_registry):
        """Should return 202 Accepted (job created)"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {"name": "n8n"}
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "ip_address": "1.2.3.4",
            "status": "running"
        })

        # Act
        response = client.post("/api/apps/n8n/deploy", json={
            "server_name": "test-server"
        })

        # Assert
        assert response.status_code == 202

    @patch('src.api.routes.apps.get_app_registry')
    def test_deploy_app_returns_404_for_nonexistent_app(self, mock_registry):
        """Should return 404 for non-existent app"""
        # Arrange
        mock_registry.return_value.get_app.return_value = None

        # Act
        response = client.post("/api/apps/nonexistent/deploy", json={
            "server_name": "test-server"
        })

        # Assert
        assert response.status_code == 404

    @patch('src.api.routes.apps.get_app_registry')
    def test_deploy_app_returns_404_for_nonexistent_server(self, mock_registry):
        """Should return 404 for non-existent server"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {"name": "n8n"}

        # Act
        response = client.post("/api/apps/n8n/deploy", json={
            "server_name": "nonexistent-server"
        })

        # Assert
        assert response.status_code == 404

    @patch('src.api.routes.apps.get_app_registry')
    def test_deploy_app_returns_job_id(self, mock_registry):
        """Should return job_id for tracking"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {"name": "n8n"}
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.post("/api/apps/n8n/deploy", json={
            "server_name": "test-server",
            "domain": "n8n.example.com"
        })

        # Assert
        data = response.json()
        assert "job_id" in data
        assert "message" in data
        assert data["app_name"] == "n8n"
        assert data["server_name"] == "test-server"

    @patch('src.api.routes.apps.get_app_registry')
    def test_deploy_app_creates_job(self, mock_registry):
        """Should create a job in JobManager"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {"name": "n8n"}
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.post("/api/apps/n8n/deploy", json={
            "server_name": "test-server",
            "environment": {"KEY": "value"}
        })

        # Assert
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        data = response.json()
        job = manager.get_job(data["job_id"])

        assert job is not None
        assert job.job_type == "deploy_app"
        assert job.params["app_name"] == "n8n"
        assert job.params["server_name"] == "test-server"
        assert job.params["environment"] == {"KEY": "value"}
        assert job.status == JobStatus.PENDING


class TestUndeployAppEndpoint:
    """Test POST /api/apps/{name}/undeploy endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager, get_orchestrator
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()
        orchestrator = get_orchestrator()
        orchestrator.storage.state._state["servers"] = {}
        orchestrator.storage.state._state["deployments"] = []
        orchestrator.storage.state.save()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_undeploy_app_returns_202(self):
        """Should return 202 Accepted (job created)"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.post("/api/apps/n8n/undeploy", json={
            "server_name": "test-server"
        })

        # Assert
        assert response.status_code == 202

    def test_undeploy_app_returns_404_for_nonexistent_server(self):
        """Should return 404 for non-existent server"""
        # Act
        response = client.post("/api/apps/n8n/undeploy", json={
            "server_name": "nonexistent-server"
        })

        # Assert
        assert response.status_code == 404

    def test_undeploy_app_returns_job_id(self):
        """Should return job_id for tracking"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.post("/api/apps/n8n/undeploy", json={
            "server_name": "test-server"
        })

        # Assert
        data = response.json()
        assert "job_id" in data
        assert "message" in data
        assert data["app_name"] == "n8n"
        assert data["server_name"] == "test-server"

    def test_undeploy_app_creates_job(self):
        """Should create a job in JobManager"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.post("/api/apps/chatwoot/undeploy", json={
            "server_name": "test-server"
        })

        # Assert
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        data = response.json()
        job = manager.get_job(data["job_id"])

        assert job is not None
        assert job.job_type == "undeploy_app"
        assert job.params["app_name"] == "chatwoot"
        assert job.params["server_name"] == "test-server"
        assert job.status == JobStatus.PENDING


class TestListDeployedAppsEndpoint:
    """Test GET /api/servers/{server_name}/apps endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager, get_orchestrator
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()
        orchestrator = get_orchestrator()
        orchestrator.storage.state._state["servers"] = {}
        orchestrator.storage.state._state["deployments"] = []
        orchestrator.storage.state.save()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_list_deployed_apps_returns_200(self):
        """Should return 200 OK"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server/apps")

        # Assert
        assert response.status_code == 200

    def test_list_deployed_apps_returns_404_for_nonexistent_server(self):
        """Should return 404 for non-existent server"""
        # Act
        response = client.get("/api/servers/nonexistent/apps")

        # Assert
        assert response.status_code == 404

    def test_list_deployed_apps_returns_list_structure(self):
        """Should return apps list structure"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server/apps")

        # Assert
        data = response.json()
        assert "apps" in data
        assert "server_name" in data
        assert "total" in data
        assert data["server_name"] == "test-server"
        assert isinstance(data["apps"], list)

    def test_list_deployed_apps_empty(self):
        """Should return empty list when no apps deployed"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server/apps")

        # Assert
        data = response.json()
        assert data["apps"] == []
        assert data["total"] == 0

    def test_list_deployed_apps_with_deployments(self):
        """Should return deployed apps from state"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })
        orchestrator.storage.state.add_deployment({
            "app_name": "n8n",
            "server": "test-server",
            "domain": "n8n.example.com",
            "status": "running"
        })

        # Act
        response = client.get("/api/servers/test-server/apps")

        # Assert
        data = response.json()
        assert len(data["apps"]) == 1
        assert data["total"] == 1
        assert data["apps"][0]["app_name"] == "n8n"
        assert data["apps"][0]["server_name"] == "test-server"


class TestAppRoutesIntegration:
    """Integration tests for app routes"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        from src.api.dependencies import get_job_manager, get_orchestrator
        manager = get_job_manager()
        manager.jobs.clear()
        manager.save_to_storage()
        orchestrator = get_orchestrator()
        orchestrator.storage.state._state["servers"] = {}
        orchestrator.storage.state._state["deployments"] = []
        orchestrator.storage.state.save()

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    @patch('src.api.routes.apps.get_app_registry')
    def test_app_deployment_lifecycle_via_api(self, mock_registry):
        """Test complete app deployment lifecycle via API"""
        # Arrange
        mock_registry.return_value.get_app.return_value = {"name": "n8n"}
        mock_registry.return_value.list_apps.return_value = [{"name": "n8n"}]

        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        # List available apps
        response = client.get("/api/apps")
        assert response.status_code == 200

        # Get app details
        response = client.get("/api/apps/n8n")
        assert response.status_code == 200

        # Deploy app (async)
        response = client.post("/api/apps/n8n/deploy", json={
            "server_name": "test-server"
        })
        assert response.status_code == 202
        deploy_job_id = response.json()["job_id"]

        # Simulate deployment by adding to state
        orchestrator.storage.state.add_deployment({
            "app_name": "n8n",
            "server": "test-server",
            "status": "running"
        })

        # List deployed apps
        response = client.get("/api/servers/test-server/apps")
        assert response.status_code == 200
        assert len(response.json()["apps"]) == 1

        # Undeploy app (async)
        response = client.post("/api/apps/n8n/undeploy", json={
            "server_name": "test-server"
        })
        assert response.status_code == 202

    def test_all_routes_return_valid_json(self):
        """All routes should return valid JSON"""
        # Arrange
        from src.api.dependencies import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.storage.state.add_server("test-server", {
            "provider": "hetzner",
            "status": "running"
        })

        with patch('src.api.routes.apps.get_app_registry') as mock_registry:
            mock_registry.return_value.get_app.return_value = {"name": "n8n"}
            mock_registry.return_value.list_apps.return_value = []

            routes = [
                ("GET", "/api/apps", None),
                ("GET", "/api/apps/n8n", None),
                ("POST", "/api/apps/n8n/deploy", {"server_name": "test-server"}),
                ("POST", "/api/apps/n8n/undeploy", {"server_name": "test-server"}),
                ("GET", "/api/servers/test-server/apps", None),
            ]

            # Act & Assert
            for method, path, json_data in routes:
                if method == "GET":
                    response = client.get(path)
                else:
                    response = client.post(path, json=json_data)

                # Should return JSON
                assert "application/json" in response.headers["content-type"]
