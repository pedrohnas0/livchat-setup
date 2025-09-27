"""Tests for orchestrator module"""

import pytest
from unittest.mock import Mock, patch, ANY

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

    @patch('src.orchestrator.SSHKeyManager')
    @patch('src.orchestrator.HetznerProvider')
    def test_create_server_with_provider(self, mock_provider_class, mock_ssh_class, temp_config_dir):
        """Test creating server with configured provider"""
        # Setup mocks
        mock_provider = Mock()
        mock_provider.create_server.return_value = {
            "id": "12345",
            "name": "test-server",
            "ip": "1.2.3.4",
            "provider": "hetzner"
        }
        mock_provider_class.return_value = mock_provider

        # Mock SSH manager
        mock_ssh = Mock()
        mock_ssh.generate_key_pair.return_value = {
            "public_key": "ssh-ed25519 AAAA...",
            "fingerprint": "test-fingerprint"
        }
        mock_ssh.add_to_hetzner.return_value = True
        mock_ssh_class.return_value = mock_ssh

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.configure_provider("hetzner", "token")

        # Create server
        orchestrator.create_server("test-server", "cx21", "nbg1")

        # Check provider called with correct parameters including SSH key
        mock_provider.create_server.assert_called_once_with(
            "test-server", "cx21", "nbg1",
            image="ubuntu-22.04",
            ssh_keys=["test-server_key"]
        )

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

    @patch('src.orchestrator.SSHKeyManager')
    def test_setup_server_ssh_generates_key(self, mock_ssh_class, temp_config_dir, sample_server_data):
        """Test setup_server_ssh generates new SSH key"""
        mock_ssh = Mock()
        mock_ssh.key_exists.return_value = False
        mock_ssh.generate_key_pair.return_value = {"name": "test-server_key", "public": "ssh-ed25519 ..."}
        mock_ssh_class.return_value = mock_ssh

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        result = orchestrator.setup_server_ssh("test-server")

        assert result is True
        mock_ssh.generate_key_pair.assert_called_once_with("test-server_key")

    @patch('src.orchestrator.ServerSetup')
    @patch('src.orchestrator.SSHKeyManager')
    def test_setup_server_complete(self, mock_ssh_class, mock_setup_class, temp_config_dir, sample_server_data):
        """Test complete server setup flow"""
        mock_ssh = Mock()
        mock_ssh.key_exists.return_value = True
        mock_ssh_class.return_value = mock_ssh

        mock_setup = Mock()
        mock_result = Mock(success=True, step="complete", message="Success", timestamp=Mock(isoformat=lambda: "2024-01-01"), details={})
        mock_setup.full_setup.return_value = mock_result
        mock_setup_class.return_value = mock_setup

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        result = orchestrator.setup_server("test-server")

        assert result["success"] is True
        assert result["server"] == "test-server"
        mock_setup.full_setup.assert_called_once()

    @patch('src.orchestrator.ServerSetup')
    def test_install_docker(self, mock_setup_class, temp_config_dir, sample_server_data):
        """Test installing Docker on server"""
        mock_setup = Mock()
        mock_result = Mock(success=True)
        mock_setup.install_docker.return_value = mock_result
        mock_setup_class.return_value = mock_setup

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        result = orchestrator.install_docker("test-server")

        assert result is True
        mock_setup.install_docker.assert_called_once()

    @patch('src.orchestrator.ServerSetup')
    def test_init_swarm(self, mock_setup_class, temp_config_dir, sample_server_data):
        """Test initializing Docker Swarm"""
        mock_setup = Mock()
        mock_result = Mock(success=True)
        mock_setup.init_swarm.return_value = mock_result
        mock_setup_class.return_value = mock_setup

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        result = orchestrator.init_swarm("test-server", "custom_network")

        assert result is True
        mock_setup.init_swarm.assert_called_once_with(sample_server_data, "custom_network")

    @patch('src.orchestrator.ServerSetup')
    def test_deploy_traefik(self, mock_setup_class, temp_config_dir, sample_server_data):
        """Test deploying Traefik"""
        mock_setup = Mock()
        mock_result = Mock(success=True)
        mock_setup.deploy_traefik.return_value = mock_result
        mock_setup_class.return_value = mock_setup

        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        result = orchestrator.deploy_traefik("test-server", "admin@example.com")

        assert result is True
        mock_setup.deploy_traefik.assert_called_once()
        call_args = mock_setup.deploy_traefik.call_args
        assert call_args.args[1]["ssl_email"] == "admin@example.com"

    @patch('asyncio.run')
    @patch('src.orchestrator.PortainerClient')
    @patch('src.orchestrator.AnsibleRunner')
    @patch('src.security_utils.PasswordGenerator')
    def test_deploy_portainer_with_auto_init(self, mock_password_gen_class, mock_ansible_runner_class,
                                            mock_portainer_class, mock_asyncio_run,
                                            temp_config_dir, sample_server_data):
        """Test deploying Portainer with automatic admin initialization"""
        # Setup password generator mock
        mock_password_gen = Mock()
        mock_password_gen.generate_app_password.return_value = "A" * 64  # 64-char password
        mock_password_gen_class.return_value = mock_password_gen

        # Mock AnsibleRunner
        mock_ansible_runner = Mock()
        mock_ansible_result = Mock(success=True, exit_code=0, stdout="", stderr="")
        mock_ansible_runner.run_playbook.return_value = mock_ansible_result
        mock_ansible_runner_class.return_value = mock_ansible_runner

        # Create orchestrator
        orchestrator = Orchestrator(temp_config_dir)
        orchestrator.init()

        # Add server to state
        orchestrator.storage.state.add_server("test-server", sample_server_data)

        # Set admin email
        orchestrator.storage.config.set("admin_email", "admin@test.com")

        # Mock Portainer client
        mock_portainer = Mock()
        mock_portainer_class.return_value = mock_portainer

        # Mock asyncio.run to return expected values
        mock_asyncio_run.side_effect = [
            True,  # wait_for_ready returns True
            True   # initialize_admin returns True
        ]

        # Deploy Portainer
        result = orchestrator.deploy_portainer("test-server")

        # Verify deployment success
        assert result is True

        # Verify PortainerClient was created with correct parameters
        mock_portainer_class.assert_called_with(
            url="https://192.168.1.1:9443",
            username="admin",  # Portainer requires 'admin' for initial setup
            password="A" * 64  # The generated password
        )

        # Verify wait_for_ready and initialize_admin were called via asyncio.run
        assert mock_asyncio_run.call_count == 2

        # Verify password was saved to vault
        saved_password = orchestrator.storage.secrets.get_secret("portainer_password_test-server")
        assert saved_password is not None
        assert saved_password == "A" * 64

        # Verify application was added to server state
        server = orchestrator.storage.state.get_server("test-server")
        assert "portainer" in server.get("applications", [])