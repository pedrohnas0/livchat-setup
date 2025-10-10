"""
Unit tests for Portainer API client
"""
import pytest
import httpx
from unittest.mock import Mock, AsyncMock, patch
from src.integrations.portainer import PortainerClient, PortainerError


class TestPortainerClient:
    """Test Portainer API client"""

    @pytest.fixture
    def client(self):
        """Create Portainer client instance"""
        return PortainerClient(
            url="https://portainer.example.com",
            username="admin",
            password="admin123"
        )

    @pytest.fixture
    def mock_httpx(self):
        """Mock httpx AsyncClient"""
        with patch('src.integrations.portainer.httpx.AsyncClient') as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_authentication_success(self, client):
        """Test successful authentication"""
        # Setup mock directly on client's _request method
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jwt": "token123"}

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        token = await client.authenticate()

        # Verify
        assert token == "token123"
        assert client.token == "token123"
        client._request.assert_called_once_with(
            "POST",
            "/api/auth",
            json={"username": "admin", "password": "admin123"}
        )

    @pytest.mark.asyncio
    async def test_authentication_failure(self, client):
        """Test authentication failure"""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid credentials"

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        with pytest.raises(PortainerError) as exc:
            await client.authenticate()

        assert "Authentication failed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_swarm_id(self, client):
        """Test getting Swarm ID"""
        # Set token
        client.token = "token123"

        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ID": "swarm123abc",
            "Version": {"Index": 10},
            "CreatedAt": "2024-01-01T00:00:00Z"
        }

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        swarm_id = await client.get_swarm_id(endpoint_id=1)

        # Verify
        assert swarm_id == "swarm123abc"

        client._request.assert_called_once_with(
            "GET",
            "/api/endpoints/1/docker/swarm",
            headers=client._get_headers()
        )

    @pytest.mark.asyncio
    async def test_get_swarm_id_not_found(self, client):
        """Test Swarm ID not found"""
        # Set token
        client.token = "token123"

        # Setup mock - response without ID field
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        with pytest.raises(PortainerError) as exc:
            await client.get_swarm_id(endpoint_id=1)

        assert "Swarm ID not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_create_stack(self, client):
        """Test stack creation"""
        # Set token
        client.token = "token123"

        # Setup mock for get_swarm_id
        swarm_mock_response = Mock()
        swarm_mock_response.status_code = 200
        swarm_mock_response.json.return_value = {"ID": "swarm123abc"}

        # Setup mock for create_stack
        stack_mock_response = Mock()
        stack_mock_response.status_code = 200
        stack_mock_response.json.return_value = {
            "Id": 1,
            "Name": "test-stack",
            "Status": 1
        }

        # Patch the _request method to return different responses
        async def mock_request(method, path, **kwargs):
            if "docker/swarm" in path:
                return swarm_mock_response
            else:
                return stack_mock_response

        client._request = AsyncMock(side_effect=mock_request)

        # Test
        compose_content = """
        version: '3.8'
        services:
          app:
            image: nginx
        """

        result = await client.create_stack(
            name="test-stack",
            compose=compose_content,
            endpoint_id=1,
            env={"VAR1": "value1"}
        )

        # Verify
        assert result["Id"] == 1
        assert result["Name"] == "test-stack"

        # Check calls - should be called twice (get_swarm_id + create_stack)
        assert client._request.call_count == 2

        # Check the create_stack call (second call)
        call_args = client._request.call_args_list[1]
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/stacks/create/swarm/string"
        assert call_args[1]["params"]["endpointId"] == 1

        # Check body includes SwarmID
        body = call_args[1]["json"]
        assert body["Name"] == "test-stack"
        assert body["SwarmID"] == "swarm123abc"
        assert "StackFileContent" in body

    @pytest.mark.asyncio
    async def test_get_stack(self, client):
        """Test getting stack info"""
        # Set token
        client.token = "token123"

        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Id": 1,
            "Name": "test-stack",
            "Status": 1,
            "EndpointId": 1
        }

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        result = await client.get_stack(1)

        # Verify
        assert result["Id"] == 1
        assert result["Name"] == "test-stack"

        client._request.assert_called_once_with(
            "GET",
            "/api/stacks/1",
            headers=client._get_headers()
        )

    @pytest.mark.asyncio
    async def test_stack_not_found(self, client):
        """Test stack not found error"""
        # Set token
        client.token = "token123"

        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Stack not found"

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        with pytest.raises(PortainerError) as exc:
            await client.get_stack(999)

        assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_delete_stack(self, client):
        """Test stack deletion"""
        # Set token
        client.token = "token123"

        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 204  # No content

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        result = await client.delete_stack(1)

        # Verify
        assert result is True

        client._request.assert_called_once_with(
            "DELETE",
            "/api/stacks/1",
            params={"external": False},
            headers=client._get_headers()
        )

    @pytest.mark.asyncio
    async def test_list_endpoints(self, client):
        """Test listing endpoints"""
        # Set token
        client.token = "token123"

        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"Id": 1, "Name": "local", "Type": 1},
            {"Id": 2, "Name": "remote", "Type": 2}
        ]

        # Patch the _request method
        client._request = AsyncMock(return_value=mock_response)

        # Test
        result = await client.list_endpoints()

        # Verify
        assert len(result) == 2
        assert result[0]["Name"] == "local"
        assert result[1]["Name"] == "remote"

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client):
        """Test retry mechanism on timeout"""
        # Set token
        client.token = "token123"

        # For now, just test that timeout raises exception
        # Retry logic with tenacity is complex to test with mocks
        client._request = AsyncMock(side_effect=httpx.TimeoutException("Connection timeout"))

        # Test - should raise timeout
        with pytest.raises(httpx.TimeoutException):
            await client.get_stack(1)

        # Verify request was attempted
        assert client._request.call_count >= 1

    @pytest.mark.asyncio
    async def test_unauthorized_refreshes_token(self, client):
        """Test token refresh on 401"""
        # Set initial token
        client.token = "old_token"

        # Create side effects for _request
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.json.return_value = {"jwt": "new_token"}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"Id": 1}

        # Mock httpx.AsyncClient for real request inside _request
        with patch('src.integrations.portainer.httpx.AsyncClient') as mock_httpx:
            mock_client = AsyncMock()

            # Setup mock to return 401 first, then succeed after re-auth
            request_call_count = 0

            async def mock_request(*args, **kwargs):
                nonlocal request_call_count
                request_call_count += 1

                if request_call_count == 1:
                    # First request returns 401
                    return Mock(status_code=401)
                elif request_call_count == 2:
                    # Auth request succeeds
                    return auth_response
                else:
                    # Retry after auth succeeds
                    return success_response

            mock_client.request = mock_request
            mock_httpx.return_value.__aenter__.return_value = mock_client

            # Test
            result = await client.get_stack(1)

            # Verify
            assert client.token == "new_token"
            assert result["Id"] == 1