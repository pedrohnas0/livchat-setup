"""Ansible Runner for executing playbooks and ad-hoc commands"""

import json
import os
import logging
import tempfile
import time
import stat
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import ansible_runner

logger = logging.getLogger(__name__)


@dataclass
class AnsibleResult:
    """Result from Ansible execution"""
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    stats: Dict = None


class AnsibleRunner:
    """Executes Ansible playbooks via Python API"""

    def __init__(self, ssh_manager: Any = None):
        """
        Initialize Ansible Runner

        Args:
            ssh_manager: SSH Key Manager for key paths
        """
        self.ssh_manager = ssh_manager
        self.work_dir = Path.home() / ".livchat" / "ansible"
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Ansible directories
        self.playbooks_dir = Path(__file__).parent.parent / "ansible" / "playbooks"
        self.inventory_dir = self.work_dir / "inventory"
        self.inventory_dir.mkdir(parents=True, exist_ok=True)

    def create_inventory(self, servers: List[Dict]) -> Dict:
        """
        Create dynamic inventory from server list

        Args:
            servers: List of server configurations

        Returns:
            Inventory dictionary
        """
        inventory = {
            "all": {
                "hosts": {},
                "vars": {
                    "ansible_python_interpreter": "/usr/bin/python3"
                }
            }
        }

        for server in servers:
            host_name = server["name"]
            ssh_key = server.get("ssh_key", "")

            # Get SSH key path if manager is available
            ssh_key_path = ""
            if self.ssh_manager and ssh_key:
                try:
                    ssh_key_path = str(self.ssh_manager.get_private_key_path(ssh_key))
                except Exception as e:
                    logger.warning(f"Could not get SSH key path: {e}")
                    ssh_key_path = str(Path.home() / ".livchat" / "ssh_keys" / ssh_key)

            inventory["all"]["hosts"][host_name] = {
                "ansible_host": server["ip"],
                "ansible_user": server.get("user", "root"),
                "ansible_ssh_private_key_file": ssh_key_path,
                "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            }

        return inventory

    def save_inventory(self, inventory: Dict, name: str = "hosts") -> Path:
        """
        Save inventory to file

        Args:
            inventory: Inventory dictionary
            name: Name for inventory file

        Returns:
            Path to saved inventory file
        """
        inventory_file = self.inventory_dir / f"{name}.json"
        inventory_file.write_text(json.dumps(inventory, indent=2))
        logger.debug(f"Inventory saved to: {inventory_file}")
        return inventory_file

    def get_playbook_path(self, playbook: str) -> Path:
        """
        Get full path to playbook

        Args:
            playbook: Playbook name or path

        Returns:
            Full path to playbook
        """
        playbook_path = Path(playbook)

        # If absolute path, return as is
        if playbook_path.is_absolute():
            return playbook_path

        # Otherwise look in playbooks directory
        return self.playbooks_dir / playbook

    def validate_playbook(self, playbook_path: str) -> bool:
        """
        Validate if playbook exists

        Args:
            playbook_path: Path to playbook

        Returns:
            True if playbook exists
        """
        path = Path(playbook_path)
        return path.exists() and path.is_file()

    def get_ansible_config(self) -> Dict:
        """
        Get Ansible configuration settings

        Returns:
            Configuration dictionary
        """
        return {
            "host_key_checking": False,
            "timeout": 30,
            "gathering": "smart",
            "pipelining": True,
            "ssh_args": "-o ControlMaster=auto -o ControlPersist=60s",
            "retry_files_enabled": False
        }

    def parse_output(self, output: Dict) -> Dict:
        """
        Parse Ansible output for results

        Args:
            output: Ansible output dictionary

        Returns:
            Parsed statistics
        """
        if "stats" in output:
            return output["stats"]
        return {}

    def run_playbook(self, playbook_path: str, inventory: Dict,
                    extra_vars: Optional[Dict] = None, retries: int = 3) -> AnsibleResult:
        """
        Execute an Ansible playbook

        Args:
            playbook_path: Path to playbook file
            inventory: Inventory dictionary
            extra_vars: Extra variables to pass to playbook
            retries: Number of retries on failure

        Returns:
            AnsibleResult with execution details
        """
        logger.info(f"Running playbook: {playbook_path}")

        # Prepare environment variables
        envvars = {
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "ANSIBLE_RETRY_FILES_ENABLED": "False",
            "ANSIBLE_TIMEOUT": "30"
        }

        # Set ansible config path if exists
        ansible_cfg = Path(__file__).parent.parent / "ansible" / "ansible.cfg"
        if ansible_cfg.exists():
            envvars["ANSIBLE_CONFIG"] = str(ansible_cfg)

        last_result = None

        for attempt in range(retries):
            if attempt > 0:
                # Exponential backoff: 2^attempt seconds
                wait_time = 2 ** attempt
                logger.info(f"Retry attempt {attempt}/{retries} after {wait_time}s")
                time.sleep(wait_time)

            # Create temporary directory for this run
            with tempfile.TemporaryDirectory() as tmpdir:
                # Save inventory to temp file
                tmp_inventory = Path(tmpdir) / "inventory.json"

                # Log inventory for debugging
                logger.debug(f"Creating inventory at: {tmp_inventory}")
                logger.debug(f"Inventory: {json.dumps(inventory, indent=2)}")

                tmp_inventory.write_text(json.dumps(inventory))

                try:
                    # Run ansible-runner
                    result = ansible_runner.run(
                        playbook=playbook_path,
                        inventory=str(tmp_inventory),
                        extravars=extra_vars or {},
                        envvars=envvars,
                        quiet=False,
                        artifact_dir=tmpdir,
                        rotate_artifacts=10
                    )

                    # Parse result
                    success = result.rc == 0 and result.status == "successful"

                    # Capture output for debugging
                    stdout_content = ""
                    stderr_content = ""

                    # Read stdout if available
                    if hasattr(result, 'stdout') and result.stdout:
                        if hasattr(result.stdout, 'read'):
                            stdout_content = result.stdout.read()
                        else:
                            stdout_content = str(result.stdout)

                    # Read stderr if available
                    if hasattr(result, 'stderr') and result.stderr:
                        if hasattr(result.stderr, 'read'):
                            stderr_content = result.stderr.read()
                        else:
                            stderr_content = str(result.stderr)

                    # Check for artifacts for more details
                    artifact_dir = Path(tmpdir)
                    stdout_file = artifact_dir / "stdout"
                    if stdout_file.exists() and not stdout_content:
                        stdout_content = stdout_file.read_text()

                    stderr_file = artifact_dir / "stderr"
                    if stderr_file.exists() and not stderr_content:
                        stderr_content = stderr_file.read_text()

                    ansible_result = AnsibleResult(
                        success=success,
                        exit_code=result.rc,
                        stdout=stdout_content,
                        stderr=stderr_content,
                        stats=result.stats if hasattr(result, 'stats') else {}
                    )

                    if success:
                        logger.info(f"Playbook succeeded on attempt {attempt + 1}")
                        return ansible_result

                    last_result = ansible_result

                    if not success:
                        logger.warning(f"Playbook failed on attempt {attempt + 1} with exit code: {result.rc}")
                        logger.debug(f"Status: {result.status if hasattr(result, 'status') else 'unknown'}")
                        if stderr_content:
                            logger.error(f"Stderr output: {stderr_content[:500]}")  # First 500 chars
                        if hasattr(result, 'stats'):
                            logger.debug(f"Stats: {result.stats}")

                except Exception as e:
                    logger.error(f"Exception on attempt {attempt + 1}: {e}")
                    last_result = AnsibleResult(
                        success=False,
                        exit_code=-1,
                        stdout="",
                        stderr=str(e)
                    )

        # All retries failed
        logger.error(f"Playbook failed after {retries} attempts")
        return last_result or AnsibleResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="All retry attempts failed"
        )

    def run_adhoc(self, host: str, module: str, args: str = "",
                 user: str = "root", ssh_key: Optional[str] = None) -> AnsibleResult:
        """
        Execute ad-hoc Ansible command

        Args:
            host: Target host (IP or hostname)
            module: Ansible module to run
            args: Module arguments
            user: SSH user
            ssh_key: SSH key name (optional)

        Returns:
            AnsibleResult with execution details
        """
        logger.info(f"Running ad-hoc command: {module} on {host}")

        # Get SSH key path if provided
        ssh_key_path = ""
        if ssh_key:
            if self.ssh_manager:
                try:
                    ssh_key_path = str(self.ssh_manager.get_private_key_path(ssh_key))
                    logger.info(f"Using SSH key from manager: {ssh_key_path}")
                except Exception as e:
                    logger.warning(f"Could not get SSH key path for {ssh_key}: {e}")

        # Create simple inventory for single host
        inventory_host = {
            "ansible_host": host,
            "ansible_user": user,
            "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        }

        # Add SSH key if available
        if ssh_key_path:
            inventory_host["ansible_ssh_private_key_file"] = ssh_key_path
            logger.info(f"Added SSH key to inventory: {ssh_key_path}")
            # Check if key file exists
            key_path_obj = Path(ssh_key_path)
            if key_path_obj.exists():
                logger.info(f"✅ SSH key file exists: {ssh_key_path}")
                # Check permissions
                file_stat = key_path_obj.stat()
                file_mode = oct(file_stat.st_mode)[-3:]
                logger.info(f"   Key file permissions: {file_mode}")
                if file_mode != "600":
                    logger.warning(f"   ⚠️ Key permissions should be 600, fixing...")
                    key_path_obj.chmod(0o600)
            else:
                logger.error(f"❌ SSH key file NOT found: {ssh_key_path}")

        inventory = {
            "all": {
                "hosts": {
                    "target": inventory_host
                }
            }
        }

        logger.debug(f"Full inventory: {json.dumps(inventory, indent=2)}")

        # Prepare environment
        envvars = {
            "ANSIBLE_HOST_KEY_CHECKING": "False"
        }

        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save inventory
            tmp_inventory = Path(tmpdir) / "inventory.json"
            tmp_inventory.write_text(json.dumps(inventory))

            # Run ansible-runner
            result = ansible_runner.run(
                module=module,
                module_args=args,
                inventory=str(tmp_inventory),
                envvars=envvars,
                quiet=False,
                artifact_dir=tmpdir,
                host_pattern="target"
            )

            # Parse result
            success = result.rc == 0 and result.status == "successful"

            return AnsibleResult(
                success=success,
                exit_code=result.rc,
                stdout=str(result.stdout) if result.stdout else "",
                stderr=str(result.stderr) if result.stderr else ""
            )