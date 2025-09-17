"""Configuration management for LivChat Setup"""

import logging
from pathlib import Path
from typing import Any, Optional
import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration files"""

    def __init__(self, config_dir: Path):
        """
        Initialize ConfigManager

        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.config_file = config_dir / "config.yaml"
        self._config = {}

    def init(self) -> None:
        """Initialize configuration file with defaults"""
        if not self.config_file.exists():
            logger.info("Creating default configuration")
            default_config = {
                "version": 1,
                "provider": "hetzner",
                "region": "nbg1",
                "server_type": "cx21",
            }
            self.save_config(default_config)
        else:
            logger.info("Configuration file already exists")

        self.load_config()

    def load_config(self) -> dict:
        """
        Load configuration from file

        Returns:
            Configuration dictionary
        """
        if self.config_file.exists():
            logger.debug(f"Loading config from {self.config_file}")
            with open(self.config_file, 'r') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            logger.warning("Config file not found, using empty config")
            self._config = {}

        return self._config

    def save_config(self, config: Optional[dict] = None) -> None:
        """
        Save configuration to file

        Args:
            config: Configuration to save (uses current if not provided)
        """
        if config is not None:
            self._config = config

        logger.debug(f"Saving config to {self.config_file}")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.config_file, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value
        """
        if not self._config:
            self.load_config()

        # Support dot notation (e.g., "providers.hetzner.region")
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        if not self._config:
            self.load_config()

        # Support dot notation
        keys = key.split('.')
        current = self._config

        # Navigate to the parent of the key to set
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the final key
        current[keys[-1]] = value

        # Save changes
        self.save_config()
        logger.debug(f"Set config {key} = {value}")

    def update(self, updates: dict) -> None:
        """
        Update multiple configuration values

        Args:
            updates: Dictionary of updates
        """
        if not self._config:
            self.load_config()

        self._config.update(updates)
        self.save_config()
        logger.debug(f"Updated config with {len(updates)} changes")