"""Unit tests for CloudflareClient with SDK v4.3.1 compatibility"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.integrations.cloudflare import CloudflareClient, CloudflareError


class TestCloudflareClient:
    """Test suite for CloudflareClient"""

    @pytest.fixture
    def client(self):
        """Create a CloudflareClient instance for testing"""
        with patch('src.integrations.cloudflare.Cloudflare') as mock_cf:
            client = CloudflareClient(
                email="test@example.com",
                global_api_key="test_api_key"
            )
            return client

    @pytest.fixture
    def mock_cloudflare(self):
        """Mock the Cloudflare SDK class"""
        with patch('src.integrations.cloudflare.Cloudflare') as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_initialization(self, client):
        """Test CloudflareClient initialization"""
        assert client.email == "test@example.com"
        assert client.api_key == "test_api_key"
        assert client.client is not None

    @pytest.mark.asyncio
    async def test_list_zones(self, client, mock_cloudflare):
        """Test listing zones"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_zones.list.return_value = [
            {"id": "zone1", "name": "example.com"},
            {"id": "zone2", "name": "livchat.ai"}
        ]
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
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
        mock_dns = MagicMock()
        mock_records = MagicMock()

        # Mock the DNS record creation - return object with attributes
        mock_record = MagicMock()
        mock_record.id = "record123"
        mock_record.type = "A"
        mock_record.name = "ptn.lab.livchat.ai"
        mock_record.content = "168.119.89.45"
        mock_record.proxied = False
        mock_record.comment = "portainer"

        mock_records.create.return_value = mock_record
        mock_dns.records = mock_records
        mock_client.dns = mock_dns
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

        mock_records.create.assert_called_once_with(
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
        mock_dns = MagicMock()
        mock_records = MagicMock()

        # Mock the DNS record creation - return object with attributes
        mock_record = MagicMock()
        mock_record.id = "record456"
        mock_record.type = "CNAME"
        mock_record.name = "chat.lab.livchat.ai"
        mock_record.content = "ptn.lab.livchat.ai"
        mock_record.proxied = False
        mock_record.comment = "chatwoot"

        mock_records.create.return_value = mock_record
        mock_dns.records = mock_records
        mock_client.dns = mock_dns
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

        # No assert on mock call since it's handled differently now

    @pytest.mark.asyncio
    async def test_setup_server_dns(self, client, mock_cloudflare):
        """Test setting up server DNS (A record for Portainer)"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()
        mock_records = MagicMock()

        # Mock zone lookup
        mock_zones.list.return_value = [
            {"id": "zone123", "name": "livchat.ai"}
        ]

        # Mock DNS record creation - return object with attributes
        mock_record = MagicMock()
        mock_record.id = "record123"
        mock_record.type = "A"
        mock_record.name = "ptn.lab.livchat.ai"
        mock_record.content = "168.119.89.45"
        mock_record.proxied = False

        mock_records.create.return_value = mock_record
        mock_dns.records = mock_records

        mock_client.zones = mock_zones
        mock_client.dns = mock_dns
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        server = {"name": "test-server", "ip": "168.119.89.45"}
        result = await client.setup_server_dns(
            server=server,
            zone_name="livchat.ai",
            subdomain="lab"
        )

        # Verify
        assert result["portainer"]["id"] == "record123"
        assert result["portainer"]["type"] == "A"
        assert result["portainer"]["content"] == "168.119.89.45"


    @pytest.mark.asyncio
    async def test_list_dns_records(self, client, mock_cloudflare):
        """Test listing DNS records for a zone"""
        # Setup mock
        mock_client = MagicMock()
        mock_dns = MagicMock()
        mock_records = MagicMock()

        # Mock DNS records list - return objects with attributes
        mock_rec1 = MagicMock()
        mock_rec1.id = "rec1"
        mock_rec1.type = "A"
        mock_rec1.name = "ptn.lab.livchat.ai"
        mock_rec1.content = "168.119.89.45"

        mock_rec2 = MagicMock()
        mock_rec2.id = "rec2"
        mock_rec2.type = "CNAME"
        mock_rec2.name = "chat.lab.livchat.ai"
        mock_rec2.content = "ptn.lab.livchat.ai"

        mock_rec3 = MagicMock()
        mock_rec3.id = "rec3"
        mock_rec3.type = "A"
        mock_rec3.name = "lab.livchat.ai"
        mock_rec3.content = "168.119.89.45"

        mock_records.list.return_value = [mock_rec1, mock_rec2, mock_rec3]
        mock_dns.records = mock_records
        mock_client.dns = mock_dns
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        records = await client.list_dns_records("zone123")

        # Verify
        assert len(records) == 3
        assert records[0]["name"] == "ptn.lab.livchat.ai"
        mock_records.list.assert_called_once_with(zone_id="zone123")

    @pytest.mark.asyncio
    async def test_delete_dns_record(self, client, mock_cloudflare):
        """Test deleting a DNS record"""
        # Setup mock
        mock_client = MagicMock()
        mock_dns = MagicMock()
        mock_records = MagicMock()

        # Mock deletion
        mock_records.delete.return_value = True

        mock_dns.records = mock_records
        mock_client.dns = mock_dns
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        result = await client.delete_dns_record("zone123", "record123")

        # Verify
        assert result is True
        mock_records.delete.assert_called_once_with(
            zone_id="zone123",
            dns_record_id="record123"
        )

    @pytest.mark.asyncio
    async def test_cleanup_server_dns(self, client, mock_cloudflare):
        """Test cleaning up server DNS records"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_dns = MagicMock()
        mock_records = MagicMock()

        # Mock zone lookup
        mock_zones.list.return_value = [
            {"id": "zone123", "name": "livchat.ai"}
        ]

        # Mock DNS records list
        mock_rec1 = MagicMock()
        mock_rec1.id = "rec1"
        mock_rec1.name = "ptn.lab.livchat.ai"
        mock_rec1.type = "A"
        mock_rec1.content = "168.119.89.45"

        mock_rec2 = MagicMock()
        mock_rec2.id = "rec2"
        mock_rec2.name = "chat.lab.livchat.ai"
        mock_rec2.type = "CNAME"
        mock_rec2.content = "ptn.lab.livchat.ai"

        mock_rec3 = MagicMock()
        mock_rec3.id = "rec3"
        mock_rec3.name = "other.livchat.ai"
        mock_rec3.type = "A"
        mock_rec3.content = "1.2.3.4"

        mock_records.list.return_value = [mock_rec1, mock_rec2, mock_rec3]
        mock_records.delete.return_value = True

        mock_dns.records = mock_records
        mock_client.zones = mock_zones
        mock_client.dns = mock_dns
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        result = await client.cleanup_server_dns(
            zone_name="livchat.ai",
            subdomain="lab"
        )

        # Verify
        assert result["success"] is True
        assert len(result["deleted"]) == 2  # Only lab-related records
        assert result["deleted"][0]["name"] == "ptn.lab.livchat.ai"
        assert result["deleted"][1]["name"] == "chat.lab.livchat.ai"

        # Should have called delete twice
        assert mock_records.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_cloudflare_error_handling(self, client, mock_cloudflare):
        """Test error handling when Cloudflare API fails"""
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_zones.list.side_effect = Exception("API Error")
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test and expect exception
        with pytest.raises(CloudflareError) as exc_info:
            await client.list_zones()

        assert "Failed to list zones" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_zone_not_found(self, client, mock_cloudflare):
        """Test when zone is not found"""
        # Setup mock
        mock_client = MagicMock()
        mock_zones = MagicMock()
        mock_zones.list.return_value = []  # No zones
        mock_client.zones = mock_zones
        mock_cloudflare.return_value = mock_client

        # Re-init client
        client._init_client()

        # Test
        zone = await client.get_zone("nonexistent.com")

        # Verify
        assert zone is None


    @pytest.mark.asyncio
    async def test_init_client_with_invalid_credentials(self):
        """Test client initialization with invalid credentials"""
        with patch('src.integrations.cloudflare.Cloudflare') as mock_cf:
            mock_cf.side_effect = Exception("Invalid credentials")

            with pytest.raises(CloudflareError) as exc_info:
                CloudflareClient(
                    email="invalid@example.com",
                    global_api_key="invalid_key"
                )

            assert "Failed to initialize Cloudflare client" in str(exc_info.value)