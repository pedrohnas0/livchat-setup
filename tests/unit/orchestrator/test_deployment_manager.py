"""
Unit tests for DeploymentManager

Tests TDD para extração do DeploymentManager do orchestrator_old.py
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from pathlib import Path
import sys

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.orchestrator.deployment_manager import DeploymentManager
# Não precisamos importar as outras classes - só usamos mocks!


class TestDeploymentManager:
    """Test suite for DeploymentManager"""

    @pytest.fixture
    def mock_storage(self, tmp_path):
        """Mock storage manager"""
        storage = MagicMock()  # Use MagicMock sem spec (padrão do projeto)
        storage.storage_dir = tmp_path
        storage.state = MagicMock()
        storage.secrets = MagicMock()

        # Mock state methods
        storage.state.get_server = Mock(return_value={
            "name": "test-server",
            "ip": "1.2.3.4",
            "applications": [],
            "dns_config": {
                "zone_name": "test.com",
                "subdomain": "dev"
            }
        })
        storage.state.update_server = Mock()
        storage.state.get_setting = Mock(return_value="admin@test.com")

        # Mock secrets methods
        storage.secrets.get_secret = Mock(return_value="secret123")
        storage.secrets.set_secret = Mock()

        return storage

    @pytest.fixture
    def mock_app_registry(self):
        """Mock app registry"""
        registry = MagicMock()  # Use MagicMock sem spec (padrão do projeto)

        # Mock resolve_dependencies
        registry.resolve_dependencies = MagicMock(return_value=["postgres", "redis", "n8n"])

        # Mock get_app
        registry.get_app = MagicMock(return_value={
            "name": "n8n",
            "dns_prefix": "n8n",
            "dependencies": ["postgres", "redis"]
        })

        return registry

    @pytest.fixture
    def mock_app_deployer(self):
        """Mock app deployer"""
        deployer = MagicMock()  # Use MagicMock sem spec (padrão do projeto)
        deployer.deploy = AsyncMock(return_value={"success": True})
        deployer.configure_dns = AsyncMock(return_value={"success": True})
        return deployer

    @pytest.fixture
    def mock_portainer(self):
        """Mock Portainer client"""
        portainer = MagicMock()  # Use MagicMock (padrão do projeto)
        portainer.get_endpoint_id = AsyncMock(return_value=1)
        return portainer

    @pytest.fixture
    def mock_cloudflare(self):
        """Mock Cloudflare client"""
        cloudflare = MagicMock()  # Use MagicMock (padrão do projeto)
        return cloudflare

    @pytest.fixture
    def deployment_manager(self, mock_storage, mock_app_registry):
        """Create DeploymentManager instance"""
        return DeploymentManager(
            storage=mock_storage,
            app_registry=mock_app_registry
        )

    # ==================== TESTS ====================

    def test_deployment_manager_initialization(self, deployment_manager):
        """Test DeploymentManager initializes correctly"""
        assert deployment_manager is not None
        assert deployment_manager.storage is not None
        assert deployment_manager.app_registry is not None
        assert deployment_manager.app_deployer is None  # Lazy initialized

    def test_ensure_app_deployer_success(self, deployment_manager, mock_portainer, mock_cloudflare):
        """Test _ensure_app_deployer initializes AppDeployer"""
        # Given
        deployment_manager.portainer = mock_portainer
        deployment_manager.cloudflare = mock_cloudflare

        # When
        result = deployment_manager._ensure_app_deployer()

        # Then
        assert result is True
        assert deployment_manager.app_deployer is not None

    def test_ensure_app_deployer_no_portainer(self, deployment_manager):
        """Test _ensure_app_deployer fails without Portainer"""
        # Given
        deployment_manager.portainer = None

        # When
        result = deployment_manager._ensure_app_deployer()

        # Then
        assert result is False
        assert deployment_manager.app_deployer is None

    def test_ensure_app_deployer_already_initialized(self, deployment_manager, mock_app_deployer):
        """Test _ensure_app_deployer returns True if already initialized"""
        # Given
        deployment_manager.app_deployer = mock_app_deployer

        # When
        result = deployment_manager._ensure_app_deployer()

        # Then
        assert result is True

    @pytest.mark.asyncio
    async def test_deploy_app_server_not_found(self, deployment_manager, mock_storage):
        """Test deploy_app fails when server doesn't exist"""
        # Given
        mock_storage.state.get_server.return_value = None

        # When
        result = await deployment_manager.deploy_app("nonexistent", "n8n")

        # Then
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_deploy_app_dependency_resolution_failure(self, deployment_manager, mock_app_registry):
        """Test deploy_app fails when dependency resolution fails"""
        # Given
        mock_app_registry.resolve_dependencies.side_effect = ValueError("Circular dependency")

        # When
        result = await deployment_manager.deploy_app("test-server", "badapp")

        # Then
        assert result["success"] is False
        assert "Dependency resolution failed" in result["error"]

    @pytest.mark.asyncio
    async def test_deploy_app_already_installed(self, deployment_manager, mock_storage, mock_app_registry):
        """Test deploy_app skips if already installed"""
        # Given
        mock_storage.state.get_server.return_value = {
            "name": "test-server",
            "applications": ["postgres", "redis", "n8n"],
            "dns_config": {}
        }
        mock_app_registry.resolve_dependencies.return_value = ["postgres", "redis", "n8n"]

        # When
        result = await deployment_manager.deploy_app("test-server", "n8n")

        # Then
        assert result["success"] is True
        assert result["skipped"] is True
        assert "already deployed" in result["message"]

    @pytest.mark.asyncio
    @patch('time.sleep')  # Mock time.sleep to avoid 15s wait
    async def test_deploy_app_success_with_dependencies(
        self, mock_sleep, deployment_manager, mock_storage, mock_app_registry,
        mock_portainer, mock_cloudflare, mock_app_deployer
    ):
        """Test deploy_app successfully installs app with dependencies"""
        # Given
        deployment_manager.portainer = mock_portainer
        deployment_manager.cloudflare = mock_cloudflare
        deployment_manager.app_deployer = mock_app_deployer

        mock_storage.state.get_server.return_value = {
            "name": "test-server",
            "ip": "1.2.3.4",
            "applications": [],  # Nothing installed
            "dns_config": {"zone_name": "test.com"}
        }
        mock_app_registry.resolve_dependencies.return_value = ["postgres", "redis", "n8n"]

        # When
        result = await deployment_manager.deploy_app("test-server", "n8n", {})

        # Then
        assert result["success"] is True
        assert result["app"] == "n8n"
        assert result["dependencies_resolved"] == ["postgres", "redis", "n8n"]
        assert len(result["apps_installed"]) == 3

        # Verify app_deployer was called for each app
        assert mock_app_deployer.deploy.call_count == 3
        # Verify sleep was called for postgres and redis (database containers)
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    @patch('time.sleep')  # Mock time.sleep to avoid 15s wait
    async def test_deploy_app_partial_installation(
        self, mock_sleep, deployment_manager, mock_storage, mock_app_registry,
        mock_portainer, mock_app_deployer
    ):
        """Test deploy_app only installs missing dependencies"""
        # Given
        deployment_manager.portainer = mock_portainer
        deployment_manager.app_deployer = mock_app_deployer

        mock_storage.state.get_server.return_value = {
            "name": "test-server",
            "ip": "1.2.3.4",
            "applications": ["postgres"],  # Postgres already installed
            "dns_config": {}
        }
        mock_app_registry.resolve_dependencies.return_value = ["postgres", "redis", "n8n"]

        # When
        result = await deployment_manager.deploy_app("test-server", "n8n", {})

        # Then
        assert result["success"] is True
        assert len(result["apps_installed"]) == 2  # Only redis + n8n
        assert result["already_installed"] == ["postgres"]

        # Verify app_deployer was called only twice (redis + n8n)
        assert mock_app_deployer.deploy.call_count == 2

    @pytest.mark.asyncio
    @patch('time.sleep')  # Mock time.sleep to avoid 15s wait
    async def test_deploy_app_failure_in_dependency(
        self, mock_sleep, deployment_manager, mock_storage, mock_app_registry,
        mock_portainer, mock_app_deployer
    ):
        """Test deploy_app stops if a dependency fails"""
        # Given
        deployment_manager.portainer = mock_portainer
        deployment_manager.app_deployer = mock_app_deployer

        # Make redis deployment fail
        async def mock_deploy_side_effect(server, app_name, config):
            if app_name == "redis":
                return {"success": False, "error": "Redis deploy failed"}
            return {"success": True}

        mock_app_deployer.deploy.side_effect = mock_deploy_side_effect

        mock_storage.state.get_server.return_value = {
            "name": "test-server",
            "applications": [],
            "dns_config": {}
        }
        mock_app_registry.resolve_dependencies.return_value = ["postgres", "redis", "n8n"]

        # When
        result = await deployment_manager.deploy_app("test-server", "n8n", {})

        # Then
        assert result["success"] is False
        assert "Failed to deploy dependency 'redis'" in result["error"]
        assert "postgres" in result["installed_before_failure"]
        assert "redis" not in result["installed_before_failure"]

    def test_create_dependency_resources_postgres(self, deployment_manager):
        """Test create_dependency_resources for PostgreSQL database"""
        # This method will be tested with actual implementation
        # For now, just verify interface exists
        pass
