"""
Unit tests for domain parameter translation in executors

Tests verify that 'domain' parameter from API is correctly
translated to 'dns_domain' for internal use.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.job_executors.infrastructure_executors import execute_deploy_infrastructure
from src.job_executors.app_executors import execute_deploy_app
from src.job_manager import Job


class TestInfrastructureExecutorDomainTranslation:
    """Test domain → dns_domain translation in infrastructure executor"""

    @pytest.mark.asyncio
    async def test_portainer_deploy_translates_domain_to_dns_domain(self):
        """Should translate 'domain' parameter to 'dns_domain' for Portainer"""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.deploy_portainer = MagicMock(return_value=True)

        job = Job(
            job_id="test-job-1",
            job_type="deploy_infrastructure",
            params={
                "app_name": "portainer",
                "server_name": "test-server",
                "environment": {},
                "domain": "ptn.lab.livchat.ai"  # API passes as 'domain'
            }
        )

        # Act
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            # Make to_thread return the result directly
            mock_to_thread.return_value = True

            result = await execute_deploy_infrastructure(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # Verify orchestrator.deploy_portainer was called with dns_domain
        mock_to_thread.assert_called_once()
        call_args = mock_to_thread.call_args

        # Check that config contains dns_domain, not domain
        assert "config" in call_args.kwargs or len(call_args.args) > 2

        # Get config from either kwargs or args
        if "config" in call_args.kwargs:
            config = call_args.kwargs["config"]
        else:
            config = call_args.args[2]  # Third arg is config

        # THIS IS THE KEY ASSERTION: dns_domain should be set, not domain
        assert "dns_domain" in config, "Config should contain 'dns_domain'"
        assert config["dns_domain"] == "ptn.lab.livchat.ai"
        assert "domain" not in config, "Config should NOT contain raw 'domain'"

    @pytest.mark.asyncio
    async def test_portainer_deploy_without_domain_works(self):
        """Should work correctly when no domain is provided"""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.deploy_portainer = MagicMock(return_value=True)

        job = Job(
            job_id="test-job-2",
            job_type="deploy_infrastructure",
            params={
                "app_name": "portainer",
                "server_name": "test-server",
                "environment": {},
                "domain": None  # No domain
            }
        )

        # Act
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = True
            result = await execute_deploy_infrastructure(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # Verify config does not contain dns_domain when domain is None
        call_args = mock_to_thread.call_args
        if "config" in call_args.kwargs:
            config = call_args.kwargs["config"]
        else:
            config = call_args.args[2]

        assert "dns_domain" not in config, "Should not have dns_domain when domain is None"


class TestAppExecutorDomainTranslation:
    """Test domain → dns_domain translation in app executor"""

    @pytest.mark.asyncio
    async def test_app_deploy_translates_domain_to_dns_domain(self):
        """Should translate 'domain' parameter to 'dns_domain' for app deployment"""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.deploy_app = AsyncMock(return_value={
            "success": True,
            "app": "n8n",
            "stack_id": 1
        })

        job = Job(
            job_id="test-job-3",
            job_type="deploy_app",
            params={
                "app_name": "n8n",
                "server_name": "test-server",
                "environment": {},
                "domain": "edt.lab.livchat.ai"  # API passes as 'domain'
            }
        )

        # Act
        result = await execute_deploy_app(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # Verify orchestrator.deploy_app was called with dns_domain
        mock_orchestrator.deploy_app.assert_called_once()
        call_kwargs = mock_orchestrator.deploy_app.call_args.kwargs

        # Check config parameter
        assert "config" in call_kwargs
        config = call_kwargs["config"]

        # THIS IS THE KEY ASSERTION: dns_domain should be set, not domain
        assert "dns_domain" in config, "Config should contain 'dns_domain'"
        assert config["dns_domain"] == "edt.lab.livchat.ai"
        assert "domain" not in config, "Config should NOT contain raw 'domain'"

    @pytest.mark.asyncio
    async def test_app_deploy_without_domain_works(self):
        """Should work correctly when no domain is provided"""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.deploy_app = AsyncMock(return_value={
            "success": True,
            "app": "postgres",
            "stack_id": 1
        })

        job = Job(
            job_id="test-job-4",
            job_type="deploy_app",
            params={
                "app_name": "postgres",
                "server_name": "test-server",
                "environment": {},
                "domain": None  # No domain (internal service)
            }
        )

        # Act
        result = await execute_deploy_app(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # Verify config does not contain dns_domain when domain is None
        call_kwargs = mock_orchestrator.deploy_app.call_args.kwargs
        config = call_kwargs["config"]

        assert "dns_domain" not in config, "Should not have dns_domain when domain is None"


class TestParameterConsistency:
    """Test that parameter naming is consistent across the system"""

    def test_server_setup_expects_dns_domain(self):
        """Document that server_setup.py expects 'dns_domain' not 'domain'"""
        # This is a documentation test - verifying our understanding
        # server_setup.py:604 checks for "dns_domain" in config
        # This test ensures we don't accidentally break this contract

        # Read server_setup.py to verify it uses dns_domain
        import pathlib
        server_setup_path = pathlib.Path(__file__).parent.parent.parent / "src" / "server_setup.py"
        content = server_setup_path.read_text()

        # Verify the key line exists
        assert 'if "dns_domain" in config:' in content, \
            "server_setup.py must check for 'dns_domain' in config"
        assert 'config["portainer_domain"] = config["dns_domain"]' in content, \
            "server_setup.py must map dns_domain to portainer_domain"

    def test_e2e_direct_uses_dns_domain(self):
        """Document that E2E direct test uses 'dns_domain'"""
        # This is a documentation test - verifying our understanding
        # E2E direct test passes dns_domain and it works

        import pathlib
        e2e_path = pathlib.Path(__file__).parent.parent / "e2e" / "test_complete_e2e_workflow.py"
        content = e2e_path.read_text()

        # Verify E2E test uses dns_domain
        assert 'portainer_config["dns_domain"]' in content, \
            "E2E direct test must use 'dns_domain' for Portainer"
        assert 'n8n_config["dns_domain"]' in content, \
            "E2E direct test must use 'dns_domain' for N8N"


class TestInfrastructureBundleStateManagement:
    """Test that infrastructure bundle only adds 'infrastructure' to state, not components"""

    @pytest.mark.asyncio
    async def test_infrastructure_bundle_only_adds_bundle_to_state(self):
        """
        When deploying infrastructure bundle, only 'infrastructure' should be added to state.
        NOT 'traefik' and 'portainer' individually (Option 3: Hybrid approach)
        """
        # Arrange
        mock_orchestrator = MagicMock()
        mock_server = {
            "name": "test-server",
            "ip": "1.2.3.4",
            "applications": []
        }

        # Mock get_server to return our test server
        mock_orchestrator.get_server = MagicMock(return_value=mock_server)

        # Mock deploy_traefik and deploy_portainer to succeed
        mock_orchestrator.deploy_traefik = MagicMock(return_value=True)
        mock_orchestrator.deploy_portainer = MagicMock(return_value=True)

        # Mock storage to track state changes
        mock_orchestrator.storage = MagicMock()
        mock_orchestrator.storage.state = MagicMock()

        job = Job(
            job_id="test-infrastructure-bundle",
            job_type="deploy_infrastructure",
            params={
                "app_name": "infrastructure",
                "server_name": "test-server",
                "environment": {},
                "domain": None
            }
        )

        # Act
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            # Simulate successful deployment
            mock_to_thread.return_value = True
            result = await execute_deploy_infrastructure(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # CRITICAL ASSERTION: State should ONLY contain "infrastructure"
        # NOT ["traefik", "portainer", "infrastructure"] (the old buggy behavior)
        apps_in_state = mock_server["applications"]

        assert "infrastructure" in apps_in_state, "infrastructure should be in state"
        assert "traefik" not in apps_in_state, "traefik should NOT be in state (part of bundle)"
        assert "portainer" not in apps_in_state, "portainer should NOT be in state (part of bundle)"
        assert len(apps_in_state) == 1, f"Should have exactly 1 app in state, got {len(apps_in_state)}: {apps_in_state}"

    @pytest.mark.asyncio
    async def test_infrastructure_bundle_cleans_old_component_entries(self):
        """
        When deploying infrastructure bundle on a server with old component entries,
        it should REMOVE 'portainer' and 'traefik' and replace with 'infrastructure'
        (Migration from old architecture)
        """
        # Arrange
        mock_orchestrator = MagicMock()
        mock_server = {
            "name": "test-server",
            "ip": "1.2.3.4",
            "applications": ["portainer", "traefik"]  # OLD state from previous test
        }

        mock_orchestrator.get_server = MagicMock(return_value=mock_server)
        mock_orchestrator.deploy_traefik = MagicMock(return_value=True)
        mock_orchestrator.deploy_portainer = MagicMock(return_value=True)
        mock_orchestrator.storage = MagicMock()
        mock_orchestrator.storage.state = MagicMock()

        job = Job(
            job_id="test-migration",
            job_type="deploy_infrastructure",
            params={
                "app_name": "infrastructure",
                "server_name": "test-server",
                "environment": {},
                "domain": None
            }
        )

        # Act
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = True
            result = await execute_deploy_infrastructure(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # MIGRATION ASSERTION: Old components should be removed
        apps_in_state = mock_server["applications"]

        assert "infrastructure" in apps_in_state, "infrastructure should be added"
        assert "traefik" not in apps_in_state, "traefik should be REMOVED (now part of bundle)"
        assert "portainer" not in apps_in_state, "portainer should be REMOVED (now part of bundle)"
        assert len(apps_in_state) == 1, f"Should have exactly 1 app after cleanup, got {len(apps_in_state)}: {apps_in_state}"

    @pytest.mark.asyncio
    async def test_infrastructure_components_not_added_individually(self):
        """
        Verify that deploy_traefik and deploy_portainer do NOT add themselves to state
        when called as part of infrastructure bundle deployment
        """
        # Arrange
        mock_orchestrator = MagicMock()
        mock_server = {
            "name": "test-server",
            "ip": "1.2.3.4",
            "applications": []
        }

        mock_orchestrator.get_server = MagicMock(return_value=mock_server)

        # Track calls to storage.state.update_server
        update_calls = []

        def track_update(server_name, server_data):
            update_calls.append({
                "server_name": server_name,
                "applications": server_data.get("applications", []).copy()
            })

        mock_orchestrator.storage = MagicMock()
        mock_orchestrator.storage.state = MagicMock()
        mock_orchestrator.storage.state.update_server = MagicMock(side_effect=track_update)

        # Mock deploy methods
        mock_orchestrator.deploy_traefik = MagicMock(return_value=True)
        mock_orchestrator.deploy_portainer = MagicMock(return_value=True)

        job = Job(
            job_id="test-component-isolation",
            job_type="deploy_infrastructure",
            params={
                "app_name": "infrastructure",
                "server_name": "test-server",
                "environment": {},
                "domain": None
            }
        )

        # Act
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = True
            result = await execute_deploy_infrastructure(job, mock_orchestrator)

        # Assert
        assert result["success"] is True

        # In the FIXED version, there should be NO calls that add "traefik" or "portainer" individually
        for call in update_calls:
            apps = call["applications"]
            if "traefik" in apps and "infrastructure" in apps:
                pytest.fail(f"BUG: Both 'traefik' and 'infrastructure' found in same update: {apps}")
            if "portainer" in apps and "infrastructure" in apps:
                pytest.fail(f"BUG: Both 'portainer' and 'infrastructure' found in same update: {apps}")
