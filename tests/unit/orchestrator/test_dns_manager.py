"""
Unit tests for DNSManager

Tests TDD para extração do DNSManager do orchestrator_old.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import sys

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.orchestrator.dns_manager import DNSManager


class TestDNSManager:
    """Test suite for DNSManager"""

    @pytest.fixture
    def mock_storage(self):
        """Mock storage manager"""
        storage = MagicMock()
        storage.state = MagicMock()

        # Mock state methods
        storage.state.get_server = MagicMock(return_value={
            "name": "test-server",
            "ip": "1.2.3.4",
            "dns_config": {
                "zone_name": "example.com",
                "subdomain": "dev"
            }
        })
        storage.state.update_server = MagicMock()

        return storage

    @pytest.fixture
    def mock_cloudflare(self):
        """Mock Cloudflare client"""
        cloudflare = MagicMock()

        # Mock DNS setup methods
        cloudflare.setup_server_dns = AsyncMock(return_value={
            "success": True,
            "record_name": "ptn.dev.example.com",
            "record_id": "abc123"
        })

        cloudflare.add_app_with_standard_prefix = AsyncMock(return_value=[
            {"success": True, "record_name": "n8n.dev.example.com"},
            {"success": True, "record_name": "whk.dev.example.com"}
        ])

        return cloudflare

    @pytest.fixture
    def dns_manager(self, mock_storage):
        """Create DNSManager instance"""
        return DNSManager(storage=mock_storage)

    # ==================== INITIALIZATION TESTS ====================

    def test_dns_manager_initialization(self, dns_manager):
        """Test DNSManager initializes correctly"""
        assert dns_manager is not None
        assert dns_manager.storage is not None
        assert dns_manager.cloudflare is None  # Not set yet

    def test_dns_manager_with_cloudflare(self, mock_storage, mock_cloudflare):
        """Test DNSManager initializes with Cloudflare client"""
        # Given
        dns_manager = DNSManager(storage=mock_storage, cloudflare=mock_cloudflare)

        # Then
        assert dns_manager.cloudflare is mock_cloudflare

    # ==================== SETUP_DNS_FOR_SERVER TESTS ====================

    @pytest.mark.asyncio
    async def test_setup_dns_for_server_no_cloudflare(self, dns_manager):
        """Test setup_dns_for_server fails without Cloudflare"""
        # Given
        dns_manager.cloudflare = None

        # When
        result = await dns_manager.setup_dns_for_server("test-server", "example.com")

        # Then
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_setup_dns_for_server_server_not_found(self, dns_manager, mock_storage, mock_cloudflare):
        """Test setup_dns_for_server fails when server doesn't exist"""
        # Given
        dns_manager.cloudflare = mock_cloudflare
        mock_storage.state.get_server.return_value = None

        # When
        result = await dns_manager.setup_dns_for_server("nonexistent", "example.com")

        # Then
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_setup_dns_for_server_success_without_subdomain(
        self, dns_manager, mock_storage, mock_cloudflare
    ):
        """Test setup_dns_for_server successfully creates DNS without subdomain"""
        # Given
        dns_manager.cloudflare = mock_cloudflare

        # When
        result = await dns_manager.setup_dns_for_server("test-server", "example.com")

        # Then
        assert result["success"] is True
        assert result["record_name"] == "ptn.dev.example.com"

        # Verify Cloudflare was called correctly
        mock_cloudflare.setup_server_dns.assert_called_once()
        call_args = mock_cloudflare.setup_server_dns.call_args
        assert call_args[1]["zone_name"] == "example.com"
        assert call_args[1]["subdomain"] is None

        # Verify DNS config was saved to state
        mock_storage.state.update_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_dns_for_server_success_with_subdomain(
        self, dns_manager, mock_storage, mock_cloudflare
    ):
        """Test setup_dns_for_server successfully creates DNS with subdomain"""
        # Given
        dns_manager.cloudflare = mock_cloudflare

        # When
        result = await dns_manager.setup_dns_for_server("test-server", "example.com", "lab")

        # Then
        assert result["success"] is True

        # Verify subdomain was passed to Cloudflare
        call_args = mock_cloudflare.setup_server_dns.call_args
        assert call_args[1]["subdomain"] == "lab"

        # Verify DNS config includes subdomain
        update_call_args = mock_storage.state.update_server.call_args
        server_data = update_call_args[0][1]
        assert server_data["dns_config"]["zone_name"] == "example.com"
        assert server_data["dns_config"]["subdomain"] == "lab"

    @pytest.mark.asyncio
    async def test_setup_dns_for_server_cloudflare_error(
        self, dns_manager, mock_cloudflare
    ):
        """Test setup_dns_for_server handles Cloudflare errors"""
        # Given
        dns_manager.cloudflare = mock_cloudflare
        mock_cloudflare.setup_server_dns.side_effect = Exception("API error")

        # When
        result = await dns_manager.setup_dns_for_server("test-server", "example.com")

        # Then
        assert result["success"] is False
        assert "API error" in result["error"]

    # ==================== ADD_APP_DNS TESTS ====================

    @pytest.mark.asyncio
    async def test_add_app_dns_no_cloudflare(self, dns_manager):
        """Test add_app_dns fails without Cloudflare"""
        # Given
        dns_manager.cloudflare = None

        # When
        result = await dns_manager.add_app_dns("n8n", "example.com")

        # Then
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_add_app_dns_success(self, dns_manager, mock_cloudflare):
        """Test add_app_dns successfully creates DNS records"""
        # Given
        dns_manager.cloudflare = mock_cloudflare

        # When
        result = await dns_manager.add_app_dns("n8n", "example.com")

        # Then
        assert result["success"] is True
        assert result["app"] == "n8n"
        assert result["records_created"] == 2  # Main + webhook

        # Verify Cloudflare was called
        mock_cloudflare.add_app_with_standard_prefix.assert_called_once_with(
            app_name="n8n",
            zone_name="example.com",
            subdomain=None
        )

    @pytest.mark.asyncio
    async def test_add_app_dns_success_with_subdomain(self, dns_manager, mock_cloudflare):
        """Test add_app_dns with subdomain"""
        # Given
        dns_manager.cloudflare = mock_cloudflare

        # When
        result = await dns_manager.add_app_dns("n8n", "example.com", "dev")

        # Then
        assert result["success"] is True

        # Verify subdomain was passed
        mock_cloudflare.add_app_with_standard_prefix.assert_called_once_with(
            app_name="n8n",
            zone_name="example.com",
            subdomain="dev"
        )

    @pytest.mark.asyncio
    async def test_add_app_dns_partial_failure(self, dns_manager, mock_cloudflare):
        """Test add_app_dns when some records fail"""
        # Given
        dns_manager.cloudflare = mock_cloudflare
        mock_cloudflare.add_app_with_standard_prefix.return_value = [
            {"success": True, "record_name": "n8n.example.com"},
            {"success": False, "error": "Record already exists"}
        ]

        # When
        result = await dns_manager.add_app_dns("n8n", "example.com")

        # Then
        assert result["success"] is True  # At least one succeeded
        assert result["records_created"] == 1

    @pytest.mark.asyncio
    async def test_add_app_dns_complete_failure(self, dns_manager, mock_cloudflare):
        """Test add_app_dns when all records fail"""
        # Given
        dns_manager.cloudflare = mock_cloudflare
        mock_cloudflare.add_app_with_standard_prefix.return_value = [
            {"success": False, "error": "Error 1"},
            {"success": False, "error": "Error 2"}
        ]

        # When
        result = await dns_manager.add_app_dns("n8n", "example.com")

        # Then
        assert result["success"] is False
        assert result["records_created"] == 0

    @pytest.mark.asyncio
    async def test_add_app_dns_cloudflare_exception(self, dns_manager, mock_cloudflare):
        """Test add_app_dns handles Cloudflare exceptions"""
        # Given
        dns_manager.cloudflare = mock_cloudflare
        mock_cloudflare.add_app_with_standard_prefix.side_effect = Exception("Connection failed")

        # When
        result = await dns_manager.add_app_dns("n8n", "example.com")

        # Then
        assert result["success"] is False
        assert "Connection failed" in result["error"]
