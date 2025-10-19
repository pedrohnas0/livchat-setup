"""
TDD: Tests for ProviderManager

Write tests FIRST, then implement
"""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.orchestrator.provider_manager import ProviderManager


class TestProviderManager:
    """Test ProviderManager class"""

    @pytest.fixture
    def storage_mock(self):
        """Mock storage"""
        storage = Mock()
        storage.secrets = Mock()
        storage.secrets.set_secret = Mock()
        storage.secrets.get_secret = Mock(return_value=None)
        return storage

    @pytest.fixture
    def ssh_manager_mock(self):
        """Mock SSH manager"""
        return Mock()

    @pytest.fixture
    def provider_manager(self, storage_mock, ssh_manager_mock):
        """Create ProviderManager instance"""
        return ProviderManager(storage_mock, ssh_manager_mock)

    def test_init(self, provider_manager, storage_mock, ssh_manager_mock):
        """Should initialize with storage and ssh_manager"""
        assert provider_manager.storage == storage_mock
        assert provider_manager.ssh_manager == ssh_manager_mock
        assert provider_manager.provider is None

    def test_configure_hetzner_stores_token_in_vault(self, provider_manager, storage_mock):
        """Should store Hetzner token in secrets vault"""
        # Act
        provider_manager.configure("hetzner", "test-token-123")

        # Assert
        storage_mock.secrets.set_secret.assert_called_once_with("hetzner_token", "test-token-123")

    def test_configure_hetzner_initializes_provider(self, provider_manager):
        """Should initialize HetznerProvider instance"""
        # Act
        provider_manager.configure("hetzner", "test-token-123")

        # Assert
        assert provider_manager.provider is not None
        assert provider_manager.provider.__class__.__name__ == "HetznerProvider"

    def test_configure_unsupported_provider_raises_error(self, provider_manager):
        """Should raise ValueError for unsupported provider"""
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported provider: digitalocean"):
            provider_manager.configure("digitalocean", "token")

    def test_get_provider_returns_existing(self, provider_manager):
        """Should return existing provider if already initialized"""
        # Arrange
        provider_manager.configure("hetzner", "token")
        existing_provider = provider_manager.provider

        # Act
        result = provider_manager.get_provider()

        # Assert
        assert result == existing_provider

    def test_get_provider_auto_initializes_from_vault(self, provider_manager, storage_mock):
        """Should auto-initialize provider from stored token"""
        # Arrange
        storage_mock.secrets.get_secret.return_value = "stored-token"

        # Act
        result = provider_manager.get_provider()

        # Assert
        assert result is not None
        storage_mock.secrets.get_secret.assert_called_with("hetzner_token")
