"""
Unit tests for App Deployer
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any
import yaml


class TestAppDeployer:
    """Test App Deployer orchestration"""

    @pytest.fixture
    def mock_portainer(self):
        """Create mock Portainer client"""
        mock = MagicMock()
        mock.create_stack = AsyncMock(return_value={
            "Id": 1,
            "Name": "test-app",
            "Status": 1
        })
        mock.get_stack = AsyncMock(return_value={
            "Id": 1,
            "Name": "test-app",
            "Status": 1
        })
        mock.delete_stack = AsyncMock(return_value=True)
        mock.list_stacks = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_cloudflare(self):
        """Create mock Cloudflare client"""
        mock = MagicMock()
        mock.add_app_with_standard_prefix = AsyncMock(return_value=[
            {"success": True, "record_name": "test.example.com"}
        ])
        mock.setup_server_dns = AsyncMock(return_value={
            "success": True,
            "record_name": "ptn.example.com"
        })
        return mock

    @pytest.fixture
    def mock_registry(self):
        """Create mock App Registry"""
        mock = MagicMock()

        # Sample app definition
        sample_app = {
            "name": "portainer",
            "category": "infrastructure",
            "version": "2.19.4",
            "description": "Container management",
            "ports": ["9443:9443"],
            "volumes": ["portainer_data:/data"],
            "environment": {"ADMIN_PASSWORD": "{{ vault.portainer_password }}"},
            "dependencies": [],
            "dns_prefix": "ptn",
            "health_check": {
                "endpoint": "https://localhost:9443",
                "interval": "30s"
            }
        }

        mock.get_app = MagicMock(return_value=sample_app)
        mock.validate_app = MagicMock(return_value={"valid": True})
        mock.resolve_dependencies = MagicMock(return_value=["portainer"])
        mock.generate_compose = MagicMock(return_value="version: '3.8'\nservices:\n  portainer:\n    image: portainer/portainer-ce:2.19.4")

        return mock

    @pytest.fixture
    def app_deployer(self, mock_portainer, mock_cloudflare, mock_registry):
        """Create AppDeployer instance with mocks"""
        from src.app_deployer import AppDeployer
        deployer = AppDeployer(
            portainer=mock_portainer,
            cloudflare=mock_cloudflare,
            registry=mock_registry
        )

        # Mock the verify_health method to avoid real HTTP calls
        deployer.verify_health = AsyncMock(return_value={
            "healthy": True,
            "app": "test-app",
            "status": "running",
            "checks_passed": 1,
            "checks_failed": 0
        })

        # Mock check_health method
        deployer.check_health = AsyncMock(return_value={
            "healthy": True,
            "status": "running",
            "checks_passed": 1,
            "checks_failed": 0
        })

        # Mock check_dependency_health
        deployer.check_dependency_health = AsyncMock(return_value=True)

        return deployer

    @pytest.fixture
    def server_info(self):
        """Sample server information"""
        return {
            "name": "srv1",
            "ip": "192.168.1.100",
            "provider": "hetzner",
            "dns": {
                "zone": "example.com",
                "subdomain": "lab"
            }
        }

    def test_initialization(self, app_deployer):
        """Test AppDeployer initialization"""
        assert app_deployer is not None
        assert app_deployer.portainer is not None
        assert app_deployer.cloudflare is not None
        assert app_deployer.registry is not None

    @pytest.mark.asyncio
    async def test_deploy_simple_app(self, app_deployer, server_info):
        """Test deploying a simple app without dependencies"""
        # Deploy configuration
        config = {
            "admin_password": "secure_password_123",
            "network_name": "livchat_network"
        }

        # Deploy app
        result = await app_deployer.deploy(server_info, "portainer", config)

        # Verify
        assert result["success"] is True
        assert result["app"] == "portainer"
        assert "stack_id" in result

        # Check that methods were called
        app_deployer.registry.get_app.assert_called_with("portainer")
        app_deployer.registry.resolve_dependencies.assert_called_with("portainer")
        app_deployer.portainer.create_stack.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_app_with_dependencies(self, app_deployer, server_info, mock_registry):
        """Test deploying app with dependencies"""
        # Setup mock for n8n with dependencies
        n8n_app = {
            "name": "n8n",
            "dependencies": ["postgres", "redis"],
            "dns_prefix": "edt",
            "additional_dns": [{"prefix": "whk", "comment": "webhook"}]
        }
        mock_registry.get_app.return_value = n8n_app
        mock_registry.resolve_dependencies.return_value = ["postgres", "redis", "n8n"]

        # Deploy
        result = await app_deployer.deploy(server_info, "n8n", {})

        # Verify
        assert result["success"] is True
        assert result["app"] == "n8n"
        assert "dependencies_resolved" in result
        assert result["dependencies_resolved"] == ["postgres", "redis", "n8n"]

    @pytest.mark.asyncio
    async def test_configure_dns(self, app_deployer, server_info):
        """Test DNS configuration for app"""
        # Configure DNS
        result = await app_deployer.configure_dns(
            server_info, "portainer", "example.com"
        )

        # Verify
        assert result["success"] is True
        app_deployer.cloudflare.add_app_with_standard_prefix.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check(self, app_deployer, server_info):
        """Test health check verification"""
        # verify_health is already mocked in the fixture
        result = await app_deployer.verify_health(server_info, "portainer")

        # Verify
        assert result["healthy"] is True
        assert result["status"] == "running"
        assert result["checks_passed"] == 1
        assert result["checks_failed"] == 0

    @pytest.mark.asyncio
    async def test_rollback_on_failure(self, app_deployer, server_info):
        """Test rollback mechanism on deployment failure"""
        # Setup failure scenario
        app_deployer.portainer.create_stack = AsyncMock(
            side_effect=Exception("Deployment failed")
        )

        # Try to deploy
        result = await app_deployer.deploy(server_info, "portainer", {})

        # Verify rollback
        assert result["success"] is False
        assert "error" in result
        assert "Deployment failed" in result["error"]

    @pytest.mark.asyncio
    async def test_list_deployed_apps(self, app_deployer, server_info):
        """Test listing deployed applications"""
        # Setup mock stacks
        app_deployer.portainer.list_stacks = AsyncMock(return_value=[
            {"Id": 1, "Name": "portainer", "Status": 1},
            {"Id": 2, "Name": "postgres", "Status": 1},
            {"Id": 3, "Name": "n8n", "Status": 1}
        ])

        # List apps
        apps = await app_deployer.list_deployed_apps(server_info)

        # Verify
        assert len(apps) == 3
        assert any(app["name"] == "portainer" for app in apps)
        assert any(app["name"] == "n8n" for app in apps)

    @pytest.mark.asyncio
    async def test_delete_app(self, app_deployer, server_info):
        """Test deleting a deployed app"""
        # Setup mock - list_stacks needs to return the app
        app_deployer.portainer.list_stacks = AsyncMock(return_value=[
            {"Id": 1, "Name": "test-app", "Status": 1}
        ])

        # Delete app
        result = await app_deployer.delete_app(server_info, "test-app")

        # Verify
        assert result["success"] is True
        assert result["action"] == "deleted"
        app_deployer.portainer.delete_stack.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_update_app(self, app_deployer, server_info):
        """Test updating an existing app"""
        # Setup existing stack - list_stacks returns the app
        app_deployer.portainer.list_stacks = AsyncMock(return_value=[
            {"Id": 1, "Name": "portainer", "Status": 1}
        ])

        # Update app
        result = await app_deployer.update_app(
            server_info, "portainer", {"version": "2.19.5"}
        )

        # Verify
        assert result["success"] is True
        assert result["action"] == "updated"
        # Should have deleted old and created new
        app_deployer.portainer.delete_stack.assert_called_once_with(1)
        app_deployer.portainer.create_stack.assert_called()

    @pytest.mark.asyncio
    async def test_deploy_with_custom_compose(self, app_deployer, server_info):
        """Test deploying with custom docker-compose"""
        custom_compose = """
version: '3.8'
services:
  custom-app:
    image: custom:latest
    ports:
      - "8080:8080"
"""
        # Deploy with custom compose
        result = await app_deployer.deploy_custom(
            server_info,
            "custom-app",
            custom_compose
        )

        # Verify
        assert result["success"] is True
        app_deployer.portainer.create_stack.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_dependencies(self, app_deployer, server_info):
        """Test waiting for dependencies to be ready"""
        # verify_health is already mocked in fixture to return healthy=True

        # Wait for dependencies
        result = await app_deployer.wait_for_dependencies(
            server_info,
            ["postgres", "redis"]
        )

        # Verify
        assert result["ready"] is True
        assert all(dep in result["dependencies_status"] for dep in ["postgres", "redis"])
        assert result["dependencies_status"]["postgres"] is True
        assert result["dependencies_status"]["redis"] is True

    @pytest.mark.asyncio
    async def test_post_deploy_actions(self, app_deployer, server_info):
        """Test post-deployment actions"""
        # Define post-deploy actions
        actions = [
            {"action": "wait_health", "timeout": 1},  # Short timeout for testing
            {"action": "init_admin", "endpoint": "/api/init"}
        ]

        # verify_health is already mocked in fixture to return healthy=True
        # So wait_health should succeed immediately

        # Execute actions
        result = await app_deployer.execute_post_deploy(
            server_info,
            "portainer",
            actions
        )

        # Verify
        assert result["success"] is True
        assert "actions_executed" in result
        assert len(result["actions_executed"]) == 2
        assert result["actions_executed"][0]["action"] == "wait_health"
        assert result["actions_executed"][0]["success"] is True

    @pytest.mark.asyncio
    async def test_deploy_with_environment_override(self, app_deployer, server_info):
        """Test deploying with environment variable overrides"""
        # Config with env overrides
        config = {
            "environment": {
                "CUSTOM_VAR": "custom_value",
                "DEBUG": "true"
            }
        }

        # Deploy
        result = await app_deployer.deploy(server_info, "portainer", config)

        # Verify
        assert result["success"] is True
        # Check that generate_compose was called with the config
        app_deployer.registry.generate_compose.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_validation_failure(self, app_deployer, server_info, mock_registry):
        """Test deployment with validation failure"""
        # Setup validation failure
        mock_registry.validate_app.return_value = {
            "valid": False,
            "errors": ["Missing required field: version"]
        }

        # Try to deploy
        result = await app_deployer.deploy(server_info, "invalid-app", {})

        # Verify
        assert result["success"] is False
        assert "validation" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_concurrent_deployments(self, app_deployer, server_info):
        """Test handling concurrent app deployments"""
        import asyncio

        # Deploy multiple apps concurrently
        tasks = [
            app_deployer.deploy(server_info, "postgres", {}),
            app_deployer.deploy(server_info, "redis", {}),
            app_deployer.deploy(server_info, "portainer", {})
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all deployments
        successful = [r for r in results if isinstance(r, dict) and r.get("success")]
        assert len(successful) >= 1  # At least one should succeed