"""Provider configuration and initialization"""

import logging

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages cloud provider configuration and initialization"""

    def __init__(self, storage, ssh_manager):
        """Initialize ProviderManager"""
        self.storage = storage
        self.ssh_manager = ssh_manager
        self.provider = None

    def configure(self, provider_name: str, token: str) -> None:
        """Configure cloud provider"""
        if provider_name.lower() != "hetzner":
            raise ValueError(f"Unsupported provider: {provider_name}")

        # Store token in vault
        secret_key = f"{provider_name}_token"
        self.storage.secrets.set_secret(secret_key, token)
        logger.info(f"Configured {provider_name} provider")

        # Initialize provider instance
        self._init_provider(provider_name, token)

    def _init_provider(self, provider_name: str, token: str):
        """Initialize provider instance"""
        if provider_name.lower() == "hetzner":
            from ..providers.hetzner import HetznerProvider
            self.provider = HetznerProvider(token)
            logger.info("Initialized Hetzner provider")
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

    def get_provider(self):
        """Get current provider instance"""
        if not self.provider:
            # Try to auto-initialize from stored credentials
            token = self.storage.secrets.get_secret("hetzner_token")
            if token:
                self._init_provider("hetzner", token)
        return self.provider
