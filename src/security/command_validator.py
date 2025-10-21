"""
SSH Command Security Validator

Validates commands before executing them remotely via SSH to prevent
dangerous operations like disk wiping, system destruction, etc.
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

# Dangerous command patterns
# Each pattern is a regex that matches potentially destructive commands
DANGEROUS_PATTERNS: List[str] = [
    # rm -rf / or rm -rf /* (delete root filesystem ONLY, not subdirs)
    # Must be followed by space, end of string, or wildcard
    r'rm\s+-[rRfF]*[rR][fF]*\s+/\s*$',      # rm -rf / at end
    r'rm\s+-[rRfF]*[rR][fF]*\s+/\*',        # rm -rf /*
    r'rm\s+-[rRfF]*[fF][rR]*\s+/\s*$',      # rm -fr / at end
    r'rm\s+-[rRfF]*[fF][rR]*\s+/\*',        # rm -fr /*

    # dd if=/dev/zero or dd if=/dev/urandom to disk (disk wipe)
    r'dd\s+if=/dev/(zero|urandom|random)\s+of=/dev/',

    # mkfs (format filesystem)
    r'mkfs\.',
    r'mkfs\s+-t',

    # Fork bomb pattern
    r':\(\)\s*\{\s*:\|:&\s*\}\s*;',
    r':\(\)\s*\{\s*:\|:\s*&\s*\}\s*;\s*:',

    # wget/curl piped to shell (download and execute)
    r'wget\s+.*\|\s*(sh|bash)',
    r'wget\s+-[OoQq]*\s*-\s+.*\|\s*(sh|bash)',
    r'curl\s+.*\|\s*(sh|bash)',

    # Generic pipe to bash/sh (cat script.sh | bash, etc.)
    r'\|\s*(bash|sh)\s*$',
    r'\|\s*(bash|sh)\s+-',
]


def is_dangerous_command(command: str) -> bool:
    """
    Check if a command matches dangerous patterns

    Args:
        command: Command string to validate

    Returns:
        True if command is dangerous, False otherwise

    Raises:
        TypeError/AttributeError: If command is None or not a string

    Examples:
        >>> is_dangerous_command("rm -rf /")
        True
        >>> is_dangerous_command("ls -la")
        False
        >>> is_dangerous_command("docker ps")
        False
    """
    if command is None:
        raise TypeError("Command cannot be None")

    # Empty or whitespace-only commands are safe (will just do nothing)
    if not command.strip():
        return False

    # Check against all dangerous patterns (case insensitive)
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            logger.warning(f"Dangerous command detected: {command[:100]}")
            logger.debug(f"Matched pattern: {pattern}")
            return True

    return False
