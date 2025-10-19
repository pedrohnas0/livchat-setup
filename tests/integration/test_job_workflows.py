"""
Integration tests for Job workflows

Tests complete job lifecycle and interaction between JobManager,
Orchestrator, and storage components using the REAL API.

These tests use local resources (temp filesystem) and mocked external APIs.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.job_manager import JobManager, Job, JobStatus
from src.orchestrator_old import Orchestrator
from src.storage import StorageManager
from src.api.server import app
from src.api.dependencies import reset_orchestrator, reset_job_manager


class TestJobManagerPersistence:
    """Integration tests for JobManager persistence"""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary directory for storage"""
        temp_dir = tempfile.mkdtemp(prefix="livchat_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def storage_manager(self, temp_storage_dir):
        """Create StorageManager with temp directory"""
        return StorageManager(config_dir=Path(temp_storage_dir))

    @pytest.fixture
    def job_manager(self, storage_manager):
        """Create JobManager instance"""
        return JobManager(storage=storage_manager)

    def test_create_job_persists_to_storage(self, job_manager):
        """Should persist job to storage when created"""
        # Create job
        job = job_manager.create_job(
            job_type="test_job",
            params={"test": "data"}
        )

        assert job.job_id is not None
        assert job.status == JobStatus.PENDING

        # Jobs are saved immediately
        job_manager.save_to_storage()

        # Get job back
        loaded_job = job_manager.get_job(job.job_id)
        assert loaded_job is not None
        assert loaded_job.job_type == "test_job"
        assert loaded_job.params == {"test": "data"}

    def test_job_lifecycle(self, job_manager):
        """Should handle complete job lifecycle"""
        # Create job
        job = job_manager.create_job(
            job_type="deploy_server",
            params={"server_name": "test-server"}
        )

        # Start job
        job.mark_started()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

        # Update progress
        job.update_progress(25, "Creating server...")
        assert job.progress == 25

        job.update_progress(75, "Installing Docker...")
        assert job.progress == 75

        # Complete job
        result = {"server_id": "srv-123"}
        job.mark_completed(result=result)

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100
        assert job.result == result
        assert job.completed_at is not None

    def test_job_error_handling(self, job_manager):
        """Should properly handle job errors"""
        job = job_manager.create_job(
            job_type="test_job",
            params={}
        )

        # Start and fail
        job.mark_started()
        error_msg = "Something went wrong"
        job.mark_completed(error=error_msg)

        assert job.status == JobStatus.FAILED
        assert job.error == error_msg

    def test_list_jobs_with_filters(self, job_manager):
        """Should filter jobs by status and type"""
        # Create jobs
        job1 = job_manager.create_job("deploy_server", {})
        job2 = job_manager.create_job("deploy_app", {})
        job3 = job_manager.create_job("deploy_server", {})

        job1.mark_started()
        job2.mark_completed()

        # Test filters
        all_jobs = job_manager.list_jobs()
        assert len(all_jobs) == 3

        running_jobs = job_manager.list_jobs(status=JobStatus.RUNNING)
        assert len(running_jobs) == 1

        server_jobs = job_manager.list_jobs(job_type="deploy_server")
        assert len(server_jobs) == 2


class TestAPIIntegrationWorkflows:
    """Integration tests using FastAPI TestClient"""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset singletons before each test"""
        reset_orchestrator()
        reset_job_manager()
        yield
        reset_orchestrator()
        reset_job_manager()

    def test_complete_server_creation_workflow_via_api(self):
        """Should handle complete server creation via API"""
        client = TestClient(app)

        # Step 1: Initialize system
        response = client.get("/health")
        assert response.status_code == 200

        # Step 2: Set Hetzner API token
        response = client.put(
            "/api/config/providers.hetzner.token",
            json={"value": "test-token"}
        )
        assert response.status_code == 200

        # Step 3: Create server (job-based)
        with patch('src.providers.hetzner.HetznerProvider.create_server') as mock_create:
            mock_create.return_value = {
                "id": 123,
                "name": "test-server",
                "public_net": {"ipv4": {"ip": "192.168.1.1"}},
                "status": "running"
            }

            response = client.post(
                "/api/servers",
                json={
                    "name": "test-server",
                    "server_type": "cx11",
                    "location": "nbg1"
                }
            )
            assert response.status_code == 202
            job_id = response.json()["job_id"]

        # Step 4: Check job status
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["job_type"] == "create_server"

        # Step 5: List all jobs
        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert len(response.json()["jobs"]) >= 1

    def test_app_deployment_workflow_via_api(self):
        """Should handle app deployment via API"""
        client = TestClient(app)

        # Initialize (check health)
        client.get("/health")

        # Create server first (manually add to state for testing)
        from src.api.dependencies import get_orchestrator
        orch = get_orchestrator()
        orch.storage.state.add_server("test-server", {
            "id": "srv-123",
            "name": "test-server",
            "ip": "192.168.1.1"
        })

        # Deploy app
        with patch('src.app_registry.AppRegistry.get_app') as mock_get_app:
            mock_get_app.return_value = {
                "name": "n8n",
                "version": "latest"
            }

            response = client.post(
                "/api/apps/n8n/deploy",
                json={
                    "server_name": "test-server",
                    "domain": "n8n.example.com"
                }
            )
            assert response.status_code == 202
            job_id = response.json()["job_id"]

        # Check job
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["job_type"] == "deploy_app"

    def test_configuration_workflow_via_api(self):
        """Should handle configuration updates via API"""
        client = TestClient(app)

        # Initialize (check health)
        client.get("/health")

        # Set config
        response = client.put(
            "/api/config/providers.hetzner.token",
            json={"value": "test-token"}
        )
        assert response.status_code == 200

        # Get config
        response = client.get("/api/config/providers.hetzner.token")
        assert response.status_code == 200
        assert response.json()["value"] == "test-token"

        # Bulk update
        response = client.post(
            "/api/config",
            json={
                "updates": {
                    "providers.hetzner.region": "nbg1",
                    "monitoring.enabled": True
                }
            }
        )
        assert response.status_code == 200
        assert response.json()["updated_count"] == 2

    def test_provider_discovery_workflow_via_api(self):
        """Should discover providers and their capabilities via API"""
        client = TestClient(app)

        # List providers
        response = client.get("/api/providers")
        assert response.status_code == 200
        providers = response.json()["providers"]
        assert len(providers) > 0

        # Get provider details
        provider_name = providers[0]["name"]
        response = client.get(f"/api/providers/{provider_name}")
        assert response.status_code == 200
        assert "capabilities" in response.json()


class TestMultiComponentIntegration:
    """Integration tests for complex multi-component workflows"""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp(prefix="livchat_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_orchestrator_and_storage_integration(self, temp_storage_dir):
        """Should integrate Orchestrator with StorageManager"""
        # Create orchestrator with custom config dir
        orch = Orchestrator(config_dir=Path(temp_storage_dir))

        # Set configuration
        orch.storage.config.set("test.key", "test_value")
        assert orch.storage.config.get("test.key") == "test_value"

        # Save server state
        orch.storage.state.add_server("test-server", {
            "id": "srv-123",
            "name": "test-server"
        })

        # Retrieve server
        server = orch.storage.state.get_server("test-server")
        assert server is not None
        assert server["id"] == "srv-123"

        # Create new orchestrator instance (simulating restart)
        orch2 = Orchestrator(config_dir=Path(temp_storage_dir))

        # Verify config and state persisted
        assert orch2.storage.config.get("test.key") == "test_value"
        server2 = orch2.storage.state.get_server("test-server")
        assert server2 is not None
        assert server2["id"] == "srv-123"

    def test_job_manager_and_storage_integration(self, temp_storage_dir):
        """Should integrate JobManager with StorageManager"""
        storage = StorageManager(config_dir=Path(temp_storage_dir))
        job_manager = JobManager(storage=storage)

        # Create jobs
        job1 = job_manager.create_job("test_1", {"param": "value1"})
        job2 = job_manager.create_job("test_2", {"param": "value2"})

        job1.mark_started()
        job2.mark_completed(result={"success": True})

        # Save to storage
        job_manager.save_to_storage()

        # Create new manager instance (simulating restart)
        job_manager2 = JobManager(storage=storage)

        # Verify jobs loaded
        all_jobs = job_manager2.list_jobs()
        assert len(all_jobs) == 2

        loaded_job1 = job_manager2.get_job(job1.job_id)
        assert loaded_job1.status == JobStatus.RUNNING

        loaded_job2 = job_manager2.get_job(job2.job_id)
        assert loaded_job2.status == JobStatus.COMPLETED
        assert loaded_job2.result == {"success": True}
