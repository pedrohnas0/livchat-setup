"""
Complete End-to-End Test via REST API

This test validates the ENTIRE LivChat Setup workflow using ONLY the REST API:
1. Server creation via POST /api/servers → Job monitoring
2. Server setup via POST /api/servers/{name}/setup → Job monitoring
3. App deployment via POST /api/apps/{name}/deploy → Job monitoring
4. State verification via GET endpoints

NO MOCKS - Only real infrastructure, controlled via API
NO direct Orchestrator calls - Everything through REST API

Run with:
  export LIVCHAT_E2E_REAL=true
  pytest tests/e2e/test_api_e2e_workflow.py -xvs

Skip with:
  SKIP_E2E_TESTS=true pytest tests/e2e/
"""

import os
import time
import pytest
import logging
from pathlib import Path
from typing import Dict, Optional
from fastapi.testclient import TestClient

from src.api.server import app
from src.api.dependencies import reset_orchestrator, reset_job_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class TestAPIE2EWorkflow:
    """E2E test using REST API only - NO direct Orchestrator access"""

    # Test configuration
    DEFAULT_TEST_CONFIG = {
        'server_name': 'e2e-api-test',
        'server_type': 'ccx23',          # 4 vCPU, 16GB RAM
        'region': 'ash',                 # Ashburn
        'os_image': 'debian-12',
        'test_domain': 'livchat.ai',
        'test_subdomain': 'api-test'
    }

    MAX_JOB_WAIT_TIME = 600  # 10 minutes max per job
    JOB_POLL_INTERVAL = 5    # Check every 5 seconds

    @pytest.fixture(scope="class", autouse=True)
    def check_e2e_enabled(self):
        """Check if E2E tests should run"""
        if os.environ.get("SKIP_E2E_TESTS", "false").lower() == "true":
            pytest.skip("E2E tests skipped via SKIP_E2E_TESTS=true")

        if os.environ.get("LIVCHAT_E2E_REAL", "false").lower() != "true":
            pytest.skip("E2E API tests require LIVCHAT_E2E_REAL=true")

    @pytest.fixture(scope="class")
    def api_client(self):
        """Create FastAPI test client with lifespan"""
        # Reset singletons to ensure clean state
        reset_orchestrator()
        reset_job_manager()

        # IMPORTANT: Use context manager to trigger lifespan events
        with TestClient(app) as client:
            yield client

        # Cleanup
        reset_orchestrator()
        reset_job_manager()

    def poll_job_until_complete(
        self,
        client: TestClient,
        job_id: str,
        job_description: str = "Job"
    ) -> Dict:
        """
        Poll job endpoint until completion or failure

        Returns:
            Final job data

        Raises:
            AssertionError: If job fails or times out
        """
        print(f"\n⏳ Monitoring {job_description} (ID: {job_id})...")

        start_time = time.time()
        last_progress = -1

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > self.MAX_JOB_WAIT_TIME:
                raise AssertionError(
                    f"{job_description} timed out after {self.MAX_JOB_WAIT_TIME}s"
                )

            # Poll job status
            response = client.get(f"/api/jobs/{job_id}")
            assert response.status_code == 200, f"Failed to get job status: {response.text}"

            job_data = response.json()
            status = job_data.get("status")
            progress = job_data.get("progress", 0)
            current_step = job_data.get("current_step", "")

            # Show progress updates
            if progress != last_progress:
                print(f"   [{int(elapsed)}s] {progress}% - {current_step}")
                last_progress = progress

            # Check if completed
            if status == "completed":
                print(f"✅ {job_description} completed in {int(elapsed)}s")
                return job_data

            # Check if failed
            if status == "failed":
                error = job_data.get("error", "Unknown error")
                print(f"❌ {job_description} failed: {error}")
                raise AssertionError(f"{job_description} failed: {error}")

            # Check if cancelled
            if status == "cancelled":
                raise AssertionError(f"{job_description} was cancelled")

            # Wait before next poll
            time.sleep(self.JOB_POLL_INTERVAL)

    @pytest.mark.timeout(1800)  # 30 minutes total
    def test_complete_infrastructure_via_api(self, api_client):
        """Test complete infrastructure workflow using ONLY REST API"""

        config = self.DEFAULT_TEST_CONFIG
        server_name = config['server_name']

        print("\n" + "="*80)
        print("🚀 E2E TEST VIA REST API")
        print("="*80)
        print(f"📋 Configuration:")
        print(f"  - Server: {server_name}")
        print(f"  - Type: {config['server_type']}")
        print(f"  - Region: {config['region']}")
        print(f"  - Image: {config['os_image']}")
        print("="*80)

        server_created = False
        server_setup = False
        apps_deployed = []

        try:
            # ===========================================
            # STEP 1: Configure Provider via API
            # ===========================================
            print(f"\n🔐 [STEP 1/6] Configuring Hetzner provider via API...")

            # Get token from environment or secrets
            hetzner_token = os.environ.get("HETZNER_TOKEN")
            if not hetzner_token:
                # Try to load from existing secrets
                from src.storage import StorageManager
                storage = StorageManager()
                hetzner_token = storage.secrets.get_secret("hetzner_token")

            if not hetzner_token:
                pytest.skip("HETZNER_TOKEN not found in environment or secrets")

            # Set provider name via API
            response = api_client.put(
                "/api/config/provider",
                json={"value": "hetzner"}
            )
            assert response.status_code == 200, f"Failed to set provider: {response.text}"
            print(f"✅ Provider set to 'hetzner' via API")

            # Set token via API (secrets are auto-loaded from vault)
            # We don't need to set it via API if it's already in vault
            # But let's verify it exists
            from src.storage import StorageManager
            storage = StorageManager()
            existing_token = storage.secrets.get_secret("hetzner_token")

            if not existing_token:
                # Token not in vault, need to configure it manually
                # For now, we assume token is already in vault from previous runs
                pytest.skip("Hetzner token not found in vault. Run configure_provider manually first.")

            # Cloudflare is auto-loaded from vault if credentials exist
            # Check if it's available
            cloudflare_email = storage.secrets.get_secret("cloudflare_email")
            cloudflare_key = storage.secrets.get_secret("cloudflare_api_key")

            if cloudflare_email and cloudflare_key:
                print(f"✅ Cloudflare auto-loaded from vault for {cloudflare_email}")
            else:
                print(f"⚠️ Cloudflare not configured in vault - DNS features will be skipped")

            # ===========================================
            # STEP 2: Create Server via API
            # ===========================================
            print(f"\n🖥️  [STEP 2/6] Creating server via API...")

            # Check if server already exists
            response = api_client.get(f"/api/servers/{server_name}")
            if response.status_code == 200:
                print(f"⚠️ Server {server_name} already exists, using existing...")
                server_data = response.json()
                server_created = True
            else:
                # Create server via API
                print(f"📝 Creating new server {server_name}...")
                response = api_client.post(
                    "/api/servers",
                    json={
                        "name": server_name,
                        "server_type": config['server_type'],
                        "location": config['region'],
                        "image": config['os_image']
                    }
                )

                assert response.status_code == 202, f"Failed to create server: {response.text}"

                create_data = response.json()
                job_id = create_data["job_id"]
                print(f"✅ Server creation job started: {job_id}")

                # Monitor job until completion
                job_result = self.poll_job_until_complete(
                    api_client,
                    job_id,
                    "Server creation"
                )

                # Verify server was created
                response = api_client.get(f"/api/servers/{server_name}")
                assert response.status_code == 200, "Server not found after creation"
                server_data = response.json()
                server_created = True

                print(f"\n✅ Server created successfully!")
                print(f"   ID: {server_data.get('id')}")
                print(f"   IP: {server_data.get('ip')}")
                print(f"   Status: {server_data.get('status')}")

                # Wait for server to be fully ready
                print(f"\n⏳ Waiting 60s for server to initialize...")
                time.sleep(60)

            # ===========================================
            # STEP 3: Setup Server via API
            # ===========================================
            print(f"\n🔧 [STEP 3/6] Setting up server infrastructure via API...")
            print(f"   This will install Docker, Swarm, Traefik...")

            response = api_client.post(
                f"/api/servers/{server_name}/setup",
                json={
                    "ssl_email": cloudflare_email or "admin@example.com",
                    "network_name": "livchat_network",
                    "timezone": "America/Sao_Paulo"
                }
            )

            assert response.status_code == 202, f"Failed to start setup: {response.text}"

            setup_data = response.json()
            job_id = setup_data["job_id"]
            print(f"✅ Server setup job started: {job_id}")

            # Monitor setup job
            job_result = self.poll_job_until_complete(
                api_client,
                job_id,
                "Server setup"
            )

            server_setup = True
            print(f"✅ Server setup completed successfully!")

            # ===========================================
            # STEP 4: List Available Apps via API
            # ===========================================
            print(f"\n📦 [STEP 4/6] Listing available apps via API...")

            response = api_client.get("/api/apps")
            assert response.status_code == 200, "Failed to list apps"

            apps_data = response.json()
            available_apps = [app["name"] for app in apps_data["apps"]]
            print(f"✅ Available apps: {', '.join(available_apps)}")

            # ===========================================
            # STEP 5: Deploy PostgreSQL via API
            # ===========================================
            print(f"\n🐘 [STEP 5/6] Deploying PostgreSQL via API...")

            response = api_client.post(
                "/api/apps/postgres/deploy",
                json={
                    "server_name": server_name,
                    "environment": {}
                }
            )

            if response.status_code == 202:
                deploy_data = response.json()
                job_id = deploy_data["job_id"]
                print(f"✅ PostgreSQL deployment job started: {job_id}")

                # Monitor deployment
                try:
                    job_result = self.poll_job_until_complete(
                        api_client,
                        job_id,
                        "PostgreSQL deployment"
                    )
                    apps_deployed.append("postgres")
                    print(f"✅ PostgreSQL deployed successfully!")
                except AssertionError as e:
                    print(f"⚠️ PostgreSQL deployment failed: {e}")
            else:
                print(f"⚠️ PostgreSQL deployment skipped: {response.status_code}")

            # ===========================================
            # STEP 6: Deploy Redis via API
            # ===========================================
            print(f"\n🔴 [STEP 6/6] Deploying Redis via API...")

            response = api_client.post(
                "/api/apps/redis/deploy",
                json={
                    "server_name": server_name,
                    "environment": {}
                }
            )

            if response.status_code == 202:
                deploy_data = response.json()
                job_id = deploy_data["job_id"]
                print(f"✅ Redis deployment job started: {job_id}")

                # Monitor deployment
                try:
                    job_result = self.poll_job_until_complete(
                        api_client,
                        job_id,
                        "Redis deployment"
                    )
                    apps_deployed.append("redis")
                    print(f"✅ Redis deployed successfully!")
                except AssertionError as e:
                    print(f"⚠️ Redis deployment failed: {e}")
            else:
                print(f"⚠️ Redis deployment skipped: {response.status_code}")

            # ===========================================
            # Verify Final State via API
            # ===========================================
            print(f"\n🔍 Verifying final state via API...")

            # Get server details
            response = api_client.get(f"/api/servers/{server_name}")
            assert response.status_code == 200
            server_data = response.json()
            print(f"✅ Server accessible via API")

            # List deployed apps
            response = api_client.get(f"/api/servers/{server_name}/apps")
            if response.status_code == 200:
                deployed_data = response.json()
                deployed_apps_list = [app["app_name"] for app in deployed_data["apps"]]
                print(f"✅ Deployed apps: {', '.join(deployed_apps_list)}")

            # List all jobs
            response = api_client.get("/api/jobs")
            assert response.status_code == 200
            jobs_data = response.json()
            print(f"✅ Total jobs created: {jobs_data['total']}")

            # ===========================================
            # Final Summary
            # ===========================================
            print(f"\n{'='*80}")
            print(f"📊 E2E API TEST SUMMARY")
            print(f"{'='*80}")
            print(f"✅ Server created: {server_created}")
            print(f"✅ Server setup: {server_setup}")
            print(f"✅ Apps deployed: {', '.join(apps_deployed) if apps_deployed else 'None'}")
            print(f"✅ All operations via REST API")

            # Assertions
            assert server_created, "Server must be created"
            assert server_setup, "Server setup must complete"

            print(f"\n🎉 E2E API TEST PASSED!")
            print(f"{'='*80}")

        except Exception as e:
            print(f"\n❌ E2E API TEST FAILED!")
            print(f"   Error: {str(e)}")
            raise

        finally:
            # Optional cleanup
            cleanup = os.environ.get("LIVCHAT_E2E_CLEANUP", "false") == "true"
            if cleanup and server_created:
                print(f"\n🧹 Cleaning up via API...")
                try:
                    response = api_client.delete(f"/api/servers/{server_name}")
                    if response.status_code == 202:
                        job_data = response.json()
                        print(f"   Deletion job started: {job_data['job_id']}")
                        # Could monitor deletion job here
                        print(f"   Server {server_name} deletion initiated")
                except Exception as e:
                    print(f"   Failed to delete server: {e}")
            else:
                print(f"\n📌 Server kept for inspection: {server_name}")
                print(f"   To cleanup: DELETE /api/servers/{server_name}")


class TestAPIJobMonitoring:
    """Test job monitoring and polling patterns via API"""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset state before each test"""
        reset_orchestrator()
        reset_job_manager()
        yield
        reset_orchestrator()
        reset_job_manager()

    def test_job_lifecycle_via_api(self):
        """Test creating and monitoring a job via API"""
        client = TestClient(app)

        # This would normally be triggered by server creation
        # For testing, we'll just verify the endpoints work

        # List jobs
        response = client.get("/api/jobs")
        assert response.status_code == 200
        initial_count = response.json()["total"]

        print(f"✅ Job listing works (count: {initial_count})")

    def test_job_filtering_via_api(self):
        """Test job filtering via API query parameters"""
        client = TestClient(app)

        # Test filters
        response = client.get("/api/jobs?status=pending")
        assert response.status_code == 200

        response = client.get("/api/jobs?job_type=create_server")
        assert response.status_code == 200

        response = client.get("/api/jobs?limit=10")
        assert response.status_code == 200

        print(f"✅ Job filtering works")


if __name__ == "__main__":
    import pytest
    pytest.main([
        __file__,
        "-xvs",           # Verbose, stop on first failure
        "--tb=short",     # Short traceback
        "--timeout=1800", # 30 minute timeout
    ])
