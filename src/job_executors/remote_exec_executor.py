"""
Remote Exec Executor Function

Executor function for remote command execution job:
- remote_exec: Execute SSH command on remote server

The executor takes (Job, Orchestrator) and updates job progress.
"""

import logging
from typing import Any, Dict

from src.job_manager import Job
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def execute_remote_exec(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute remote command execution job

    Args:
        job: Job instance with params (server_name, command, timeout, working_dir)
        orchestrator: Orchestrator instance

    Returns:
        Command execution result with success, stdout, stderr, exit_code
    """
    logger.info(f"Executing remote_exec job {job.job_id}")

    # Extract params
    params = job.params
    server_name = params.get("server_name")
    command = params.get("command")
    timeout = params.get("timeout", 30)
    working_dir = params.get("working_dir")

    # Validate required params
    if not server_name:
        raise ValueError("server_name is required in job params")
    if not command:
        raise ValueError("command is required in job params")

    # Step 1: Starting command execution
    job.advance_step(1, 2, f"Connecting to {server_name} via SSH")

    try:
        # Execute command with real-time streaming
        # Logs are automatically captured by JobLogManager from logger.info() calls
        result = await orchestrator.execute_remote_command_streaming(
            server_name=server_name,
            command=command,
            timeout=timeout,
            working_dir=working_dir
        )

        # Step 2: Command completed
        success = result.get("success", False)
        exit_code = result.get("exit_code", -1)

        if success:
            job.advance_step(2, 2, f"Command completed successfully (exit {exit_code})")
            job.update_progress(100, f"Command executed: exit_code={exit_code}")
        else:
            job.advance_step(2, 2, f"Command failed (exit {exit_code})")
            job.update_progress(100, f"Command failed: exit_code={exit_code}")

        logger.info(
            f"Remote command executed on {server_name}: "
            f"success={success}, exit_code={exit_code}, "
            f"stdout_len={len(result.get('stdout', ''))}, "
            f"stderr_len={len(result.get('stderr', ''))}"
        )

        return result

    except Exception as e:
        logger.error(f"Remote command execution failed on {server_name}: {e}", exc_info=True)
        job.update_progress(100, f"Execution failed: {str(e)}")

        # Return error result in same format
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "server_name": server_name,
            "command": command
        }
