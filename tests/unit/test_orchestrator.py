"""Tests for orchestrator module"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.orchestrator import DependencyResolver, Orchestrator


class TestDependencyResolver:
    """Test dependency resolution logic"""

    def setup_method(self):
        """Setup for each test"""
        self.resolver = DependencyResolver()

    def test_resolve_simple_dependency(self):
        """Test resolving a single app with dependencies"""
        apps = ["n8n"]
        result = self.resolver.resolve_install_order(apps)

        # n8n needs postgres and redis
        assert "postgres" in result
        assert "redis" in result
        assert "n8n" in result

        # Dependencies should come before n8n
        assert result.index("postgres") < result.index("n8n")
        assert result.index("redis") < result.index("n8n")

    def test_resolve_multiple_apps_shared_deps(self):
        """Test multiple apps that share dependencies"""
        apps = ["n8n", "chatwoot"]
        result = self.resolver.resolve_install_order(apps)

        # Both need postgres and redis, but should appear only once
        assert result.count("postgres") == 1
        assert result.count("redis") == 1

        # Dependencies before apps
        assert result.index("postgres") < result.index("n8n")
        assert result.index("postgres") < result.index("chatwoot")
        assert result.index("redis") < result.index("n8n")
        assert result.index("redis") < result.index("chatwoot")

    def test_resolve_no_dependencies(self):
        """Test app with no dependencies"""
        apps = ["nginx"]  # Not in dependencies dict
        result = self.resolver.resolve_install_order(apps)

        assert result == ["nginx"]

    def test_resolve_nested_dependencies(self):
        """Test apps with nested/chained dependencies"""
        # Note: Current implementation doesn't have nested deps, but test the concept
        apps = ["wordpress", "n8n"]
        result = self.resolver.resolve_install_order(apps)

        # Should include all unique dependencies
        assert "mysql" in result  # for wordpress
        assert "postgres" in result  # for n8n
        assert "redis" in result  # for n8n

    def test_empty_list_returns_empty(self):
        """Test that empty input returns empty output"""
        result = self.resolver.resolve_install_order([])
        assert result == []

    def test_unknown_app_handled_gracefully(self):
        """Test that unknown apps are included without error"""
        apps = ["unknown_app", "n8n"]
        result = self.resolver.resolve_install_order(apps)

        assert "unknown_app" in result
        assert "n8n" in result
        assert "postgres" in result  # n8n dependency

    def test_get_dependencies(self):
        """Test getting dependencies for an app"""
        deps = self.resolver.get_dependencies("n8n")
        assert deps == ["postgres", "redis"]

        deps = self.resolver.get_dependencies("unknown")
        assert deps == []

    def test_validate_dependencies(self):
        """Test validating dependencies for an app"""
        result = self.resolver.validate_dependencies("n8n")

        assert result["valid"] is True
        assert result["app"] == "n8n"
        assert result["dependencies"] == ["postgres", "redis"]

    def test_configure_dependency(self):
        """Test configuring a dependency for parent app"""
        config = self.resolver.configure_dependency("n8n", "postgres")

        assert config["parent"] == "n8n"
        assert config["dependency"] == "postgres"
        assert config["database"] == "n8n_queue"
        assert config["user"] == "n8n_user"

        # Test redis config
        config = self.resolver.configure_dependency("n8n", "redis")
        assert config["db"] == 1


class TestOrchestrator:
    """Test main orchestrator"""

    def test_init_loads_existing_config(self, temp_config_dir, sample_config):
        """Test that init loads existing configuration"""
        # Create existing config
        config_file = temp_config_dir / "config.yaml"
        config_file.parent.mkdir(exist_ok=True)
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)

        orchestrator = Orchestrator(temp_config_dir)

        # Should have loaded the config
        assert orchestrator.storage.config.get("provider") == "hetzner"

    def test_init_creates_storage(self, temp_config_dir):
        """Test that init creates all storage components"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        assert (temp_config_dir / "config.yaml").exists()
        assert (temp_config_dir / "state.json").exists()
        assert (temp_config_dir / "credentials.vault").exists()

    @patch('src.orchestrator.HetznerProvider')
    def test_configure_provider_saves_token(self, mock_provider_class, temp_config_dir):
        """Test configuring provider saves token securely"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        orchestrator.configure_provider("hetzner", "test_token_123")

        # Check token saved in secrets
        saved_token = orchestrator.storage.secrets.get_secret("hetzner_token")
        assert saved_token == "test_token_123"

        # Check provider set in config
        provider = orchestrator.storage.config.get("provider")
        assert provider == "hetzner"

        # Check provider initialized
        mock_provider_class.assert_called_once_with("test_token_123")

    def test_configure_unsupported_provider_raises(self, temp_config_dir):
        """Test configuring unsupported provider raises error"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        with pytest.raises(ValueError) as exc:
            orchestrator.configure_provider("unsupported", "token")

        assert "Unsupported provider" in str(exc.value)

    @patch('src.orchestrator.HetznerProvider')
    def test_create_server_with_provider(self, mock_provider_class, temp_config_dir):
        """Test creating server with configured provider"""
        # Setup mock
        mock_provider = Mock()
        mock_provider.create_server.return_value = {
            "id": "12345",
            "name": "test-server",
            "ip": "1.2.3.4",
            "provider": "hetzner"
        }
        mock_provider_class.return_value = mock_provider

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.configure_provider("hetzner", "token")

        # Create server
        server = orchestrator.create_server("test-server", "cx21", "nbg1")

        # Check provider called
        mock_provider.create_server.assert_called_once_with("test-server", "cx21", "nbg1")

        # Check server saved to state
        saved = orchestrator.storage.state.get_server("test-server")
        assert saved["ip"] == "1.2.3.4"

    def test_create_server_without_provider_fails(self, temp_config_dir):
        """Test creating server without provider raises error"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        with pytest.raises(RuntimeError) as exc:
            orchestrator.create_server("test", "cx21", "nbg1")

        # Default config has hetzner provider, but no token
        assert "Hetzner token not found" in str(exc.value)

    def test_list_servers_from_state(self, temp_config_dir, sample_server_data):
        """Test listing servers from state"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        # Add servers to state
        orchestrator.storage.state.add_server("server1", sample_server_data)
        orchestrator.storage.state.add_server("server2", sample_server_data)

        servers = orchestrator.list_servers()
        assert len(servers) == 2
        assert "server1" in servers
        assert "server2" in servers

    def test_get_server_by_name(self, temp_config_dir, sample_server_data):
        """Test getting server by name"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        server = orchestrator.get_server("test-server")
        assert server["ip"] == "192.168.1.1"

    def test_get_nonexistent_server(self, temp_config_dir):
        """Test getting nonexistent server returns None"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        server = orchestrator.get_server("nonexistent")
        assert server is None

    @patch('src.orchestrator.HetznerProvider')
    def test_delete_server_updates_state(self, mock_provider_class, temp_config_dir, sample_server_data):
        """Test deleting server updates state"""
        # Setup mock
        mock_provider = Mock()
        mock_provider.delete_server.return_value = True
        mock_provider_class.return_value = mock_provider

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.secrets.set_secret("hetzner_token", "test_token")

        # Add server to state
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        # Delete server
        result = orchestrator.delete_server("test-server")

        assert result is True
        assert orchestrator.get_server("test-server") is None

    def test_delete_nonexistent_server(self, temp_config_dir):
        """Test deleting nonexistent server returns False"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        result = orchestrator.delete_server("nonexistent")
        assert result is False

    def test_deploy_apps_resolves_dependencies(self, temp_config_dir, sample_server_data):
        """Test deploying apps resolves dependencies"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        result = orchestrator.deploy_apps("test-server", ["n8n", "wordpress"])

        # Check dependencies resolved
        assert "postgres" in result["install_order"]
        assert "redis" in result["install_order"]
        assert "mysql" in result["install_order"]

        # Check order
        order = result["install_order"]
        assert order.index("postgres") < order.index("n8n")

    def test_deploy_to_nonexistent_server(self, temp_config_dir):
        """Test deploying to nonexistent server raises error"""
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        with pytest.raises(ValueError) as exc:
            orchestrator.deploy_apps("nonexistent", ["n8n"])

        assert "Server nonexistent not found" in str(exc.value)

    def test_validate_app_dependencies(self, temp_config_dir):
        """Test validating app dependencies"""
        orchestrator = Orchestrator(temp_config_dir)
        result = orchestrator.validate_app_dependencies("n8n")

        assert result["valid"] is True
        assert result["app"] == "n8n"
        assert "postgres" in result["dependencies"]