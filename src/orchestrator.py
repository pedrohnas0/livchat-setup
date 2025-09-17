"""Core orchestration and dependency resolution for LivChat Setup"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from .storage import StorageManager
    from .providers.hetzner import HetznerProvider
except ImportError:
    # For direct execution
    from storage import StorageManager
    from providers.hetzner import HetznerProvider

logger = logging.getLogger(__name__)


class DependencyResolver:
    """Resolves and manages application dependencies"""

    def __init__(self):
        """Initialize DependencyResolver"""
        # Hardcoded dependencies for now - will load from YAML later
        self.dependencies = {
            "n8n": ["postgres", "redis"],
            "chatwoot": ["postgres", "redis", "sidekiq"],
            "wordpress": ["mysql"],
            "grafana": ["postgres"],
            "nocodb": ["postgres"],
        }

    def resolve_install_order(self, apps: List[str]) -> List[str]:
        """
        Resolve installation order based on dependencies

        Args:
            apps: List of applications to install

        Returns:
            Ordered list of applications to install (dependencies first)
        """
        resolved = []
        to_resolve = apps.copy()

        while to_resolve:
            # Find apps with no unresolved dependencies
            can_install = []
            for app in to_resolve:
                deps = self.dependencies.get(app, [])
                # Check if all dependencies are resolved or not in our install list
                if all(dep in resolved or dep not in apps for dep in deps):
                    can_install.append(app)

            if not can_install:
                # Circular dependency or missing dependency
                logger.warning(f"Cannot resolve dependencies for: {to_resolve}")
                break

            # Add resolvable apps to resolved list
            for app in can_install:
                if app not in resolved:
                    # First add the dependencies that are in our install list
                    for dep in self.dependencies.get(app, []):
                        if dep in apps and dep not in resolved:
                            resolved.append(dep)
                    # Then add the app itself
                    resolved.append(app)
                    to_resolve.remove(app)

        return resolved

    def validate_dependencies(self, app: str) -> Dict[str, Any]:
        """
        Validate if an application's dependencies can be satisfied

        Args:
            app: Application name

        Returns:
            Validation result with status and details
        """
        result = {
            "valid": True,
            "app": app,
            "dependencies": [],
            "missing": [],
            "errors": []
        }

        deps = self.dependencies.get(app, [])
        result["dependencies"] = deps

        # For now, just return the dependencies
        # In the future, check if they're installed or available

        return result

    def get_dependencies(self, app: str) -> List[str]:
        """
        Get dependencies for an application

        Args:
            app: Application name

        Returns:
            List of dependencies
        """
        return self.dependencies.get(app, [])

    def configure_dependency(self, parent_app: str, dependency: str) -> Dict[str, Any]:
        """
        Configure a dependency for a parent application

        Args:
            parent_app: Parent application name
            dependency: Dependency name

        Returns:
            Configuration details
        """
        # This will be expanded to handle actual configuration
        # For now, return a placeholder
        config = {
            "parent": parent_app,
            "dependency": dependency,
            "status": "configured"
        }

        # Example configurations
        if dependency == "postgres" and parent_app == "n8n":
            config["database"] = "n8n_queue"
            config["user"] = "n8n_user"
        elif dependency == "redis" and parent_app == "n8n":
            config["db"] = 1

        return config


class Orchestrator:
    """Main orchestrator for LivChat Setup system"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize Orchestrator

        Args:
            config_dir: Custom config directory (default: ~/.livchat)
        """
        self.config_dir = config_dir or Path.home() / ".livchat"
        self.storage = StorageManager(self.config_dir)
        self.resolver = DependencyResolver()
        self.provider = None

        # Auto-load existing data if available
        if self.config_dir.exists():
            try:
                self.storage.config.load()
                self.storage.state.load()
                logger.info("Loaded existing configuration and state")
            except Exception as e:
                logger.debug(f"Could not load existing data: {e}")

        logger.info(f"Orchestrator initialized with config dir: {self.config_dir}")

    def init(self) -> None:
        """Initialize configuration directory and files"""
        logger.info("Initializing LivChat Setup...")
        self.storage.init()
        logger.info("Initialization complete")

    def configure_provider(self, provider_name: str, token: str) -> None:
        """
        Configure a cloud provider

        Args:
            provider_name: Name of the provider (e.g., 'hetzner')
            token: API token for the provider
        """
        logger.info(f"Configuring provider: {provider_name}")

        # Save token securely
        self.storage.secrets.set_secret(f"{provider_name}_token", token)

        # Update config
        self.storage.config.set("provider", provider_name)

        # Initialize provider
        if provider_name == "hetzner":
            self.provider = HetznerProvider(token)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        logger.info(f"Provider {provider_name} configured successfully")

    def create_server(self, name: str, server_type: str, region: str) -> Dict[str, Any]:
        """
        Create a new server

        Args:
            name: Server name
            server_type: Server type (e.g., 'cx21')
            region: Region/location (e.g., 'nbg1')

        Returns:
            Server information dictionary
        """
        if not self.provider:
            # Try to load provider from config
            provider_name = self.storage.config.get("provider")
            if provider_name == "hetzner":
                token = self.storage.secrets.get_secret("hetzner_token")
                if not token:
                    raise RuntimeError("Hetzner token not found. Run configure_provider first.")
                self.provider = HetznerProvider(token)
            else:
                raise RuntimeError("No provider configured. Run configure_provider first.")

        logger.info(f"Creating server: {name} ({server_type} in {region})")

        # Create server via provider
        server = self.provider.create_server(name, server_type, region)

        # Save to state
        self.storage.state.add_server(name, server)

        logger.info(f"Server {name} created successfully: {server['ip']}")
        return server

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all managed servers"""
        return self.storage.state.list_servers()

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server by name"""
        return self.storage.state.get_server(name)

    def delete_server(self, name: str) -> bool:
        """
        Delete a server

        Args:
            name: Server name

        Returns:
            True if successful
        """
        logger.info(f"Deleting server: {name}")

        server = self.storage.state.get_server(name)
        if not server:
            logger.warning(f"Server {name} not found in state")
            return False

        if not self.provider:
            # Try to load provider from config
            provider_name = server.get("provider", self.storage.config.get("provider"))
            if provider_name == "hetzner":
                token = self.storage.secrets.get_secret("hetzner_token")
                if token:
                    self.provider = HetznerProvider(token)

        # Delete from provider
        if self.provider and "id" in server:
            try:
                self.provider.delete_server(server["id"])
            except Exception as e:
                logger.error(f"Failed to delete server from provider: {e}")

        # Remove from state regardless
        self.storage.state.remove_server(name)

        logger.info(f"Server {name} deleted successfully")
        return True

    def deploy_apps(self, server_name: str, apps: List[str]) -> Dict[str, Any]:
        """
        Deploy applications to a server with dependency resolution

        Args:
            server_name: Target server name
            apps: List of applications to deploy

        Returns:
            Deployment result
        """
        server = self.get_server(server_name)
        if not server:
            raise ValueError(f"Server {server_name} not found")

        # Resolve installation order
        install_order = self.resolver.resolve_install_order(apps)

        logger.info(f"Resolved installation order: {install_order}")

        # For now, just return the plan
        # In the future, this will actually deploy
        result = {
            "server": server_name,
            "requested_apps": apps,
            "install_order": install_order,
            "status": "planned"
        }

        # Add to deployment history
        self.storage.state.add_deployment({
            "server": server_name,
            "apps": install_order,
            "status": "planned"
        })

        return result

    def validate_app_dependencies(self, app: str) -> Dict[str, Any]:
        """
        Validate application dependencies

        Args:
            app: Application name

        Returns:
            Validation result
        """
        return self.resolver.validate_dependencies(app)


# Compatibility alias for migration period
LivChatSetup = Orchestrator

__all__ = ["Orchestrator", "DependencyResolver", "LivChatSetup"]