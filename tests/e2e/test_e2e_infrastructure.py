"""
End-to-End Infrastructure Tests for LivChat Setup

These tests ONLY run with real infrastructure (no mocks).

Requirements:
- Valid Hetzner token (from environment or vault)
- Valid Cloudflare credentials (optional)

Note: E2E tests always use real infrastructure.
To skip them, use pytest markers: pytest -m "not e2e"
"""

import os
import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestrator import Orchestrator
from src.storage import StorageManager


class TestE2EInfrastructure:
    """End-to-End tests with real infrastructure"""

    # Test configuration
    SERVER_CONFIG = {
        'name': 'e2e-test-server',
        'type': 'ccx23',         # 4 vCPU, 16GB RAM, 80GB NVMe
        'region': 'ash',         # Ashburn, VA
        'image': 'debian-12',
    }

    @pytest.fixture(scope="class")
    def e2e_enabled(self):
        """Check if E2E tests should run"""
        # E2E tests run by default unless explicitly disabled
        if os.environ.get("SKIP_E2E_TESTS", "false").lower() == "true":
            pytest.skip("E2E tests skipped via SKIP_E2E_TESTS=true")

    @pytest.fixture(scope="class")
    def orchestrator(self):
        """Create orchestrator with persistent storage for tests"""
        storage_dir = Path("/tmp/livchat_e2e_test")
        storage_dir.mkdir(parents=True, exist_ok=True)

        orch = Orchestrator(config_dir=storage_dir)
        orch.init()

        # Configure provider from environment or vault
        token = os.environ.get("HETZNER_TOKEN")
        if not token:
            # Try to load from vault
            storage = StorageManager(storage_dir)
            token = storage.secrets.get_secret("hetzner_token")

        if not token:
            pytest.skip("Hetzner token not found in environment or vault")

        orch.configure_provider("hetzner", token)  # Pass token as string, not dict

        yield orch

        # Cleanup is handled in individual tests

    @pytest.fixture
    def cleanup_server(self, orchestrator):
        """Fixture to ensure server cleanup after test"""
        servers_to_cleanup = []

        def register_for_cleanup(server_name: str):
            servers_to_cleanup.append(server_name)

        yield register_for_cleanup

        # Cleanup after test
        for server_name in servers_to_cleanup:
            try:
                print(f"\n🧹 Cleaning up server: {server_name}")
                orchestrator.delete_server(server_name)
            except Exception as e:
                print(f"⚠️  Failed to cleanup {server_name}: {e}")

    @pytest.mark.timeout(600)  # 10 minute timeout
    def test_server_lifecycle(self, e2e_enabled, orchestrator, cleanup_server):
        _ = e2e_enabled  # Mark as used
        """Test complete server lifecycle: create → setup → delete"""

        server_name = self.SERVER_CONFIG['name']
        cleanup_server(server_name)  # Register for cleanup

        # 1. Create server
        server = orchestrator.create_server(
            name=server_name,
            server_type=self.SERVER_CONFIG['type'],
            region=self.SERVER_CONFIG['region'],
            image=self.SERVER_CONFIG['image']
        )

        assert server is not None
        assert server.get('ip') is not None
        assert server.get('status') == 'running'

        # 2. Setup server (base + docker + swarm + traefik)
        result = orchestrator.setup_server(server_name, {
            'ssl_email': 'test@example.com',
            'network_name': 'livchat_network'
        })

        assert result.get('success') is True

        # Get steps from either root or details object
        steps = result.get('completed_steps', [])
        if not steps and 'details' in result:
            steps = result['details'].get('completed_steps', [])
        if not steps:
            steps = result.get('steps_completed', [])

        assert len(steps) > 0, "No completed steps found in result"
        assert 'base-setup' in steps
        assert 'docker-install' in steps
        assert 'swarm-init' in steps
        assert 'traefik-deploy' in steps

        # 3. Verify server state
        servers = orchestrator.list_servers()
        server_names = [s.get('name') for s in servers]
        assert server_name in server_names

        # 4. Delete server (handled by cleanup_server fixture)
        # This ensures cleanup even if test fails

    @pytest.mark.timeout(900)  # 15 minute timeout for full deployment
    @pytest.mark.asyncio
    async def test_app_deployment_with_dependencies(self, e2e_enabled, orchestrator, cleanup_server):
        _ = e2e_enabled  # Mark as used
        """Test deploying applications with dependencies"""

        server_name = f"{self.SERVER_CONFIG['name']}-apps"
        cleanup_server(server_name)  # Register for cleanup

        # 1. Create and setup server
        server = orchestrator.create_server(
            name=server_name,
            server_type=self.SERVER_CONFIG['type'],
            region=self.SERVER_CONFIG['region'],
            image=self.SERVER_CONFIG['image']
        )

        assert server is not None

        # Full setup including Portainer
        result = orchestrator.setup_server(server_name, {
            'ssl_email': 'test@example.com',
            'setup_portainer': True,
            'portainer_admin_password': 'TestPassword123!'
        })

        assert result.get('success') is True

        # 2. Deploy PostgreSQL (dependency for n8n)
        postgres_result = await orchestrator.deploy_app(
            server_name=server_name,
            app_name='postgres',
            config={
                'postgres_password': 'pgpass123',
                'postgres_db': 'postgres'
            }
        )

        assert postgres_result.get('success') is True

        # 3. Deploy Redis (dependency for n8n)
        redis_result = await orchestrator.deploy_app(
            server_name=server_name,
            app_name='redis',
            config={
                'redis_password': 'redispass123'
            }
        )

        assert redis_result.get('success') is True

        # 4. Deploy n8n with dependencies
        n8n_result = await orchestrator.deploy_app(
            server_name=server_name,
            app_name='n8n',
            config={
                'n8n_basic_auth_user': 'admin',
                'n8n_basic_auth_password': 'n8npass123',
                'postgres_password': 'pgpass123',
                'redis_password': 'redispass123'
            }
        )

        assert n8n_result.get('success') is True

        # 5. Verify all apps are deployed
        # This would require checking Portainer API or server state
        # For now, we trust the success flags

    @pytest.mark.timeout(300)  # 5 minute timeout
    def test_dns_configuration(self, e2e_enabled, orchestrator, cleanup_server):
        _ = e2e_enabled  # Mark as used
        """Test DNS configuration with Cloudflare"""

        # Skip if no Cloudflare credentials
        if not orchestrator.cloudflare:
            pytest.skip("Cloudflare not configured")

        server_name = f"{self.SERVER_CONFIG['name']}-dns"
        cleanup_server(server_name)

        # Create server
        server = orchestrator.create_server(
            name=server_name,
            server_type=self.SERVER_CONFIG['type'],
            region=self.SERVER_CONFIG['region'],
            image=self.SERVER_CONFIG['image']
        )

        assert server is not None

        # Configure DNS
        dns_result = orchestrator.configure_dns(
            server_name=server_name,
            zone='livchat.ai',
            subdomain='e2e-test'
        )

        assert dns_result.get('success') is True
        assert dns_result.get('records_created') > 0

        # Cleanup DNS records
        cleanup_result = orchestrator.cleanup_dns(
            zone='livchat.ai',
            subdomain='e2e-test'
        )

        assert cleanup_result.get('success') is True

    @pytest.mark.timeout(60)  # 1 minute timeout
    def test_state_persistence(self, e2e_enabled, orchestrator):
        _ = e2e_enabled  # Mark as used
        _ = orchestrator  # Mark as used
        """Test that state persists across orchestrator instances"""

        storage_dir = Path("/tmp/livchat_e2e_test")

        # Create first orchestrator and add some state
        orch1 = Orchestrator(config_dir=storage_dir)
        orch1.init()

        # Add a test server to state (without creating real server)
        test_server = {
            'name': 'test-persistence',
            'ip': '10.0.0.1',
            'provider': 'hetzner',
            'status': 'running'
        }
        orch1.storage.state.add_server(test_server)
        orch1.storage.state.save()

        # Create second orchestrator from same storage
        orch2 = Orchestrator(config_dir=storage_dir)
        orch2.init()

        # Verify state was loaded
        servers = orch2.storage.state.get_servers()
        server_names = [s.get('name') for s in servers]

        assert 'test-persistence' in server_names

        # Cleanup test state
        orch2.storage.state.remove_server('test-persistence')
        orch2.storage.state.save()


if __name__ == "__main__":
    # Run with: python -m pytest tests/e2e/test_e2e_infrastructure.py -v
    # Or skip with: SKIP_E2E_TESTS=true python -m pytest tests/e2e/
    pytest.main([__file__, "-v", "--tb=short"])