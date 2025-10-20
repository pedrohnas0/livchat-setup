"""
Unit tests for App Registry System
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml
import json
from typing import Dict, Any


class TestAppRegistry:
    """Test App Registry for YAML definitions"""

    @pytest.fixture
    def sample_app_yaml(self):
        """Sample app definition YAML"""
        return """
name: portainer
category: infrastructure
version: "2.19.4"
description: Container management platform

ports:
  - "9443:9443"
  - "8000:8000"

volumes:
  - portainer_data:/data

environment:
  ADMIN_PASSWORD: "{{ vault.portainer_password }}"

deploy:
  mode: global
  placement:
    constraints:
      - node.role == manager

health_check:
  endpoint: https://localhost:9443
  interval: 30s
  retries: 3

dependencies: []

dns_prefix: ptn
"""

    @pytest.fixture
    def sample_app_with_deps_yaml(self):
        """Sample app with dependencies"""
        return """
name: n8n
category: automation
version: "1.25.0"
description: Workflow automation

ports:
  - "5678:5678"

volumes:
  - n8n_data:/home/node/.n8n

environment:
  DB_TYPE: postgresdb
  DB_POSTGRESDB_DATABASE: n8n
  DB_POSTGRESDB_HOST: postgres
  DB_POSTGRESDB_PASSWORD: "{{ vault.postgres_password }}"
  EXECUTIONS_MODE: queue
  QUEUE_BULL_REDIS_HOST: redis

dependencies:
  - postgres
  - redis

dns_prefix: edt
additional_dns:
  - prefix: whk
    comment: n8n webhook
"""

    @pytest.fixture
    def app_registry(self):
        """Create AppRegistry instance"""
        from src.app_registry import AppRegistry
        return AppRegistry()

    def test_initialization(self, app_registry):
        """Test AppRegistry initialization"""
        assert app_registry is not None
        assert app_registry.apps == {}
        assert app_registry.catalog == {}

    def test_load_single_definition(self, app_registry, sample_app_yaml, tmp_path):
        """Test loading a single app definition"""
        # Create temp YAML file
        app_file = tmp_path / "portainer.yaml"
        app_file.write_text(sample_app_yaml)

        # Load definition
        app_registry.load_definition(str(app_file))

        # Verify
        assert "portainer" in app_registry.apps
        app = app_registry.apps["portainer"]
        assert app["name"] == "portainer"
        assert app["category"] == "infrastructure"
        assert app["version"] == "2.19.4"
        assert app["dns_prefix"] == "ptn"

    def test_load_definitions_from_directory(self, app_registry, sample_app_yaml,
                                           sample_app_with_deps_yaml, tmp_path):
        """Test loading multiple definitions from directory"""
        # Create directory structure
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()

        infra_dir = apps_dir / "infrastructure"
        infra_dir.mkdir()

        automation_dir = apps_dir / "automation"
        automation_dir.mkdir()

        # Create YAML files
        (infra_dir / "portainer.yaml").write_text(sample_app_yaml)
        (automation_dir / "n8n.yaml").write_text(sample_app_with_deps_yaml)

        # Load all definitions
        app_registry.load_definitions(str(apps_dir))

        # Verify
        assert len(app_registry.apps) == 2
        assert "portainer" in app_registry.apps
        assert "n8n" in app_registry.apps

    def test_get_app(self, app_registry, sample_app_yaml, tmp_path):
        """Test getting app definition"""
        # Create temp YAML file
        app_file = tmp_path / "portainer.yaml"
        app_file.write_text(sample_app_yaml)

        # Load and get
        app_registry.load_definition(str(app_file))
        app = app_registry.get_app("portainer")

        # Verify
        assert app is not None
        assert app["name"] == "portainer"

    def test_get_nonexistent_app(self, app_registry):
        """Test getting non-existent app"""
        app = app_registry.get_app("nonexistent")
        assert app is None

    def test_validate_app_schema(self, app_registry):
        """Test app definition schema validation"""
        # Valid app
        valid_app = {
            "name": "test-app",
            "category": "test",
            "version": "1.0.0",
            "description": "Test app"
        }
        result = app_registry.validate_app(valid_app)
        assert result["valid"] is True

        # Invalid app (missing required fields)
        invalid_app = {
            "name": "test-app"
            # Missing category, version, description
        }
        result = app_registry.validate_app(invalid_app)
        assert result["valid"] is False
        assert "errors" in result

    def test_resolve_dependencies(self, app_registry, sample_app_yaml,
                                 sample_app_with_deps_yaml, tmp_path):
        """Test dependency resolution"""
        # Create temp files
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()

        # Create app files
        (apps_dir / "portainer.yaml").write_text(sample_app_yaml)
        (apps_dir / "n8n.yaml").write_text(sample_app_with_deps_yaml)

        # Create dependency files (postgres and redis)
        postgres_yaml = """
name: postgres
category: database
version: "14"
description: PostgreSQL database
dependencies: []
dns_prefix: pg
"""
        redis_yaml = """
name: redis
category: database
version: "7"
description: Redis cache
dependencies: []
dns_prefix: rds
"""
        (apps_dir / "postgres.yaml").write_text(postgres_yaml)
        (apps_dir / "redis.yaml").write_text(redis_yaml)

        # Load all definitions
        app_registry.load_definitions(str(apps_dir))

        # Resolve dependencies for n8n
        deps = app_registry.resolve_dependencies("n8n")

        # Verify order: dependencies first
        assert deps == ["postgres", "redis", "n8n"]

    def test_circular_dependency_detection(self, app_registry, tmp_path):
        """Test detection of circular dependencies"""
        # Create apps with circular dependency
        app1_yaml = """
name: app1
category: test
version: "1.0"
description: App 1
dependencies:
  - app2
"""
        app2_yaml = """
name: app2
category: test
version: "1.0"
description: App 2
dependencies:
  - app1
"""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "app1.yaml").write_text(app1_yaml)
        (apps_dir / "app2.yaml").write_text(app2_yaml)

        # Load definitions
        app_registry.load_definitions(str(apps_dir))

        # Try to resolve - should detect circular dependency
        with pytest.raises(ValueError, match="Circular dependency"):
            app_registry.resolve_dependencies("app1")

    def test_generate_compose(self, app_registry, sample_app_yaml, tmp_path):
        """Test docker-compose generation"""
        # Load app
        app_file = tmp_path / "portainer.yaml"
        app_file.write_text(sample_app_yaml)
        app_registry.load_definition(str(app_file))

        # Generate compose with config
        config = {
            "admin_password": "secure_password_123",
            "network_name": "livchat_network"
        }
        compose = app_registry.generate_compose("portainer", config)

        # Verify
        assert compose is not None

        # Parse compose as YAML
        compose_data = yaml.safe_load(compose)
        assert "services" in compose_data
        assert "portainer" in compose_data["services"]

        service = compose_data["services"]["portainer"]
        assert "9443:9443" in service["ports"]
        assert "portainer_data:/data" in service["volumes"]

    def test_list_available_apps(self, app_registry, sample_app_yaml,
                                sample_app_with_deps_yaml, tmp_path):
        """Test listing available apps"""
        # Create temp files
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "portainer.yaml").write_text(sample_app_yaml)
        (apps_dir / "n8n.yaml").write_text(sample_app_with_deps_yaml)

        # Load definitions
        app_registry.load_definitions(str(apps_dir))

        # List apps
        apps = app_registry.list_apps()

        # Verify
        assert len(apps) == 2
        assert any(app["name"] == "portainer" for app in apps)
        assert any(app["name"] == "n8n" for app in apps)

    def test_list_apps_by_category(self, app_registry, sample_app_yaml,
                                  sample_app_with_deps_yaml, tmp_path):
        """Test listing apps filtered by category"""
        # Create temp files
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "portainer.yaml").write_text(sample_app_yaml)
        (apps_dir / "n8n.yaml").write_text(sample_app_with_deps_yaml)

        # Load definitions
        app_registry.load_definitions(str(apps_dir))

        # List infrastructure apps
        infra_apps = app_registry.list_apps(category="infrastructure")
        assert len(infra_apps) == 1
        assert infra_apps[0]["name"] == "portainer"

        # List automation apps
        auto_apps = app_registry.list_apps(category="automation")
        assert len(auto_apps) == 1
        assert auto_apps[0]["name"] == "n8n"

    def test_app_with_additional_dns(self, app_registry, sample_app_with_deps_yaml, tmp_path):
        """Test app with additional DNS entries (like n8n webhook)"""
        # Load app
        app_file = tmp_path / "n8n.yaml"
        app_file.write_text(sample_app_with_deps_yaml)
        app_registry.load_definition(str(app_file))

        # Get app
        app = app_registry.get_app("n8n")

        # Verify
        assert app["dns_prefix"] == "edt"
        assert "additional_dns" in app
        assert len(app["additional_dns"]) == 1
        assert app["additional_dns"][0]["prefix"] == "whk"
        assert app["additional_dns"][0]["comment"] == "n8n webhook"

    def test_invalid_yaml(self, app_registry, tmp_path):
        """Test handling of invalid YAML file"""
        # Create invalid YAML
        invalid_yaml = "invalid: yaml: content: ["
        app_file = tmp_path / "invalid.yaml"
        app_file.write_text(invalid_yaml)

        # Try to load - should not crash
        with pytest.raises(yaml.YAMLError):
            app_registry.load_definition(str(app_file))

    def test_missing_required_fields(self, app_registry, tmp_path):
        """Test validation of missing required fields"""
        # YAML missing required fields
        incomplete_yaml = """
name: incomplete
# Missing category, version, description
"""
        app_file = tmp_path / "incomplete.yaml"
        app_file.write_text(incomplete_yaml)

        # Try to load
        with pytest.raises(ValueError, match="Missing required fields"):
            app_registry.load_definition(str(app_file))

    def test_generate_compose_with_template_and_labels(self, app_registry, tmp_path):
        """
        TDD Test: Verify compose_template with Traefik labels inside deploy section
        This follows the SetupOrion pattern with 3 N8N services (editor, webhook, worker)
        """
        # Create app YAML following SetupOrion pattern with 3 services
        app_yaml = """
name: n8n
category: automation
version: "1.25.1"
description: Workflow automation platform
deploy_method: portainer
dependencies:
  - postgres
  - redis
dns_prefix: edt

compose_template: |
  version: '3.8'
  services:
    n8n_editor:
      image: n8nio/n8n:latest
      command: start
      environment:
        DB_TYPE: postgresdb
        DB_POSTGRESDB_HOST: postgres
        DB_POSTGRESDB_DATABASE: n8n_queue
        DB_POSTGRESDB_PASSWORD: "{{ vault.postgres_password }}"
        EXECUTIONS_MODE: queue
        QUEUE_BULL_REDIS_HOST: redis
        N8N_PROTOCOL: https
        N8N_HOST: "edt.{{ domain }}"
        WEBHOOK_URL: "https://whk.{{ domain }}/"
      deploy:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.n8n_editor.rule=Host(`edt.{{ domain }}`)"
          - "traefik.http.routers.n8n_editor.entrypoints=websecure"
          - "traefik.http.routers.n8n_editor.tls.certresolver=letsencrypt"
          - "traefik.http.services.n8n_editor.loadbalancer.server.port=5678"
      networks:
        - livchat_network

    n8n_webhook:
      image: n8nio/n8n:latest
      command: webhook
      environment:
        DB_TYPE: postgresdb
        DB_POSTGRESDB_HOST: postgres
        DB_POSTGRESDB_DATABASE: n8n_queue
        DB_POSTGRESDB_PASSWORD: "{{ vault.postgres_password }}"
        EXECUTIONS_MODE: queue
        QUEUE_BULL_REDIS_HOST: redis
        N8N_PROTOCOL: https
        WEBHOOK_URL: "https://whk.{{ domain }}/"
      deploy:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.n8n_webhook.rule=Host(`whk.{{ domain }}`)"
          - "traefik.http.routers.n8n_webhook.entrypoints=websecure"
          - "traefik.http.routers.n8n_webhook.tls.certresolver=letsencrypt"
          - "traefik.http.services.n8n_webhook.loadbalancer.server.port=5678"
      networks:
        - livchat_network

    n8n_worker:
      image: n8nio/n8n:latest
      command: worker --concurrency=10
      environment:
        DB_TYPE: postgresdb
        DB_POSTGRESDB_HOST: postgres
        DB_POSTGRESDB_DATABASE: n8n_queue
        DB_POSTGRESDB_PASSWORD: "{{ vault.postgres_password }}"
        EXECUTIONS_MODE: queue
        QUEUE_BULL_REDIS_HOST: redis
      networks:
        - livchat_network

  volumes:
    n8n_data:
      external: true
      name: n8n_data

  networks:
    livchat_network:
      external: true
      name: livchat_network
"""
        # Load app
        app_file = tmp_path / "n8n.yaml"
        app_file.write_text(app_yaml)
        app_registry.load_definition(str(app_file))

        # Generate compose with config
        config = {
            "postgres_password": "test_postgres_pass123",
            "domain": "lab.livchat.ai"
        }
        compose = app_registry.generate_compose("n8n", config)

        # Parse generated compose
        compose_data = yaml.safe_load(compose)

        # Verify structure
        assert "services" in compose_data

        # Verify 3 N8N services exist (SetupOrion pattern)
        assert "n8n_editor" in compose_data["services"]
        assert "n8n_webhook" in compose_data["services"]
        assert "n8n_worker" in compose_data["services"]

        editor = compose_data["services"]["n8n_editor"]
        webhook = compose_data["services"]["n8n_webhook"]
        worker = compose_data["services"]["n8n_worker"]

        # Verify commands
        assert editor["command"] == "start"
        assert webhook["command"] == "webhook"
        assert worker["command"] == "worker --concurrency=10"

        # Verify environment variables were substituted in editor
        assert editor["environment"]["DB_POSTGRESDB_PASSWORD"] == "test_postgres_pass123"
        assert editor["environment"]["N8N_HOST"] == "edt.lab.livchat.ai"
        assert editor["environment"]["WEBHOOK_URL"] == "https://whk.lab.livchat.ai/"
        assert editor["environment"]["N8N_PROTOCOL"] == "https"

        # Verify webhook environment
        assert webhook["environment"]["DB_POSTGRESDB_PASSWORD"] == "test_postgres_pass123"
        assert webhook["environment"]["WEBHOOK_URL"] == "https://whk.lab.livchat.ai/"

        # Verify worker environment
        assert worker["environment"]["DB_POSTGRESDB_PASSWORD"] == "test_postgres_pass123"
        assert worker["environment"]["EXECUTIONS_MODE"] == "queue"

        # Verify Traefik labels on editor
        assert "deploy" in editor
        assert "labels" in editor["deploy"]
        editor_labels = editor["deploy"]["labels"]
        assert "traefik.enable=true" in editor_labels
        assert "traefik.http.routers.n8n_editor.rule=Host(`edt.lab.livchat.ai`)" in editor_labels
        assert "traefik.http.routers.n8n_editor.entrypoints=websecure" in editor_labels

        # Verify Traefik labels on webhook
        assert "deploy" in webhook
        assert "labels" in webhook["deploy"]
        webhook_labels = webhook["deploy"]["labels"]
        assert "traefik.enable=true" in webhook_labels
        assert "traefik.http.routers.n8n_webhook.rule=Host(`whk.lab.livchat.ai`)" in webhook_labels
        assert "traefik.http.routers.n8n_webhook.entrypoints=websecure" in webhook_labels

        # Verify worker has no Traefik labels (backend only)
        # Worker may or may not have deploy section, but should not have Traefik labels

        # Verify volumes section
        assert "volumes" in compose_data
        assert "n8n_data" in compose_data["volumes"]
        assert compose_data["volumes"]["n8n_data"]["external"] is True

        # Verify networks section
        assert "networks" in compose_data
        assert "livchat_network" in compose_data["networks"]
        assert compose_data["networks"]["livchat_network"]["external"] is True

    def test_list_apps_filters_unlisted_by_default(self, app_registry, tmp_path):
        """Test that unlisted apps are filtered by default"""
        # Create apps with different listed values
        infrastructure_yaml = """
name: infrastructure
category: infrastructure
version: "1.0.0"
description: Essential infrastructure bundle
"""
        traefik_yaml = """
name: traefik
category: infrastructure
version: "v3.4.0"
description: Reverse proxy
listed: false
"""
        portainer_yaml = """
name: portainer
category: infrastructure
version: "2.19.4"
description: Container management
listed: false
"""
        n8n_yaml = """
name: n8n
category: automation
version: "1.25.0"
description: Workflow automation
"""
        postgres_yaml = """
name: postgres
category: database
version: "14"
description: PostgreSQL database
"""

        # Create temp files
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "infrastructure.yaml").write_text(infrastructure_yaml)
        (apps_dir / "traefik.yaml").write_text(traefik_yaml)
        (apps_dir / "portainer.yaml").write_text(portainer_yaml)
        (apps_dir / "n8n.yaml").write_text(n8n_yaml)
        (apps_dir / "postgres.yaml").write_text(postgres_yaml)

        # Load definitions
        app_registry.load_definitions(str(apps_dir))

        # Default behavior: should NOT include unlisted apps (traefik/portainer)
        apps = app_registry.list_apps()
        app_names = [app['name'] for app in apps]

        # Verify listed apps are present
        assert 'infrastructure' in app_names
        assert 'n8n' in app_names
        assert 'postgres' in app_names

        # Verify unlisted apps are filtered out
        assert 'traefik' not in app_names
        assert 'portainer' not in app_names

    def test_list_apps_shows_unlisted_when_requested(self, app_registry, tmp_path):
        """Test that unlisted apps appear with show_unlisted=True"""
        # Create apps with different listed values
        infrastructure_yaml = """
name: infrastructure
category: infrastructure
version: "1.0.0"
description: Essential infrastructure bundle
"""
        traefik_yaml = """
name: traefik
category: infrastructure
version: "v3.4.0"
description: Reverse proxy
listed: false
"""
        portainer_yaml = """
name: portainer
category: infrastructure
version: "2.19.4"
description: Container management
listed: false
"""
        n8n_yaml = """
name: n8n
category: automation
version: "1.25.0"
description: Workflow automation
"""

        # Create temp files
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "infrastructure.yaml").write_text(infrastructure_yaml)
        (apps_dir / "traefik.yaml").write_text(traefik_yaml)
        (apps_dir / "portainer.yaml").write_text(portainer_yaml)
        (apps_dir / "n8n.yaml").write_text(n8n_yaml)

        # Load definitions
        app_registry.load_definitions(str(apps_dir))

        # With show_unlisted: should include ALL apps
        apps = app_registry.list_apps(show_unlisted=True)
        app_names = [app['name'] for app in apps]

        # Verify all apps are present (including unlisted)
        assert 'infrastructure' in app_names
        assert 'traefik' in app_names
        assert 'portainer' in app_names
        assert 'n8n' in app_names