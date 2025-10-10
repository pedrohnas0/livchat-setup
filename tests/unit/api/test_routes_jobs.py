"""
Unit tests for job routes

Following TDD: Write tests FIRST

Tests for:
- GET /api/jobs - List jobs
- GET /api/jobs/{job_id} - Get specific job
- POST /api/jobs/{job_id}/cancel - Cancel job
- POST /api/jobs/cleanup - Cleanup old jobs
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.routes.jobs import router
from src.api.dependencies import reset_job_manager, reset_orchestrator
from src.job_manager import Job, JobManager, JobStatus
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestListJobsEndpoint:
    """Test GET /api/jobs endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        # Get fresh manager and clear all jobs
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()  # Clear in-memory jobs
        manager.save_to_storage()  # Clear persisted jobs

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_list_jobs_empty(self):
        """Should return empty list when no jobs"""
        # Act
        response = client.get("/api/jobs")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_returns_all_jobs(self):
        """Should return all jobs"""
        # Arrange - create jobs via dependency
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job1 = manager.create_job("create_server", {"name": "test1"})
        job2 = manager.create_job("deploy_app", {"name": "test2"})

        # Act
        response = client.get("/api/jobs")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["total"] == 2

    def test_list_jobs_filter_by_status(self):
        """Should filter jobs by status"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job1 = manager.create_job("test", {})
        job2 = manager.create_job("test", {})
        job2.mark_started()

        # Act
        response = client.get("/api/jobs?status=pending")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["status"] == "pending"

    def test_list_jobs_filter_by_type(self):
        """Should filter jobs by type"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.create_job("create_server", {})
        manager.create_job("deploy_app", {})

        # Act
        response = client.get("/api/jobs?job_type=create_server")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_type"] == "create_server"

    def test_list_jobs_limit(self):
        """Should respect limit parameter"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        for i in range(5):
            manager.create_job("test", {})

        # Act
        response = client.get("/api/jobs?limit=2")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["total"] == 2

    def test_list_jobs_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.get("/api/jobs")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_list_jobs_includes_job_details(self):
        """Should include all job details"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {"key": "value"})
        job.add_log("Test log")

        # Act
        response = client.get("/api/jobs")

        # Assert
        assert response.status_code == 200
        data = response.json()
        job_data = data["jobs"][0]
        assert "job_id" in job_data
        assert "job_type" in job_data
        assert "status" in job_data
        assert "progress" in job_data
        assert "params" in job_data
        assert "logs" in job_data
        assert job_data["params"]["key"] == "value"


class TestGetJobEndpoint:
    """Test GET /api/jobs/{job_id} endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        # Get fresh manager and clear all jobs
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()  # Clear in-memory jobs
        manager.save_to_storage()  # Clear persisted jobs

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_get_job_returns_200(self):
        """Should return 200 for existing job"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        # Act
        response = client.get(f"/api/jobs/{job.job_id}")

        # Assert
        assert response.status_code == 200

    def test_get_job_returns_404_for_nonexistent(self):
        """Should return 404 for non-existent job"""
        # Act
        response = client.get("/api/jobs/nonexistent-job-id")

        # Assert
        assert response.status_code == 404

    def test_get_job_returns_json(self):
        """Should return JSON response"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        # Act
        response = client.get(f"/api/jobs/{job.job_id}")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_get_job_returns_complete_data(self):
        """Should return complete job data"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("create_server", {"name": "test"})
        job.add_log("Test log entry")
        job.update_progress(50, "Half done")

        # Act
        response = client.get(f"/api/jobs/{job.job_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job.job_id
        assert data["job_type"] == "create_server"
        assert data["status"] == "pending"
        assert data["progress"] == 50
        assert data["current_step"] == "Half done"
        assert data["params"]["name"] == "test"
        assert len(data["logs"]) == 2  # add_log + update_progress

    def test_get_job_404_has_detail(self):
        """Should return error detail for 404"""
        # Act
        response = client.get("/api/jobs/nonexistent")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestCancelJobEndpoint:
    """Test POST /api/jobs/{job_id}/cancel endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        # Get fresh manager and clear all jobs
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()  # Clear in-memory jobs
        manager.save_to_storage()  # Clear persisted jobs

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_cancel_job_returns_200(self):
        """Should return 200 for successful cancellation"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        # Act
        response = client.post(f"/api/jobs/{job.job_id}/cancel")

        # Assert
        assert response.status_code == 200

    def test_cancel_job_returns_404_for_nonexistent(self):
        """Should return 404 for non-existent job"""
        # Act
        response = client.post("/api/jobs/nonexistent/cancel")

        # Assert
        assert response.status_code == 404

    def test_cancel_job_cancels_pending_job(self):
        """Should successfully cancel pending job"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        # Act
        response = client.post(f"/api/jobs/{job.job_id}/cancel")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cancelled" in data["message"].lower()
        assert data["job_id"] == job.job_id
        # Verify job was actually cancelled
        assert job.status == JobStatus.CANCELLED

    def test_cancel_job_fails_for_running_job(self):
        """Should fail to cancel running job"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})
        job.mark_started()

        # Act
        response = client.post(f"/api/jobs/{job.job_id}/cancel")

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "cannot be cancelled" in data["detail"].lower()

    def test_cancel_job_returns_json(self):
        """Should return JSON response"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        # Act
        response = client.post(f"/api/jobs/{job.job_id}/cancel")

        # Assert
        assert response.headers["content-type"] == "application/json"


class TestCleanupJobsEndpoint:
    """Test POST /api/jobs/cleanup endpoint"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        # Get fresh manager and clear all jobs
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()  # Clear in-memory jobs
        manager.save_to_storage()  # Clear persisted jobs

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_cleanup_jobs_returns_200(self):
        """Should return 200 OK"""
        # Act
        response = client.post("/api/jobs/cleanup")

        # Assert
        assert response.status_code == 200

    def test_cleanup_jobs_returns_json(self):
        """Should return JSON response"""
        # Act
        response = client.post("/api/jobs/cleanup")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_cleanup_jobs_removes_old_completed_jobs(self):
        """Should remove old completed jobs"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()

        # Create old job
        old_job = manager.create_job("test", {})
        old_job.mark_started()
        old_job.mark_completed(result={"success": True})
        old_job.completed_at = datetime.utcnow() - timedelta(days=8)

        # Create recent job
        recent_job = manager.create_job("test", {})
        recent_job.mark_started()
        recent_job.mark_completed(result={"success": True})

        # Act
        response = client.post("/api/jobs/cleanup?max_age_days=7")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["removed"] == 1
        # Verify old job was removed
        assert manager.get_job(old_job.job_id) is None
        assert manager.get_job(recent_job.job_id) is not None

    def test_cleanup_jobs_respects_max_age_parameter(self):
        """Should respect max_age_days parameter"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()

        job = manager.create_job("test", {})
        job.mark_started()
        job.mark_completed(result={})
        job.completed_at = datetime.utcnow() - timedelta(days=5)

        # Act - cleanup jobs older than 3 days
        response = client.post("/api/jobs/cleanup?max_age_days=3")

        # Assert
        data = response.json()
        assert data["data"]["removed"] == 1

    def test_cleanup_jobs_default_max_age(self):
        """Should use default max_age of 7 days"""
        # Act
        response = client.post("/api/jobs/cleanup")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "removed" in data["data"]

    def test_cleanup_jobs_returns_count(self):
        """Should return count of removed jobs"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()

        for i in range(3):
            job = manager.create_job("test", {})
            job.mark_started()
            job.mark_completed(result={})
            job.completed_at = datetime.utcnow() - timedelta(days=10)

        # Act
        response = client.post("/api/jobs/cleanup")

        # Assert
        data = response.json()
        assert data["data"]["removed"] == 3


class TestJobRoutesIntegration:
    """Integration tests for job routes"""

    def setup_method(self):
        """Reset singletons before each test"""
        reset_job_manager()
        reset_orchestrator()
        # Get fresh manager and clear all jobs
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        manager.jobs.clear()  # Clear in-memory jobs
        manager.save_to_storage()  # Clear persisted jobs

    def teardown_method(self):
        """Cleanup after each test"""
        reset_job_manager()
        reset_orchestrator()

    def test_job_lifecycle_via_api(self):
        """Test complete job lifecycle via API"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        # Act & Assert - List jobs
        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert len(response.json()["jobs"]) == 1

        # Get specific job
        response = client.get(f"/api/jobs/{job.job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

        # Cancel job
        response = client.post(f"/api/jobs/{job.job_id}/cancel")
        assert response.status_code == 200

        # Verify cancelled
        response = client.get(f"/api/jobs/{job.job_id}")
        assert response.json()["status"] == "cancelled"

    def test_all_job_routes_return_valid_json(self):
        """All routes should return valid JSON"""
        # Arrange
        from src.api.dependencies import get_job_manager
        manager = get_job_manager()
        job = manager.create_job("test", {})

        routes = [
            ("GET", "/api/jobs"),
            ("GET", f"/api/jobs/{job.job_id}"),
            ("POST", f"/api/jobs/{job.job_id}/cancel"),
            ("POST", "/api/jobs/cleanup"),
        ]

        # Act & Assert
        for method, path in routes:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path)

            # Should return JSON (200 or other)
            assert "application/json" in response.headers["content-type"]
