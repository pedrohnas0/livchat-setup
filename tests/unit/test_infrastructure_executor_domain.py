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
