"""Server Setup orchestration module"""

import logging
import socket
import time
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SetupResult:
    """Result from a setup step"""
    success: bool
    step: str
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict = field(default_factory=dict)


class ServerSetup:
    """Orchestrates complete server setup process"""

    def __init__(self, ansible_runner: Any, storage=None):
        """
        Initialize ServerSetup

        Args:
            ansible_runner: AnsibleRunner instance for executing playbooks
            storage: Optional StorageManager instance for password storage
        """
        self.ansible_runner = ansible_runner
        self.setup_status = {}  # Track setup status per server
        self.storage = storage  # Storage manager for secrets

        # Define playbook paths
        self.playbook_dir = Path(__file__).parent.parent / "ansible" / "playbooks"

        # Initialize AppRegistry for YAML definitions
        from .app_registry import AppRegistry
        self.app_registry = AppRegistry()

        # Load infrastructure definitions
        definitions_dir = Path(__file__).parent.parent / "apps" / "definitions"
        if definitions_dir.exists():
            try:
                self.app_registry.load_definitions(str(definitions_dir))
                logger.info(f"Loaded {len(self.app_registry.apps)} stack definitions")
            except Exception as e:
                logger.warning(f"Could not load app definitions: {e}")

    def check_port_open(self, host: str, port: int = 22, timeout: float = 5) -> bool:
        """
        Check if a port is open on the host

        Args:
            host: Host IP address
            port: Port to check (default: 22 for SSH)
            timeout: Connection timeout in seconds

        Returns:
            True if port is open, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Port check failed: {e}")
            return False

    def wait_for_ssh(self, server: Dict, timeout: int = 120, check_interval: int = 5) -> bool:
        """
        Wait for SSH to become available on server

        Args:
            server: Server configuration dict with 'ip' key
            timeout: Maximum time to wait in seconds
            check_interval: Interval between checks in seconds

        Returns:
            True if SSH is ready, False if timeout
        """
        host = server.get("ip")
        if not host:
            logger.error("Server IP not found")
            return False

        logger.info(f"Waiting for SSH to be ready on {host}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.check_port_open(host, 22):
                logger.info(f"SSH port is open on {host}")
                # Additional small delay for SSH daemon to fully initialize
                time.sleep(2)
                return True

            elapsed = int(time.time() - start_time)
            logger.debug(f"SSH not ready yet on {host} ({elapsed}s elapsed)")
            time.sleep(check_interval)

        logger.warning(f"SSH did not become ready on {host} within {timeout} seconds")
        return False

    def test_connectivity(self, server: Dict) -> bool:
        """
        Test Ansible connectivity using ping module

        Args:
            server: Server configuration dict

        Returns:
            True if Ansible can connect, False otherwise
        """
        logger.info(f"Testing Ansible connectivity to {server['name']} ({server['ip']})")

        # Create inventory
        inventory = self.create_inventory(server)

        # Log inventory details for debugging
        import json
        logger.debug(f"Inventory for ping test: {json.dumps(inventory, indent=2)}")

        # Run ping module
        result = self.ansible_runner.run_adhoc(
            host=server["ip"],
            module="ping",
            user=server.get("user", "root"),
            ssh_key=server.get("ssh_key")
        )

        if result.success:
            logger.info(f"✅ Ansible ping successful to {server['name']}")
        else:
            logger.error(f"❌ Ansible ping failed to {server['name']}")
            logger.error(f"   Exit code: {result.exit_code}")
            if result.stderr:
                logger.error(f"   Error: {result.stderr[:500]}")

        return result.success

    def create_inventory(self, server: Dict) -> Dict:
        """
        Create inventory from server configuration

        Args:
            server: Server configuration dict

        Returns:
            Ansible inventory dict
        """
        # Get SSH key path from ansible_runner's ssh_manager if available
        ssh_key_name = server.get('ssh_key', f"{server['name']}_key")

        # Try to get the path from SSH manager first
        ssh_key_path = None
        if self.ansible_runner and hasattr(self.ansible_runner, 'ssh_manager') and self.ansible_runner.ssh_manager:
            try:
                ssh_key_path = str(self.ansible_runner.ssh_manager.get_private_key_path(ssh_key_name))
                logger.debug(f"Got SSH key path from manager: {ssh_key_path}")
            except Exception as e:
                logger.debug(f"Could not get key from manager: {e}")

        # Fallback to default path if not found
        if not ssh_key_path:
            from os.path import expanduser
            ssh_key_path = expanduser(f"~/.livchat/ssh_keys/{ssh_key_name}")
            logger.debug(f"Using default SSH key path: {ssh_key_path}")

        inventory = {
            "all": {
                "hosts": {
                    server["name"]: {
                        "ansible_host": server["ip"],
                        "ansible_user": server.get("user", "root"),
                        "ansible_ssh_private_key_file": ssh_key_path,
                        "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
                        "ansible_python_interpreter": "/usr/bin/python3"
                    }
                }
            }
        }

        logger.debug(f"Created inventory for {server['name']}: IP={server['ip']}, Key={ssh_key_path}")
        return inventory

    def validate_server_config(self, server: Dict) -> bool:
        """
        Validate server configuration has required fields

        Args:
            server: Server configuration

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["name", "ip", "ssh_key"]
        return all(field in server for field in required_fields)

    def update_status(self, server_name: str, step: str, success: bool, message: str = ""):
        """
        Update setup status for a server

        Args:
            server_name: Name of the server
            step: Setup step name
            success: Whether step succeeded
            message: Optional status message
        """
        if server_name not in self.setup_status:
            self.setup_status[server_name] = {
                "completed_steps": [],
                "current_step": None,
                "last_update": None
            }

        status = self.setup_status[server_name]

        if success:
            if step not in status["completed_steps"]:
                status["completed_steps"].append(step)
            status["current_step"] = None
        else:
            status["current_step"] = step

        status["last_update"] = datetime.now().isoformat()
        status["last_message"] = message

        logger.info(f"Server {server_name}: Step '{step}' - {'Success' if success else 'Failed'}")

    def get_setup_status(self, server_name: str) -> Dict:
        """
        Get current setup status for a server

        Args:
            server_name: Name of the server

        Returns:
            Status dictionary
        """
        return self.setup_status.get(server_name, {
            "completed_steps": [],
            "current_step": None,
            "last_update": None
        })

    def setup_base(self, server: Dict, retries: int = 1) -> SetupResult:
        """
        Execute base setup playbook

        Args:
            server: Server configuration
            retries: Number of retry attempts

        Returns:
            SetupResult
        """
        if not self.validate_server_config(server):
            return SetupResult(
                success=False,
                step="base-setup",
                message="Invalid server configuration"
            )

        logger.info(f"Starting base setup for {server['name']}")

        playbook_path = self.playbook_dir / "base-setup.yml"
        inventory = self.create_inventory(server)

        extra_vars = {
            "server_name": server["name"],
            "timezone": server.get("timezone", "America/Sao_Paulo")
        }

        for attempt in range(retries):
            result = self.ansible_runner.run_playbook(
                playbook_path=str(playbook_path),
                inventory=inventory,
                extra_vars=extra_vars
            )

            if result.success:
                self.update_status(server["name"], "base-setup", True, "Base setup completed")
                return SetupResult(
                    success=True,
                    step="base-setup",
                    message="Base setup completed successfully",
                    details={"attempt": attempt + 1}
                )

        self.update_status(server["name"], "base-setup", False, "Base setup failed")
        return SetupResult(
            success=False,
            step="base-setup",
            message=f"Base setup failed after {retries} attempts",
            details={"stderr": result.stderr if result else ""}
        )

    def install_docker(self, server: Dict) -> SetupResult:
        """
        Install Docker on the server

        Args:
            server: Server configuration

        Returns:
            SetupResult
        """
        logger.info(f"Installing Docker on {server['name']}")

        playbook_path = self.playbook_dir / "docker-install.yml"
        inventory = self.create_inventory(server)

        result = self.ansible_runner.run_playbook(
            playbook_path=str(playbook_path),
            inventory=inventory
        )

        success = result.success
        self.update_status(server["name"], "docker-install", success,
                         "Docker installed" if success else "Docker installation failed")

        return SetupResult(
            success=success,
            step="docker-install",
            message="Docker installed successfully" if success else "Docker installation failed",
            details={"exit_code": result.exit_code}
        )

    def init_swarm(self, server: Dict, network_name: str = "livchat_network") -> SetupResult:
        """
        Initialize Docker Swarm

        Args:
            server: Server configuration
            network_name: Name for the overlay network

        Returns:
            SetupResult
        """
        logger.info(f"Initializing Docker Swarm on {server['name']}")

        playbook_path = self.playbook_dir / "swarm-init.yml"
        inventory = self.create_inventory(server)

        extra_vars = {
            "swarm_network": network_name
        }

        result = self.ansible_runner.run_playbook(
            playbook_path=str(playbook_path),
            inventory=inventory,
            extra_vars=extra_vars
        )

        success = result.success
        self.update_status(server["name"], "swarm-init", success,
                         "Swarm initialized" if success else "Swarm initialization failed")

        return SetupResult(
            success=success,
            step="swarm-init",
            message="Docker Swarm initialized successfully" if success else "Swarm initialization failed",
            details={"network": network_name}
        )

    def deploy_infrastructure_from_yaml(self, server: Dict, stack_name: str, config: Optional[Dict] = None) -> SetupResult:
        """
        Deploy infrastructure stack from YAML definition using Ansible

        Args:
            server: Server configuration
            stack_name: Name of the stack to deploy (e.g., 'traefik', 'portainer')
            config: Optional configuration

        Returns:
            SetupResult object
        """
        logger.info(f"Deploying {stack_name} from YAML definition on {server['name']}")

        # Get stack definition from registry
        stack_def = self.app_registry.get_app(stack_name)
        if not stack_def:
            logger.warning(f"No YAML definition found for {stack_name}")
            return SetupResult(
                success=False,
                step=f"{stack_name}-deploy",
                message=f"Stack definition not found: {stack_name}"
            )

        # Verify it's an infrastructure component (ansible deployment)
        if stack_def.get('deploy_method') != 'ansible':
            logger.warning(f"{stack_name} is not configured for Ansible deployment")
            return SetupResult(
                success=False,
                step=f"{stack_name}-deploy",
                message=f"{stack_name} should be deployed via {stack_def.get('deploy_method', 'unknown')}"
            )

        config = config or {}
        inventory = self.create_inventory(server)

        # Prepare variables
        extra_vars = {
            "stack_name": stack_name,
            "server_ip": server["ip"],
            "ansible_host": server["ip"],
            "ansible_user": "root"
        }

        # Add variables from config and YAML definition
        if 'variables' in stack_def:
            for var_name, var_def in stack_def['variables'].items():
                if var_name in config:
                    extra_vars[var_name] = config[var_name]
                elif 'default' in var_def:
                    extra_vars[var_name] = var_def['default']
                elif var_def.get('required', False):
                    return SetupResult(
                        success=False,
                        step=f"{stack_name}-deploy",
                        message=f"Required variable '{var_name}' not provided"
                    )

        # Add any additional config values
        for key, value in config.items():
            if key not in extra_vars:
                extra_vars[key] = value

        # Get compose content
        compose_content = stack_def.get('compose', '')
        if not compose_content:
            return SetupResult(
                success=False,
                step=f"{stack_name}-deploy",
                message=f"No compose definition found for {stack_name}"
            )

        # Substitute variables in compose content
        for key, value in extra_vars.items():
            # Replace both ${KEY} and ${key} patterns
            compose_content = compose_content.replace(f"${{{key.upper()}}}", str(value))
            compose_content = compose_content.replace(f"${{{key}}}", str(value))
            # Also handle patterns with defaults like ${KEY:-default}
            pattern = re.compile(rf'\${{\s*{re.escape(key)}\s*:-[^}}]*\}}')
            compose_content = pattern.sub(str(value), compose_content)
            pattern_upper = re.compile(rf'\${{\s*{re.escape(key.upper())}\s*:-[^}}]*\}}')
            compose_content = pattern_upper.sub(str(value), compose_content)

        # Create temporary compose file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(compose_content)
            stack_file = f.name

        extra_vars["stack_file"] = stack_file

        # Use generic stack deployment playbook
        playbook_path = self.playbook_dir / "generic-stack-deploy.yml"

        # If generic playbook doesn't exist, fall back to specific one
        if not playbook_path.exists():
            specific_playbook = self.playbook_dir / f"{stack_name}-deploy.yml"
            if specific_playbook.exists():
                playbook_path = specific_playbook
            else:
                # Clean up temp file
                try:
                    os.remove(stack_file)
                except:
                    pass
                return SetupResult(
                    success=False,
                    step=f"{stack_name}-deploy",
                    message=f"No deployment playbook found for {stack_name}"
                )

        result = self.ansible_runner.run_playbook(
            playbook_path=str(playbook_path),
            inventory=inventory,
            extra_vars=extra_vars
        )

        # Clean up temp file
        try:
            os.remove(stack_file)
        except:
            pass

        success = result.success
        self.update_status(server["name"], f"{stack_name}-deploy", success,
                         f"{stack_name} deployed" if success else f"{stack_name} deployment failed")

        return SetupResult(
            success=success,
            step=f"{stack_name}-deploy",
            message=f"{stack_name} deployed successfully" if success else f"{stack_name} deployment failed",
            details=result.details if hasattr(result, 'details') else {}
        )

    def deploy_traefik(self, server: Dict, config: Optional[Dict] = None) -> SetupResult:
        """
        Deploy Traefik reverse proxy

        Args:
            server: Server configuration
            config: Traefik configuration options

        Returns:
            SetupResult
        """
        # Try YAML-based deployment first
        result = self.deploy_infrastructure_from_yaml(server, "traefik", config)
        if result.success or "Stack definition not found" not in result.message:
            return result

        # Fall back to original playbook-based deployment
        logger.info(f"Deploying Traefik on {server['name']} using legacy playbook")

        playbook_path = self.playbook_dir / "traefik-deploy.yml"
        inventory = self.create_inventory(server)

        config = config or {}
        extra_vars = {
            "ssl_email": config.get("ssl_email", "admin@example.com"),
            "swarm_network": config.get("network_name", "livchat_network"),
            "traefik_version": config.get("traefik_version", "v3.2.3")
        }

        result = self.ansible_runner.run_playbook(
            playbook_path=str(playbook_path),
            inventory=inventory,
            extra_vars=extra_vars
        )

        success = result.success
        self.update_status(server["name"], "traefik-deploy", success,
                         "Traefik deployed" if success else "Traefik deployment failed")

        return SetupResult(
            success=success,
            step="traefik-deploy",
            message="Traefik deployed successfully" if success else "Traefik deployment failed",
            details={"ssl_email": extra_vars["ssl_email"]}
        )

    def deploy_portainer(self, server: Dict, config: Optional[Dict] = None) -> SetupResult:
        """
        Deploy Portainer CE management platform

        Args:
            server: Server configuration
            config: Portainer configuration options

        Returns:
            SetupResult
        """
        # Generate secure password if not provided
        config = config or {}
        if "portainer_admin_password" not in config:
            from .security_utils import PasswordGenerator, CredentialsManager

            if self.storage:
                # Use CredentialsManager for proper vault integration
                cred_manager = CredentialsManager(self.storage)
                credentials = cred_manager.generate_app_credentials(
                    app_name="portainer",
                    username="admin",
                    alphanumeric_only=True  # Use only alphanumeric chars to avoid shell/Docker issues
                )
                config["portainer_admin_password"] = credentials.password

                # Save complete credentials to vault (CredentialsManager does this automatically)
                cred_manager.save_credentials(credentials)

                # Also save in the old format for backward compatibility
                self.storage.secrets.set_secret(
                    f"portainer_password_{server['name']}",
                    credentials.password
                )
                logger.info("Generated secure 64-character alphanumeric password for Portainer and saved to vault")
            else:
                # Fallback if no storage available
                password_gen = PasswordGenerator()
                config["portainer_admin_password"] = password_gen.generate_app_password(
                    "portainer",
                    alphanumeric_only=True
                )
                logger.warning("No storage manager available, password won't be saved in vault")

        # Save admin email for future use (OAuth, notifications, etc)
        if "admin_email" not in config and self.storage:
            config["admin_email"] = self.storage.config.get("admin_email", "pedrohnas0@gmail.com")

        # Handle domain for Traefik - ensure PORTAINER_DOMAIN is set
        if "dns_domain" in config:
            config["portainer_domain"] = config["dns_domain"]  # Map dns_domain to portainer_domain
            logger.info(f"Setting Portainer domain for Traefik: {config['portainer_domain']}")

        # Remove password from config before passing to Ansible (SetupOrion style)
        # Password will be set via API after deployment
        config_for_ansible = config.copy()
        if "portainer_admin_password" in config_for_ansible:
            del config_for_ansible["portainer_admin_password"]
            logger.info("Password removed from Ansible config - will be set via API after deployment")

        # Try YAML-based deployment first
        result = self.deploy_infrastructure_from_yaml(server, "portainer", config_for_ansible)
        if result.success:
            # Log access info on success
            logger.info(f"Portainer deployed successfully on {server['name']}")
            logger.info(f"Access URL: https://{server['ip']}:{config.get('portainer_https_port', 9443)}")
            logger.info(f"Username: admin")
            logger.info("Password: [Stored securely in Vault]")
            return result
        elif "Stack definition not found" not in result.message:
            return result

        # Fall back to original playbook-based deployment
        logger.info(f"Deploying Portainer on {server['name']} using legacy playbook")

        playbook_path = self.playbook_dir / "portainer-deploy.yml"
        inventory = self.create_inventory(server)

        extra_vars = {
            "portainer_version": config.get("portainer_version", "2.19.4"),
            "portainer_https_port": config.get("portainer_https_port", 9443),
            "portainer_edge_port": config.get("portainer_edge_port", 8000),
            "portainer_admin_password": config.get("portainer_admin_password"),
            "portainer_admin_email": config.get("portainer_admin_email", "admin@example.com"),
            "portainer_data_path": config.get("portainer_data_path", "/var/lib/portainer"),
            "dns_domain": config.get("dns_domain", "")  # Domain for Traefik routing
        }

        result = self.ansible_runner.run_playbook(
            playbook_path=str(playbook_path),
            inventory=inventory,
            extra_vars=extra_vars
        )

        success = result.success
        self.update_status(server["name"], "portainer-deploy", success,
                         "Portainer deployed" if success else "Portainer deployment failed")

        if success:
            logger.info(f"Portainer deployed successfully on {server['name']}")
            logger.info(f"Access URL: https://{server['ip']}:{extra_vars['portainer_https_port']}")
            logger.info(f"Username: {extra_vars.get('portainer_admin_username', 'admin')}")
            logger.info("Password: [Stored securely in Vault]")

        return SetupResult(
            success=success,
            step="portainer-deploy",
            message="Portainer deployed successfully" if success else "Portainer deployment failed",
            details={
                "url": f"https://{server['ip']}:{extra_vars['portainer_https_port']}",
                "username": extra_vars.get('portainer_admin_username', 'admin')
            }
        )

    def full_setup(self, server: Dict, config: Optional[Dict] = None) -> SetupResult:
        """
        Execute complete server setup

        Args:
            server: Server configuration
            config: Optional configuration overrides

        Returns:
            SetupResult with overall status
        """
        logger.info(f"Starting full setup for {server['name']}")

        config = config or {}

        # Wait for SSH to be ready first
        if not self.wait_for_ssh(server):
            return SetupResult(
                success=False,
                step="ssh-wait",
                message="SSH did not become available",
                details={"server": server["name"], "ip": server.get("ip")}
            )

        # Test Ansible connectivity
        logger.info("Testing Ansible connectivity before setup...")
        if not self.test_connectivity(server):
            return SetupResult(
                success=False,
                step="ansible-connectivity",
                message="Ansible cannot connect to the server",
                details={"server": server["name"], "ip": server.get("ip")}
            )

        # Define setup steps in order
        # v0.2.0: Traefik and Portainer are NO LONGER deployed during setup
        # They must be deployed separately as "infrastructure" app
        steps = [
            ("base-setup", lambda: self.setup_base(server)),
            ("docker-install", lambda: self.install_docker(server)),
            ("swarm-init", lambda: self.init_swarm(
                server,
                config.get("network_name", "livchat_network")
            ))
            # Traefik/Portainer deployment removed - use deploy-app instead
        ]

        completed_steps = []

        for step_name, step_func in steps:
            logger.info(f"Executing step: {step_name}")
            result = step_func()

            if not result.success:
                logger.error(f"Failed at step: {step_name}")
                return SetupResult(
                    success=False,
                    step=step_name,
                    message=f"Failed at step: {step_name}",
                    details={
                        "completed_steps": completed_steps,
                        "failed_step": step_name,
                        "error": result.message
                    }
                )

            completed_steps.append(step_name)

        logger.info(f"Full setup completed for {server['name']}")

        return SetupResult(
            success=True,
            step="complete",
            message="Server setup completed successfully",
            details={
                "completed_steps": completed_steps,
                "server": server["name"]
            }
        )