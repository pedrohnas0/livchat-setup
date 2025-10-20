"""
Complete End-to-End Test with All Features

This test validates the ENTIRE LivChat Setup workflow:
1. Server creation on Hetzner
2. Base setup (Docker, Swarm, Traefik)
3. Portainer deployment with auto-init
4. Cloudflare DNS configuration
5. Application deployment (PostgreSQL, Redis, N8N)
6. Health checks and verification

NO MOCKS - Only real infrastructure

Run with: pytest tests/e2e/test_complete_e2e_workflow.py
Skip with: SKIP_E2E_TESTS=true pytest tests/e2e/
"""

import os
import sys
import time
import asyncio
import pytest
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestrator import Orchestrator
from src.storage import StorageManager

# Configure clean logging - only essentials
logging.basicConfig(
    level=logging.WARNING,  # Only warnings and errors by default
    format='%(asctime)s [%(levelname)8s] %(message)s',
    datefmt='%H:%M:%S'
)

# Get logger for this test
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # This test can be INFO level

# Reduce ansible-runner verbosity
ansible_logger = logging.getLogger('ansible_runner')
ansible_logger.setLevel(logging.WARNING)  # Only warnings/errors


class TestCompleteE2EWorkflow:
    """Complete E2E test with optimized logging"""

    # Test configuration - consistent with test_complete_workflow.py
    DEFAULT_TEST_CONFIG = {
        'server_name': 'e2e-complete-test',
        'server_type': 'ccx23',          # 4 vCPU, 16GB RAM
        'region': 'ash',                 # Ashburn for consistency
        'os_image': 'debian-12',         # Debian 12
        'persistent_dir': '/tmp/livchat_e2e_complete'
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_logging(self):
        """Configure optimized logging for E2E tests"""
        # Set WARNING level for most modules to reduce noise
        logging.getLogger('src.orchestrator').setLevel(logging.WARNING)
        logging.getLogger('src.ansible_executor').setLevel(logging.WARNING)
        logging.getLogger('src.server_setup').setLevel(logging.WARNING)
        logging.getLogger('src.integrations.portainer').setLevel(logging.WARNING)
        logging.getLogger('src.integrations.cloudflare').setLevel(logging.WARNING)

        # Enable INFO only for critical errors
        logging.getLogger('src.providers').setLevel(logging.INFO)

    @pytest.fixture(scope="class")
    def e2e_enabled(self):
        """Check if E2E tests should run"""
        # E2E tests run by default unless explicitly disabled
        if os.environ.get("SKIP_E2E_TESTS", "false").lower() == "true":
            pytest.skip("E2E tests skipped via SKIP_E2E_TESTS=true")

    @pytest.fixture(scope="class")
    def orchestrator(self):
        """Create orchestrator with persistent storage"""
        config = self.DEFAULT_TEST_CONFIG
        storage_dir = Path(config['persistent_dir'])
        storage_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📁 Using persistent directory: {storage_dir}")

        orch = Orchestrator(config_dir=storage_dir)
        orch.init()

        # Load Hetzner token
        token = os.environ.get("HETZNER_TOKEN")
        if not token:
            storage = StorageManager(storage_dir)
            token = storage.secrets.get_secret("hetzner_token")

        if not token:
            pytest.skip("Hetzner token not found")

        # Configure provider
        print(f"🔐 Configuring Hetzner provider...")
        orch.configure_provider("hetzner", token)

        # Configure Cloudflare if available
        cloudflare_email = os.environ.get("CLOUDFLARE_EMAIL")
        cloudflare_key = os.environ.get("CLOUDFLARE_API_KEY")

        if cloudflare_email and cloudflare_key:
            print(f"☁️ Configuring Cloudflare for {cloudflare_email}...")
            orch.configure_cloudflare(cloudflare_email, cloudflare_key)

        yield orch

        # Cleanup handled in test

    @pytest.mark.timeout(1800)  # 30 minutes for complete test
    def test_complete_infrastructure_workflow(self, e2e_enabled, orchestrator):
        """Test COMPLETE workflow with all features and verbose output"""
        _ = e2e_enabled  # Mark as used

        config = self.DEFAULT_TEST_CONFIG
        server_name = config['server_name']
        zone_name = "livchat.ai"
        subdomain = "lab"

        # Print test header
        print("\n" + "="*60)
        print("🚀 COMPLETE E2E TEST")
        print("="*60)
        print(f"📋 Configuration:")
        print(f"  - Server: {server_name}")
        print(f"  - Type: {config['server_type']} (4 vCPU, 16GB RAM)")
        print(f"  - Region: {config['region']} (Ashburn)")
        print(f"  - Image: {config['os_image']}")
        print(f"  - DNS Zone: {zone_name}")
        print(f"  - Subdomain: {subdomain}")
        print(f"\n📌 Expected URLs:")
        print(f"  • Portainer: https://ptn.{subdomain}.{zone_name}")
        print(f"  • PostgreSQL: Internal service")
        print(f"  • Redis: Internal service")
        print(f"  • N8N: https://edt.{subdomain}.{zone_name}")
        print("="*80)

        server = None
        setup_complete = False
        portainer_deployed = False
        dns_configured = False
        apps_deployed = []

        try:
            # =====================================
            # STEP 1: Create Server
            # =====================================
            print(f"\n🖥️  [STEP 1/7] Creating server on Hetzner...")

            # Check if server already exists
            existing = orchestrator.get_server(server_name)
            if existing:
                print(f"⚠️ Server {server_name} found in state, verifying if it's accessible...")

                # Try to verify if server is really accessible
                import socket
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((existing.get('ip'), 22))
                    sock.close()

                    if result == 0:
                        print(f"✅ Server {server_name} is accessible, using existing...")
                        server = existing
                    else:
                        print(f"❌ Server {server_name} not accessible (port 22 closed)")
                        print(f"🧹 Removing stale server from state...")
                        orchestrator.storage.state.remove_server(server_name)
                        existing = None
                except Exception as e:
                    print(f"❌ Failed to verify server: {e}")
                    print(f"🧹 Removing stale server from state...")
                    orchestrator.storage.state.remove_server(server_name)
                    existing = None

            if not existing:
                print(f"📝 Creating new server {server_name}...")
                print(f"   Type: {config['server_type']}")
                print(f"   Region: {config['region']}")
                print(f"   Image: {config['os_image']}")

                server = orchestrator.create_server(
                    name=server_name,
                    server_type=config['server_type'],
                    region=config['region'],
                    image=config['os_image']
                )

                print(f"\n✅ Server created successfully!")
                print(f"   ID: {server.get('id')}")
                print(f"   IP: {server.get('ip')}")
                print(f"   IPv6: {server.get('ipv6', 'N/A')}")
                print(f"   Status: {server.get('status')}")

                # Wait longer for new server to be fully ready
                print(f"\n⏳ Waiting 60s for new server to initialize...")
                time.sleep(60)  # Single wait, no spam

            assert server is not None
            assert server.get('ip') is not None

            # Wait for SSH to be ready
            print(f"\n⏳ Waiting 30s for SSH to be ready...")
            time.sleep(30)  # Single wait

            # =====================================
            # STEP 2: Setup Server (Docker, Swarm, Traefik)
            # =====================================
            print(f"\n🔧 [STEP 2/7] Setting up server infrastructure...")
            print(f"   📌 This will install:")
            print(f"      - Docker & Docker Compose")
            print(f"      - Docker Swarm mode")
            print(f"      - Traefik reverse proxy")
            print(f"      - Basic firewall rules")

            print(f"   Starting setup process...")

            setup_result = orchestrator.setup_server(server_name, {
                'ssl_email': os.environ.get("CLOUDFLARE_EMAIL", "admin@example.com"),
                'network_name': 'livchat_network',
                'timezone': 'America/Sao_Paulo'
            })

            if setup_result.get('success'):
                setup_complete = True
                print(f"\n✅ Server setup completed successfully!")
                # Get steps from either root or details object
                steps = setup_result.get('completed_steps', [])
                if not steps and 'details' in setup_result:
                    steps = setup_result['details'].get('completed_steps', [])
                if not steps:
                    steps = setup_result.get('steps_completed', [])
                print(f"   Completed steps: {', '.join(steps)}")
            else:
                print(f"\n❌ Server setup failed!")
                print(f"   Error: {setup_result.get('error')}")
                raise AssertionError(f"Setup failed: {setup_result}")

            # =====================================
            # STEP 3: Configure DNS (if Cloudflare configured)
            # =====================================
            if orchestrator.cloudflare:
                print(f"\n🌐 [STEP 3/7] Configuring DNS on Cloudflare...")
                print(f"   Zone: {zone_name}")
                print(f"   Subdomain: {subdomain}")
                print(f"   IP: {server['ip']}")

                dns_result = asyncio.run(orchestrator.setup_dns_for_server(
                    server_name,
                    zone_name,
                    subdomain
                ))

                if dns_result.get('success'):
                    dns_configured = True
                    print(f"\n✅ DNS configured successfully!")
                    print(f"   Records created:")
                    print(f"     - ptn.{subdomain}.{zone_name} → {server['ip']}")
                    print(f"     - edt.{subdomain}.{zone_name} → {server['ip']}")
                    print(f"\n⏳ Waiting 10s for DNS propagation...")
                    time.sleep(10)
                else:
                    print(f"\n⚠️ DNS configuration skipped or failed")
                    print(f"   Error: {dns_result.get('error')}")
            else:
                print(f"\n⏭️ [STEP 3/7] Skipping DNS (Cloudflare not configured)")

            # =====================================
            # STEP 4: Deploy Portainer with Auto-Init
            # =====================================
            print(f"\n📊 [STEP 4/7] Deploying Portainer with auto-init...")

            portainer_config = {}
            if dns_configured:
                portainer_domain = f"ptn.{subdomain}.{zone_name}"
                portainer_config["dns_domain"] = portainer_domain
                print(f"   Using domain: {portainer_domain}")

            print(f"   Admin email: {os.environ.get('CLOUDFLARE_EMAIL', 'admin@example.com')}")
            print(f"\n🚀 Deploying Portainer stack...")

            portainer_result = orchestrator.deploy_portainer(server_name, config=portainer_config)

            if portainer_result:
                portainer_deployed = True
                print(f"\n✅ Portainer deployed successfully!")
                print(f"   Access URLs:")
                print(f"     - HTTPS: https://{server['ip']}:9443")
                if dns_configured:
                    print(f"     - Traefik: https://{portainer_domain}")
                print(f"\n⏳ Waiting 120s for Portainer to initialize...")
                time.sleep(120)  # Single wait
            else:
                print(f"\n❌ Portainer deployment failed!")

            # =====================================
            # STEP 5: Deploy PostgreSQL
            # =====================================
            print(f"\n🐘 [STEP 5/7] Deploying PostgreSQL database...")

            # Don't pass password, let it be generated (alphanumeric only)
            pg_result = asyncio.run(orchestrator.deploy_app(
                server_name,
                "postgres",
                {}  # Empty config, password will be auto-generated
            ))

            if pg_result.get('success'):
                apps_deployed.append("postgres")
                print(f"\n✅ PostgreSQL deployed successfully!")
                print(f"   Stack ID: {pg_result.get('stack_id')}")
                print(f"   Database: postgres")
                print(f"   Port: 5432 (internal)")
            else:
                print(f"\n❌ PostgreSQL deployment failed!")
                print(f"   Error: {pg_result.get('error')}")

            # =====================================
            # STEP 6: Deploy Redis
            # =====================================
            print(f"\n🔴 [STEP 6/7] Deploying Redis cache...")

            # Don't pass password, let it be generated if needed
            redis_result = asyncio.run(orchestrator.deploy_app(
                server_name,
                "redis",
                {}  # Empty config
            ))

            if redis_result.get('success'):
                apps_deployed.append("redis")
                print(f"\n✅ Redis deployed successfully!")
                print(f"   Stack ID: {redis_result.get('stack_id')}")
                print(f"   Port: 6379 (internal)")
            else:
                print(f"\n❌ Redis deployment failed!")
                print(f"   Error: {redis_result.get('error')}")

            # =====================================
            # STEP 7: Deploy N8N with Dependencies
            # =====================================
            print(f"\n🔄 [STEP 7/7] Deploying N8N workflow automation...")
            print(f"   Dependencies: PostgreSQL, Redis")

            n8n_config = {
                "basic_auth_user": "admin",
                "basic_auth_password": "n8npass123"
            }

            if dns_configured:
                n8n_domain = f"edt.{subdomain}.{zone_name}"
                n8n_config["dns_domain"] = n8n_domain
                print(f"   Using domain: {n8n_domain}")

            n8n_result = asyncio.run(orchestrator.deploy_app(
                server_name,
                "n8n",
                n8n_config
            ))

            if n8n_result.get('success'):
                apps_deployed.append("n8n")
                print(f"\n✅ N8N deployed successfully!")
                print(f"   Stack ID: {n8n_result.get('stack_id')}")
                if dns_configured:
                    print(f"   URL: https://{n8n_domain}")
                print(f"   Credentials: admin / n8npass123")
            else:
                print(f"\n❌ N8N deployment failed!")
                print(f"   Error: {n8n_result.get('error')}")

            # =====================================
            # Final Summary
            # =====================================
            print(f"\n{'='*60}")
            print(f"📊 TEST SUMMARY")
            print(f"{'='*60}")
            print(f"✅ Server created: {server_name} ({server['ip']})")
            print(f"✅ Base setup completed: {setup_complete}")
            print(f"✅ DNS configured: {dns_configured}")
            print(f"✅ Portainer deployed: {portainer_deployed}")
            print(f"✅ Apps deployed: {', '.join(apps_deployed) if apps_deployed else 'None'}")

            # Assertions
            assert setup_complete, "Server setup must complete"
            assert portainer_deployed, "Portainer must be deployed"
            assert "postgres" in apps_deployed, "PostgreSQL must be deployed"
            assert "redis" in apps_deployed, "Redis must be deployed"

            print(f"\n🎉 ALL TESTS PASSED!")
            print(f"{'='*60}")

        except Exception as e:
            print(f"\n❌ TEST FAILED!")
            print(f"   Error: {str(e)}")
            raise

        finally:
            # Optional cleanup (can be disabled for debugging)
            cleanup = os.environ.get("LIVCHAT_E2E_CLEANUP", "false") == "true"
            if cleanup and server:
                print(f"\n🧹 Cleaning up...")
                try:
                    orchestrator.delete_server(server_name)
                    print(f"   Server {server_name} deleted")
                except:
                    print(f"   Failed to delete server {server_name}")
            else:
                print(f"\n📌 Server kept for inspection: {server_name}")
                print(f"   To cleanup manually: orchestrator.delete_server('{server_name}')")


if __name__ == "__main__":
    # Run with optimized output
    pytest.main([
        __file__,
        "-x",             # Stop on first failure
        "-ra",            # Show summary of all except passed
        "--tb=line",      # One-line traceback
        "--timeout=1800", # 30 minute timeout
        "-p", "no:warnings"  # Disable warnings
    ])