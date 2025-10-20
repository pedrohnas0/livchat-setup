"""
Unit tests for Job Executor Functions

Tests executor functions that handle different job types:
- Server operations (create, setup, delete)
- App operations (deploy, undeploy)

TDD Approach: RED → GREEN → REFACTOR
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.job_manager import Job, JobStatus
from src.orchestrator import Orchestrator


class TestServerExecutors:
    """Tests for server-related executor functions"""

    @pytest.fixture
    def orchestrator(self):
        """Mock Orchestrator"""
        orch = MagicMock(spec=Orchestrator)
        # NOTE: create_server and setup_server are SYNC, not async
        orch.create_server = MagicMock(return_value={
            "id": "srv-123",
            "name": "test-server",
            "ip": "192.168.1.1",
            "status": "running"
        })
        orch.setup_server = MagicMock(return_value={
            "success": True,
            "services": ["docker", "traefik", "portainer"]
        })
        # delete_server is async
        orch.delete_server = AsyncMock(return_value={
            "success": True,
            "deleted": True
        })
        return orch

    @pytest.fixture
    def create_job(self):
        """Create server job"""
        return Job(
            job_id="create-123",
            job_type="create_server",
            params={
                "name": "test-server",
                "server_type": "cx11",
                "location": "nbg1",
                "image": "debian-12"
            }
        )

    @pytest.fixture
    def setup_job(self):
        """Setup server job"""
        return Job(
            job_id="setup-123",
            job_type="setup_server",
            params={
                "server_name": "test-server",
                "ssl_email": "admin@example.com",
                "network_name": "livchat_network"
            }
        )

    @pytest.fixture
    def delete_job(self):
        """Delete server job"""
        return Job(
            job_id="delete-123",
            job_type="delete_server",
            params={
                "server_name": "test-server"
            }
        )

    @pytest.mark.asyncio
    async def test_execute_create_server(self, create_job, orchestrator):
        """Should create server and return result"""
        from src.job_executors.server_executors import execute_create_server

        result = await execute_create_server(create_job, orchestrator)

        # Should call orchestrator.create_server
        orchestrator.create_server.assert_called_once()
        call_args = orchestrator.create_server.call_args[1]
        assert call_args["name"] == "test-server"
        assert call_args["server_type"] == "cx11"
        # NOTE: Executor converts location to region
        assert call_args["region"] == "nbg1"

        # Should return result
        assert result is not None
        assert result["id"] == "srv-123"
        assert result["ip"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_execute_create_server_updates_progress(self, create_job, orchestrator):
        """Should update job progress during creation"""
        from src.job_executors.server_executors import execute_create_server

        # Track progress updates
        progress_updates = []
        original_update = create_job.update_progress

        def track_progress(progress, step):
            progress_updates.append((progress, step))
            original_update(progress, step)

        create_job.update_progress = track_progress

        await execute_create_server(create_job, orchestrator)

        # Should have multiple progress updates
        assert len(progress_updates) >= 2
        assert progress_updates[0][0] < 100  # First update < 100%
        assert progress_updates[-1][0] == 100  # Last update = 100%

    @pytest.mark.asyncio
    async def test_execute_setup_server(self, setup_job, orchestrator):
        """Should setup server infrastructure"""
        from src.job_executors.server_executors import execute_setup_server

        result = await execute_setup_server(setup_job, orchestrator)

        # Should call orchestrator.setup_server
        orchestrator.setup_server.assert_called_once()
        call_args = orchestrator.setup_server.call_args[1]
        assert call_args["server_name"] == "test-server"
        # NOTE: Executor passes config dict, not individual kwargs
        assert "config" in call_args
        assert call_args["config"]["ssl_email"] == "admin@example.com"
        assert call_args["config"]["network_name"] == "livchat_network"

        # Should return result
        assert result is not None
        assert result["success"] is True
        assert "services" in result

    @pytest.mark.asyncio
    async def test_execute_setup_server_updates_progress(self, setup_job, orchestrator):
        """Should update job progress during setup"""
        from src.job_executors.server_executors import execute_setup_server

        progress_updates = []

        def track_progress(progress, step):
            progress_updates.append((progress, step))

        setup_job.update_progress = track_progress

        await execute_setup_server(setup_job, orchestrator)

        # Should have progress updates
        assert len(progress_updates) >= 2

    @pytest.mark.asyncio
    async def test_execute_delete_server(self, delete_job, orchestrator):
        """Should delete server"""
        from src.job_executors.server_executors import execute_delete_server

        result = await execute_delete_server(delete_job, orchestrator)

        # Should call orchestrator.delete_server
        orchestrator.delete_server.assert_called_once()
        call_args = orchestrator.delete_server.call_args[1]
        # NOTE: Executor passes 'name', not 'server_name'
        assert call_args["name"] == "test-server"

        # Should return result
        assert result is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_delete_server_handles_errors(self, delete_job, orchestrator):
        """Should handle deletion errors gracefully"""
        from src.job_executors.server_executors import execute_delete_server

        # Make delete fail
        orchestrator.delete_server.side_effect = Exception("Server not found")

        with pytest.raises(Exception) as exc_info:
            await execute_delete_server(delete_job, orchestrator)

        assert "Server not found" in str(exc_info.value)


class TestAppExecutors:
    """Tests for app-related executor functions"""

    @pytest.fixture
    def orchestrator(self):
        """Mock Orchestrator"""
        orch = MagicMock(spec=Orchestrator)
        orch.deploy_app = AsyncMock(return_value={
            "success": True,
            "app_name": "n8n",
            "server": "test-server",
            "status": "running"
        })
        orch.undeploy_app = AsyncMock(return_value={
            "success": True,
            "removed": True
        })
        return orch

    @pytest.fixture
    def deploy_job(self):
        """Deploy app job"""
        return Job(
            job_id="deploy-123",
            job_type="deploy_app",
            params={
                "app_name": "n8n",
                "server_name": "test-server",
                "environment": {
                    "N8N_ENCRYPTION_KEY": "test-key"
                }
            }
        )

    @pytest.fixture
    def undeploy_job(self):
        """Undeploy app job"""
        return Job(
            job_id="undeploy-123",
            job_type="undeploy_app",
            params={
                "app_name": "n8n",
                "server_name": "test-server"
            }
        )

    @pytest.mark.asyncio
    async def test_execute_deploy_app(self, deploy_job, orchestrator):
        """Should deploy app to server"""
        from src.job_executors.app_executors import execute_deploy_app

        result = await execute_deploy_app(deploy_job, orchestrator)

        # Should call orchestrator.deploy_app
        orchestrator.deploy_app.assert_called_once()
        call_args = orchestrator.deploy_app.call_args[1]
        assert call_args["app_name"] == "n8n"
        assert call_args["server_name"] == "test-server"
        # NOTE: Executor passes config dict with environment
        assert "config" in call_args
        assert "environment" in call_args["config"]

        # Should return result
        assert result is not None
        assert result["success"] is True
        assert result["app_name"] == "n8n"

    @pytest.mark.asyncio
    async def test_execute_deploy_app_updates_progress(self, deploy_job, orchestrator):
        """Should update job progress during deployment"""
        from src.job_executors.app_executors import execute_deploy_app

        progress_updates = []

        def track_progress(progress, step):
            progress_updates.append((progress, step))

        deploy_job.update_progress = track_progress

        await execute_deploy_app(deploy_job, orchestrator)

        # Should have progress updates
        assert len(progress_updates) >= 2
        assert progress_updates[-1][0] == 100

    @pytest.mark.asyncio
    async def test_execute_undeploy_app(self, undeploy_job, orchestrator):
        """Should undeploy app from server"""
        from src.job_executors.app_executors import execute_undeploy_app

        result = await execute_undeploy_app(undeploy_job, orchestrator)

        # Should call orchestrator.undeploy_app
        orchestrator.undeploy_app.assert_called_once()
        call_args = orchestrator.undeploy_app.call_args[1]
        assert call_args["app_name"] == "n8n"
        assert call_args["server_name"] == "test-server"

        # Should return result
        assert result is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_deploy_app_handles_errors(self, deploy_job, orchestrator):
        """Should handle deployment errors gracefully"""
        from src.job_executors.app_executors import execute_deploy_app

        # Make deploy fail
        orchestrator.deploy_app.side_effect = Exception("Deployment failed")

        with pytest.raises(Exception) as exc_info:
            await execute_deploy_app(deploy_job, orchestrator)

        assert "Deployment failed" in str(exc_info.value)


class TestExecutorRegistry:
    """Tests for executor registry"""

    def test_registry_contains_server_executors(self):
        """Should have server executor functions registered"""
        from src.job_executors import EXECUTOR_REGISTRY

        assert "create_server" in EXECUTOR_REGISTRY
        assert "setup_server" in EXECUTOR_REGISTRY
        assert "delete_server" in EXECUTOR_REGISTRY

    def test_registry_contains_app_executors(self):
        """Should have app executor functions registered"""
        from src.job_executors import EXECUTOR_REGISTRY

        assert "deploy_app" in EXECUTOR_REGISTRY
        assert "undeploy_app" in EXECUTOR_REGISTRY

    def test_registry_executors_are_callable(self):
        """All registered executors should be callable"""
        from src.job_executors import EXECUTOR_REGISTRY

        for job_type, executor_func in EXECUTOR_REGISTRY.items():
            assert callable(executor_func), f"{job_type} executor is not callable"
