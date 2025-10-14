"""
App Registry System for managing application definitions
"""
import logging
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from .security_utils import PasswordGenerator

logger = logging.getLogger(__name__)


@dataclass
class AppDefinition:
    """Application definition data structure"""
    name: str
    category: str
    version: str
    description: str
    ports: List[str] = field(default_factory=list)
    volumes: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    deploy: Dict[str, Any] = field(default_factory=dict)
    health_check: Dict[str, Any] = field(default_factory=dict)
    dns_prefix: Optional[str] = None
    additional_dns: List[Dict[str, str]] = field(default_factory=list)
    # v0.2.0: Bundle support
    required_by_all_apps: bool = False  # If True, this app is required for all other apps
    components: List[str] = field(default_factory=list)  # List of apps in bundle (e.g., ['traefik', 'portainer'])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppDefinition":
        """Create AppDefinition from dictionary"""
        # Extract only known fields
        known_fields = {
            "name", "category", "version", "description",
            "ports", "volumes", "environment", "dependencies",
            "deploy", "health_check", "dns_prefix", "additional_dns",
            "required_by_all_apps", "components"  # v0.2.0: Bundle support
        }
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "description": self.description,
            "ports": self.ports,
            "volumes": self.volumes,
            "environment": self.environment,
            "dependencies": self.dependencies,
            "deploy": self.deploy,
            "health_check": self.health_check,
            "dns_prefix": self.dns_prefix,
            "additional_dns": self.additional_dns,
            "required_by_all_apps": self.required_by_all_apps,  # v0.2.0
            "components": self.components  # v0.2.0
        }


class AppRegistry:
    """
    System for registering and managing application definitions
    """

    # Required fields for app definition
    REQUIRED_FIELDS = ["name", "category", "version", "description"]

    def __init__(self):
        """Initialize App Registry"""
        self.apps: Dict[str, Dict[str, Any]] = {}
        self.catalog: Dict[str, Any] = {}
        logger.info("App Registry initialized")

    def load_definition(self, file_path: str) -> None:
        """
        Load a single app definition from YAML file

        Args:
            file_path: Path to YAML file

        Raises:
            yaml.YAMLError: If YAML is invalid
            ValueError: If required fields are missing
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"App definition not found: {file_path}")

        logger.info(f"Loading app definition from {file_path}")

        # Load YAML
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        # Validate required fields
        missing = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Store app definition
        app_name = data["name"]
        self.apps[app_name] = data
        logger.info(f"Loaded app: {app_name} v{data['version']}")

    def load_definitions(self, directory: str) -> None:
        """
        Load all app definitions from a directory

        Args:
            directory: Path to directory containing YAML files
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        logger.info(f"Loading app definitions from {directory}")

        # Find all YAML files recursively
        yaml_files = list(dir_path.glob("**/*.yaml")) + list(dir_path.glob("**/*.yml"))

        for yaml_file in yaml_files:
            try:
                self.load_definition(str(yaml_file))
            except Exception as e:
                logger.warning(f"Failed to load {yaml_file}: {e}")
                # Continue loading other files

        logger.info(f"Loaded {len(self.apps)} app definitions")

    def get_app(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get app definition by name

        Args:
            name: Application name

        Returns:
            App definition dict or None if not found
        """
        return self.apps.get(name)

    def validate_app(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate app definition against schema

        Args:
            app_data: App definition dictionary

        Returns:
            Validation result with status and errors
        """
        result = {
            "valid": True,
            "errors": []
        }

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in app_data:
                result["valid"] = False
                result["errors"].append(f"Missing required field: {field}")

        # Validate field types
        if "name" in app_data and not isinstance(app_data["name"], str):
            result["valid"] = False
            result["errors"].append("Field 'name' must be a string")

        if "dependencies" in app_data and not isinstance(app_data["dependencies"], list):
            result["valid"] = False
            result["errors"].append("Field 'dependencies' must be a list")

        return result

    def resolve_dependencies(self, app_name: str, _visited: Optional[set] = None) -> List[str]:
        """
        Resolve installation order based on dependencies

        Args:
            app_name: Application name to resolve
            _visited: Internal tracking of visited apps (for circular detection)

        Returns:
            Ordered list of apps to install (dependencies first)

        Raises:
            ValueError: If circular dependency detected
        """
        if _visited is None:
            _visited = set()

        # Check for circular dependency
        if app_name in _visited:
            raise ValueError(f"Circular dependency detected: {app_name}")

        _visited.add(app_name)

        # Get app definition
        app = self.get_app(app_name)
        if not app:
            logger.warning(f"App not found: {app_name}")
            return [app_name]

        # Resolve dependencies recursively
        result = []
        dependencies = app.get("dependencies", [])

        for dep in dependencies:
            # Recursively resolve dependency
            dep_list = self.resolve_dependencies(dep, _visited.copy())
            for d in dep_list:
                if d not in result:
                    result.append(d)

        # Add the app itself
        if app_name not in result:
            result.append(app_name)

        return result

    def generate_compose(self, app_name: str, config: Dict[str, Any]) -> str:
        """
        Generate docker-compose.yml for an application

        Args:
            app_name: Application name
            config: Configuration values for template

        Returns:
            Docker compose YAML string
        """
        app = self.get_app(app_name)
        if not app:
            raise ValueError(f"App not found: {app_name}")

        # Generate passwords if needed using official PasswordGenerator
        password_gen = PasswordGenerator()

        # Generate secure PostgreSQL password if not provided
        # Use only alphanumeric to avoid special char issues
        if app_name == "postgres" and "postgres_password" not in config:
            postgres_password = password_gen.generate_app_password("postgres", alphanumeric_only=True)
            config["postgres_password"] = postgres_password
            logger.info(f"Generated PostgreSQL password for deployment (alphanumeric only)")

        # Generate secure Redis password if not provided
        # Use only alphanumeric to avoid special char issues
        if app_name == "redis" and "redis_password" not in config:
            redis_password = password_gen.generate_app_password("redis", alphanumeric_only=True)
            config["redis_password"] = redis_password
            logger.info(f"Generated Redis password for deployment (alphanumeric only)")

        # Generate N8N encryption key if not provided
        # Required for N8N to encrypt sensitive data
        if app_name == "n8n" and "encryption_key" not in config:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            encryption_key = ''.join(secrets.choice(alphabet) for _ in range(32))
            config["encryption_key"] = encryption_key
            logger.info(f"Generated N8N encryption key for deployment")

        # Generate webhook_domain from domain if not provided (for N8N)
        if app_name == "n8n" and "webhook_domain" not in config and "domain" in config:
            domain = config["domain"]
            # Extract subdomain and zone from domain (e.g., "edt.lab.livchat.ai" -> "whk.lab.livchat.ai")
            parts = domain.split(".", 1)
            if len(parts) == 2:
                # Replace "edt" prefix with "whk" prefix
                config["webhook_domain"] = f"whk.{parts[1]}"
                logger.info(f"Generated webhook_domain from domain: {config['webhook_domain']}")
            else:
                # Fallback: same as domain
                config["webhook_domain"] = domain

        # If app has compose_template, use it (more complete definition)
        if "compose_template" in app:
            # Use the compose template from the YAML
            compose_str = app["compose_template"]

            # Log config keys for debugging template substitution
            logger.debug(f"Generating compose for {app_name} with config keys: {list(config.keys())}")

            # Replace template variables with actual values
            if "{{" in compose_str:
                # Replace vault references with generated or provided passwords
                # Ensure we have a password for postgres
                if "{{ vault.postgres_password }}" in compose_str:
                    if "postgres_password" not in config:
                        # Generate if missing (shouldn't happen but just in case)
                        config["postgres_password"] = password_gen.generate_app_password("postgres", alphanumeric_only=True)
                    compose_str = compose_str.replace("{{ vault.postgres_password }}",
                                                     config["postgres_password"])

                # Replace redis password if present
                if "{{ vault.redis_password }}" in compose_str:
                    if "redis_password" not in config:
                        config["redis_password"] = password_gen.generate_app_password("redis", alphanumeric_only=True)
                    compose_str = compose_str.replace("{{ vault.redis_password }}",
                                                     config["redis_password"])

                # Replace portainer password if present
                compose_str = compose_str.replace("{{ vault.portainer_password }}",
                                                 config.get("admin_password", ""))

                # Replace other template variables
                for key, value in config.items():
                    compose_str = compose_str.replace(f"{{{{ {key} }}}}", str(value))

            return compose_str

        # Fallback: Build compose structure from scratch (for backward compatibility)
        compose = {
            "version": "3.8",
            "services": {
                app_name: {
                    "image": f"{app_name}:{app.get('version', 'latest')}",
                    "ports": app.get("ports", []),
                    "volumes": app.get("volumes", []),
                    "environment": {},
                    "networks": ["livchat_network"]
                }
            },
            "networks": {
                "livchat_network": {
                    "external": True,
                    "name": config.get("network_name", "livchat_network")
                }
            }
        }

        # Add volume declarations if app has volumes
        if app.get("volumes"):
            compose["volumes"] = {}
            for volume_mount in app.get("volumes", []):
                # Extract volume name from mount (format: "volume_name:/path")
                if ":" in volume_mount:
                    volume_name = volume_mount.split(":")[0]
                    # Only add named volumes, not bind mounts (which start with /)
                    if not volume_name.startswith("/"):
                        # SetupOrion style: mark as external with same name
                        compose["volumes"][volume_name] = {
                            "external": True,
                            "name": volume_name
                        }

        # Add environment variables
        env = app.get("environment", {})
        if isinstance(env, dict):
            # Replace template variables
            for key, value in env.items():
                if isinstance(value, str) and "{{" in value:
                    # Simple template replacement
                    value = value.replace("{{ vault.portainer_password }}",
                                        config.get("admin_password", ""))
                    value = value.replace("{{ vault.postgres_password }}",
                                        config.get("postgres_password", "postgres123"))
                    value = value.replace("{{ vault.redis_password }}",
                                        config.get("redis_password", ""))
                compose["services"][app_name]["environment"][key] = value
        elif isinstance(env, list):
            # Handle list format (KEY=VALUE)
            compose["services"][app_name]["environment"] = env

        # Add deploy configuration if present
        if "deploy" in app:
            compose["services"][app_name]["deploy"] = app["deploy"]

        # Add health check if present
        if "health_check" in app:
            health = app["health_check"]
            compose["services"][app_name]["healthcheck"] = {
                "test": f"curl -f {health.get('endpoint', 'http://localhost/')} || exit 1",
                "interval": health.get("interval", "30s"),
                "retries": health.get("retries", 3),
                "start_period": "40s",
                "timeout": "10s"
            }

        # Convert to YAML
        return yaml.dump(compose, default_flow_style=False)

    def list_apps(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available applications

        Args:
            category: Optional category filter

        Returns:
            List of app definitions (summary)
        """
        apps = []

        for name, app in self.apps.items():
            # Filter by category if specified
            if category and app.get("category") != category:
                continue

            # Create summary
            summary = {
                "name": app["name"],
                "category": app.get("category", "unknown"),
                "version": app.get("version", "unknown"),
                "description": app.get("description", ""),
                "has_dependencies": bool(app.get("dependencies", []))
            }
            apps.append(summary)

        # Sort by name
        apps.sort(key=lambda x: x["name"])

        return apps

    def get_app_dns_config(self, app_name: str) -> Dict[str, Any]:
        """
        Get DNS configuration for an app

        Args:
            app_name: Application name

        Returns:
            DNS configuration with prefix and additional records
        """
        app = self.get_app(app_name)
        if not app:
            return {}

        config = {
            "dns_prefix": app.get("dns_prefix", app_name[:3].lower()),
            "additional_dns": app.get("additional_dns", [])
        }

        return config

    def save_catalog(self, file_path: str) -> None:
        """
        Save app catalog to file

        Args:
            file_path: Path to save catalog
        """
        catalog = {
            "version": "1.0.0",
            "apps": self.list_apps(),
            "total": len(self.apps),
            "categories": list(set(app.get("category", "unknown") for app in self.apps.values()))
        }

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            yaml.dump(catalog, f, default_flow_style=False)

        logger.info(f"Catalog saved to {file_path}")

    def is_bundle(self, app_name: str) -> bool:
        """
        Check if app is a bundle (has components)

        Args:
            app_name: Application name

        Returns:
            True if app is a bundle
        """
        app = self.get_app(app_name)
        if not app:
            return False
        return len(app.get("components", [])) > 0

    def is_required_by_all(self, app_name: str) -> bool:
        """
        Check if app is required by all other apps (v0.2.0)

        Args:
            app_name: Application name

        Returns:
            True if app is required for all deployments
        """
        app = self.get_app(app_name)
        if not app:
            return False
        return app.get("required_by_all_apps", False)