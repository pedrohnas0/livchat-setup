"""
Unit tests for Cloudflare API client
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.integrations.cloudflare import CloudflareClient, CloudflareError


class TestCloudflareClient:
    """Test Cloudflare API client with Global API Key"""

    @pytest.fixture
    def client(self):
        """Create Cloudflare client instance"""
        return CloudflareClient(
            email="test@example.com",
            global_api_key="test_api_key_123"
        )

    @pytest.fixture
    def mock_cloudflare(self):
        """Mock Cloudflare SDK"""
        with patch('src.integrations.cloudflare.Cloudflare') as mock:
            yield mock

    def test_initialization(self, mock_cloudflare):
        """Test client initialization with email and global API key"""
        # Create client
        client = CloudflareClient(
            email="test@example.com",
            global_api_key="test_api_key_123"
        )

        # Verify SDK was initialized with correct parameters
        mock_cloudflare.assert_called_once_with(
            api_email="test@example.com",
            api_key="test_api_key_123"
        )

    @pytest.mark.asyncio
    async def test_list_zones(self, client, mock_cloudflare):
        """Test listing DNS zones"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_zones.list.return_value = [
            {"id": "zone1", "name": "example.com"},
            {"id": "zone2", "name": "livchat.ai"}
        ]
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client to use mocked SDK
        client._init_client()

        # Test
        zones = await client.list_zones()

        # Verify
        assert len(zones) == 2
        assert zones[1]["name"] == "livchat.ai"
        mock_zones.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_zone_by_name(self, client, mock_cloudflare):
        """Test getting zone by name"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_zones.list.return_value = [
            {"id": "zone123", "name": "livchat.ai"}
        ]
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        zone = await client.get_zone("livchat.ai")

        # Verify
        assert zone["id"] == "zone123"
        assert zone["name"] == "livchat.ai"
        mock_zones.list.assert_called_with(name="livchat.ai")

    @pytest.mark.asyncio
    async def test_create_a_record(self, client, mock_cloudflare):
        """Test creating A record (for Portainer)"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()

        # Mock the DNS record creation - dns_records.create
        mock_dns_create = MagicMock()
        mock_dns_create.return_value = {
            "id": "record123",
            "type": "A",
            "name": "ptn.lab.livchat.ai",
            "content": "168.119.89.45",
            "proxied": False,
            "comment": "portainer"
        }
        mock_dns.create = mock_dns_create

        mock_zones.dns_records = mock_dns
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        record = await client.create_dns_record(
            zone_id="zone123",
            type="A",
            name="ptn.lab.livchat.ai",
            content="168.119.89.45",
            proxied=False,
            comment="portainer"
        )

        # Verify
        assert record["id"] == "record123"
        assert record["type"] == "A"
        assert record["content"] == "168.119.89.45"

        mock_dns.create.assert_called_once_with(
            zone_id="zone123",
            type="A",
            name="ptn.lab.livchat.ai",
            content="168.119.89.45",
            proxied=False,
            comment="portainer",
            ttl=1
        )

    @pytest.mark.asyncio
    async def test_create_cname_record(self, client, mock_cloudflare):
        """Test creating CNAME record (for apps)"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()

        # Mock the DNS record creation - dns_records.create
        mock_dns_create = MagicMock()
        mock_dns_create.return_value = {
            "id": "record456",
            "type": "CNAME",
            "name": "chat.lab.livchat.ai",
            "content": "ptn.lab.livchat.ai",
            "proxied": False,
            "comment": "chatwoot"
        }
        mock_dns.create = mock_dns_create

        mock_zones.dns_records = mock_dns
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        record = await client.create_dns_record(
            zone_id="zone123",
            type="CNAME",
            name="chat.lab.livchat.ai",
            content="ptn.lab.livchat.ai",
            proxied=False,
            comment="chatwoot"
        )

        # Verify
        assert record["id"] == "record456"
        assert record["type"] == "CNAME"
        assert record["content"] == "ptn.lab.livchat.ai"

    @pytest.mark.asyncio
    async def test_setup_server_dns(self, client, mock_cloudflare):
        """Test setting up server DNS (A record for Portainer)"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()

        # Mock zone lookup
        mock_zones.list.return_value = [
            {"id": "zone123", "name": "livchat.ai"}
        ]

        # Mock DNS record creation
        mock_dns_create = MagicMock()
        mock_dns_create.return_value = {
            "id": "record123",
            "type": "A",
            "name": "ptn.lab.livchat.ai",
            "content": "168.119.89.45",
            "proxied": False,
            "comment": "portainer"
        }
        mock_dns.create = mock_dns_create

        # Mock list_dns_records - for checking existing records
        mock_dns_list = MagicMock()
        mock_dns_list.return_value = []  # No existing records
        mock_dns.list = mock_dns_list

        mock_zones.dns_records = mock_dns
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        server = {
            "name": "srv1",
            "ip": "168.119.89.45"
        }

        result = await client.setup_server_dns(
            server=server,
            zone_name="livchat.ai",
            subdomain="lab"
        )

        # Verify
        assert result["success"] is True
        assert result["record_name"] == "ptn.lab.livchat.ai"
        assert result["record_type"] == "A"

    @pytest.mark.asyncio
    async def test_add_app_dns(self, client, mock_cloudflare):
        """Test adding app DNS (CNAME record)"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()

        # Mock zone lookup
        mock_zones.list.return_value = [
            {"id": "zone123", "name": "livchat.ai"}
        ]

        # Mock DNS record creation for app
        mock_dns_create = MagicMock()
        mock_dns_create.return_value = {
            "id": "record789",
            "type": "CNAME",
            "name": "edt.lab.livchat.ai",
            "content": "ptn.lab.livchat.ai",
            "proxied": False,
            "comment": "n8n"
        }
        mock_dns.create = mock_dns_create

        # Mock list_dns_records - for checking existing records
        mock_dns_list = MagicMock()
        mock_dns_list.return_value = []  # No existing records
        mock_dns.list = mock_dns_list

        mock_zones.dns_records = mock_dns
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test adding N8N (which needs edt and whk records)
        result = await client.add_app_dns(
            app_prefix="edt",
            zone_name="livchat.ai",
            subdomain="lab",
            comment="n8n"
        )

        # Verify
        assert result["success"] is True
        assert result["record_name"] == "edt.lab.livchat.ai"
        assert result["target"] == "ptn.lab.livchat.ai"

    @pytest.mark.asyncio
    async def test_list_dns_records(self, client, mock_cloudflare):
        """Test listing DNS records for a zone"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()

        # Mock the DNS list method - dns_records.list
        mock_dns_list = MagicMock()
        mock_dns_list.return_value = [
            {"id": "r1", "type": "A", "name": "ptn.lab.livchat.ai"},
            {"id": "r2", "type": "CNAME", "name": "chat.lab.livchat.ai"},
            {"id": "r3", "type": "CNAME", "name": "edt.lab.livchat.ai"}
        ]
        mock_dns.list = mock_dns_list

        mock_zones.dns_records = mock_dns
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        records = await client.list_dns_records("zone123")

        # Verify
        assert len(records) == 3
        assert records[0]["type"] == "A"
        assert records[1]["type"] == "CNAME"

    @pytest.mark.asyncio
    async def test_delete_dns_record(self, client, mock_cloudflare):
        """Test deleting DNS record"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()

        # Mock the DNS delete method - dns_records.delete
        mock_dns_delete = MagicMock()
        mock_dns_delete.return_value = True
        mock_dns.delete = mock_dns_delete

        mock_zones.dns_records = mock_dns
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        result = await client.delete_dns_record("zone123", "record123")

        # Verify
        assert result is True
        mock_dns.delete.assert_called_once_with(
            zone_id="zone123",
            dns_record_id="record123"
        )

    @pytest.mark.asyncio
    async def test_error_handling(self, client, mock_cloudflare):
        """Test error handling"""
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_zones.list.side_effect = Exception("API Error")
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        with pytest.raises(CloudflareError) as exc:
            await client.list_zones()

        assert "Failed to list zones" in str(exc.value)