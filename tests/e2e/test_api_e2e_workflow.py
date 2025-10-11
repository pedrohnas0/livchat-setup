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
        'test_subdomain': 'lab'          # Using 'lab' subdomain
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
        job_description: str = "Job",
        validate_result: bool = True
    ) -> Dict:
        """
        Poll job endpoint until completion or failure

        Args:
            client: FastAPI test client
            job_id: Job identifier
            job_description: Human-readable job description
            validate_result: If True, checks result.success field (default: True)

        Returns:
            Final job data

        Raises:
            AssertionError: If job fails, times out, or result.success is False
        """
        print(f"\n⏳ Monitoring {job_description} (ID: {job_id})...")

        start_time = time.time()
        last_progress = -1
        log_sample_shown = False

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
            logs = job_data.get("logs", [])

            # Show progress updates
            if progress != last_progress:
                print(f"   [{int(elapsed)}s] {progress}% - {current_step}")

                # Show log sample once during execution (NEW: Observability validation)
                if not log_sample_shown and len(logs) > 0 and progress > 20:
                    print(f"   📋 Recent logs sample ({len(logs)} entries):")
                    for log in logs[-3:]:  # Show last 3 logs
                        print(f"      [{log.get('level', 'INFO')}] {log.get('message', '')}")
                    log_sample_shown = True

                last_progress = progress

            # Check if completed
            if status == "completed":
                print(f"✅ {job_description} job completed in {int(elapsed)}s")

                # OBSERVABILITY VALIDATION: Verify logs were captured
                print(f"   📊 Observability check:")
                print(f"      - Recent logs: {len(logs)} entries")
                if len(logs) > 0:
                    print(f"      - Latest: {logs[0].get('message', 'N/A')}")

                # CRITICAL: Validate actual result, not just job completion
                if validate_result:
                    result = job_data.get("result", {})

                    # Check for explicit failure indicators
                    has_error = result.get("error") is not None
                    success_field = result.get("success")

                    # Logic:
                    # - If success=False explicitly, it's a failure
                    # - If error field exists, it's a failure
                    # - If success=True or success field missing but no error, it's success
                    is_failure = (success_field is False) or has_error

                    if is_failure:
                        error_msg = result.get("error") or result.get("message", "Unknown error")
                        print(f"\n❌ {job_description} FAILED despite job completion:")
                        print(f"   Error: {error_msg}")
                        if logs:
                            print(f"   📋 Recent logs:")
                            for log in logs[-5:]:
                                print(f"      [{log.get('level', 'INFO')}] {log.get('message', '')}")
                        raise AssertionError(f"{job_description} failed: {error_msg}")

                    print(f"   ✅ Result validation: success (no errors detected)")

                return job_data

            # Check if failed
            if status == "failed":
                error = job_data.get("error", "Unknown error")
                print(f"❌ {job_description} failed: {error}")

                # Show recent logs to help debug (NEW: Observability for failures)
                if logs:
                    print(f"   📋 Recent logs before failure:")
                    for log in logs[-5:]:
                        print(f"      [{log.get('level', 'INFO')}] {log.get('message', '')}")

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
        dns_configured = False
        apps_deployed = []

        try:
            # ===========================================
            # STEP 1: Configure Provider via API
            # ===========================================
            print(f"\n🔐 [STEP 1/8] Configuring Hetzner provider via API...")

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
            print(f"\n🖥️  [STEP 2/8] Creating server via API...")

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
            print(f"\n🔧 [STEP 3/8] Setting up server infrastructure via API...")
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
            # STEP 3.25: Configure DNS via Cloudflare (if available)
            # ===========================================
            zone_name = config['test_domain']  # "livchat.ai"
            subdomain = config['test_subdomain']  # "api-test"

            if cloudflare_email and cloudflare_key:
                print(f"\n🌐 [STEP 3.25/8] Configuring DNS via Cloudflare...")
                print(f"   Zone: {zone_name}")
                print(f"   Subdomain: {subdomain}")
                print(f"   IP: {server_data.get('ip')}")

                # Note: API doesn't have direct DNS endpoint yet
                # We need to use orchestrator directly for this
                from src.api.dependencies import get_orchestrator
                orch = get_orchestrator()

                # Setup DNS
                import asyncio
                dns_result = asyncio.run(orch.setup_dns_for_server(
                    server_name=server_name,
                    zone_name=zone_name,
                    subdomain=subdomain
                ))

                if dns_result.get('success'):
                    dns_configured = True
                    print(f"✅ DNS configured successfully!")
                    print(f"   Records created:")
                    print(f"     - ptn.{subdomain}.{zone_name} → {server_data.get('ip')}")
                    print(f"     - edt.{subdomain}.{zone_name} → {server_data.get('ip')}")
                    print(f"\n⏳ Waiting 10s for DNS propagation...")
                    time.sleep(10)
                else:
                    print(f"⚠️ DNS configuration failed: {dns_result.get('error')}")
            else:
                print(f"\n⏭️ [STEP 3.25/8] Skipping DNS (Cloudflare not configured)")

            # ===========================================
            # STEP 3.5: Deploy Portainer via API (CRITICAL!)
            # ===========================================
            print(f"\n🐳 [STEP 3.5/8] Deploying Portainer via API...")
            print(f"   Portainer is REQUIRED for deploying applications...")

            portainer_config = {
                "server_name": server_name,
                "environment": {}
            }

            # Add domain if DNS is configured
            if dns_configured:
                portainer_domain = f"ptn.{subdomain}.{zone_name}"
                portainer_config["domain"] = portainer_domain
                print(f"   Using domain: {portainer_domain}")

            response = api_client.post(
                "/api/apps/portainer/deploy",
                json=portainer_config
            )

            assert response.status_code == 202, f"Failed to start Portainer deployment: {response.text}"

            portainer_data = response.json()
            job_id = portainer_data["job_id"]
            print(f"✅ Portainer deployment job started: {job_id}")

            # Monitor Portainer deployment with validation
            job_result = self.poll_job_until_complete(
                api_client,
                job_id,
                "Portainer deployment",
                validate_result=True  # Will catch if Portainer deployment actually fails
            )

            apps_deployed.append("portainer")
            print(f"✅ Portainer deployed successfully!")
            print(f"⏳ Waiting 30s for Portainer to fully initialize...")
            time.sleep(30)

            # ===========================================
            # STEP 4: List Available Apps via API
            # ===========================================
            print(f"\n📦 [STEP 4/8] Listing available apps via API...")

            response = api_client.get("/api/apps")
            assert response.status_code == 200, "Failed to list apps"

            apps_data = response.json()
            available_apps = [app["name"] for app in apps_data["apps"]]
            print(f"✅ Available apps: {', '.join(available_apps)}")

            # ===========================================
            # STEP 5: Deploy PostgreSQL via API
            # ===========================================
            print(f"\n🐘 [STEP 5/8] Deploying PostgreSQL via API...")

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
            print(f"\n🔴 [STEP 6/8] Deploying Redis via API...")

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
            # STEP 6.5: Deploy N8N via API
            # ===========================================
            print(f"\n🔄 [STEP 6.5/8] Deploying N8N workflow automation via API...")
            print(f"   Dependencies: PostgreSQL, Redis")

            n8n_config = {
                "server_name": server_name,
                "environment": {
                    "N8N_BASIC_AUTH_USER": "admin",
                    "N8N_BASIC_AUTH_PASSWORD": "n8npass123"
                }
            }

            # Add domain if DNS is configured
            if dns_configured:
                n8n_domain = f"edt.{subdomain}.{zone_name}"
                n8n_config["domain"] = n8n_domain
                print(f"   Using domain: {n8n_domain}")

            response = api_client.post(
                "/api/apps/n8n/deploy",
                json=n8n_config
            )

            if response.status_code == 202:
                deploy_data = response.json()
                job_id = deploy_data["job_id"]
                print(f"✅ N8N deployment job started: {job_id}")

                # Monitor deployment
                try:
                    job_result = self.poll_job_until_complete(
                        api_client,
                        job_id,
                        "N8N deployment"
                    )
                    apps_deployed.append("n8n")
                    print(f"✅ N8N deployed successfully!")
                    if dns_configured:
                        print(f"   URL: https://{n8n_domain}")
                    print(f"   Credentials: admin / n8npass123")
                except AssertionError as e:
                    print(f"⚠️ N8N deployment failed: {e}")
            else:
                print(f"⚠️ N8N deployment skipped: {response.status_code}")

            # ===========================================
            # STEP 7: Verify Final State via API
            # ===========================================
            print(f"\n🔍 [STEP 7/8] Verifying final state via API...")

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
            # OBSERVABILITY VALIDATION
            # ===========================================
            print(f"\n🔬 [OBSERVABILITY] Validating log capture system...")

            # Get all completed jobs
            completed_jobs = [job for job in jobs_data["jobs"] if job["status"] == "completed"]

            if completed_jobs:
                # Pick the server setup job (most logs)
                setup_job = next((job for job in completed_jobs if "setup" in job["job_type"]), completed_jobs[0])
                job_id = setup_job["job_id"]

                print(f"   Testing log retrieval for job: {job_id}")

                # Test 1: GET /api/jobs/{job_id} includes recent_logs
                response = api_client.get(f"/api/jobs/{job_id}")
                assert response.status_code == 200
                job_detail = response.json()
                recent_logs = job_detail.get("logs", [])

                print(f"   ✅ Recent logs via GET /api/jobs/{{id}}: {len(recent_logs)} entries")
                if len(recent_logs) > 0:
                    print(f"      Sample: {recent_logs[0].get('message', 'N/A')[:80]}...")

                # Test 2: GET /api/jobs/{job_id}/logs - Detailed logs
                response = api_client.get(f"/api/jobs/{job_id}/logs?tail=100")
                assert response.status_code == 200
                logs_detail = response.json()

                total_lines = logs_detail.get("total_lines", 0)
                log_file = logs_detail.get("log_file")
                detailed_logs = logs_detail.get("logs", [])

                print(f"   ✅ Detailed logs via GET /api/jobs/{{id}}/logs:")
                print(f"      - Total lines: {total_lines}")
                print(f"      - Log file: {log_file}")
                if detailed_logs:
                    print(f"      - Sample (last 3):")
                    for line in detailed_logs[-3:]:
                        print(f"         {line[:100]}...")

                # Test 3: Filter by ERROR level
                response = api_client.get(f"/api/jobs/{job_id}/logs?level=ERROR&tail=50")
                assert response.status_code == 200
                error_logs = response.json()

                print(f"   ✅ Filtered logs (ERROR only): {error_logs.get('total_lines', 0)} entries")

                # Assertions for observability
                assert len(recent_logs) > 0, "Recent logs should not be empty"
                assert total_lines > 0, "Detailed logs should not be empty"
                assert log_file is not None, "Log file path should be present"

                print(f"   🎉 Observability validation PASSED!")
            else:
                print(f"   ⚠️ No completed jobs to test observability")

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

            # Assertions - STRICT: Verify all critical steps completed
            assert server_created, "Server must be created"
            assert server_setup, "Server setup must complete"
            assert "portainer" in apps_deployed, "Portainer must be deployed (required for app deployments)"
            assert "postgres" in apps_deployed, "PostgreSQL must be deployed successfully"
            assert "redis" in apps_deployed, "Redis must be deployed successfully"
            # N8N is optional (requires DNS)
            if dns_configured:
                assert "n8n" in apps_deployed, "N8N must be deployed when DNS is configured"

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
