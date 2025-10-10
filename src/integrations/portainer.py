"""
Portainer API client - Native implementation without third-party SDKs
"""
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class PortainerError(Exception):
    """Portainer API error"""
    pass


@dataclass
class StackConfig:
    """Stack configuration"""
    name: str
    compose: str
    endpoint_id: int
    env: Dict[str, str] = None


class PortainerClient:
    """
    Portainer API client

    Native REST client for Portainer API v2.x
    """

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize Portainer client

        Args:
            url: Portainer URL (e.g., https://portainer.example.com)
            username: Admin username
            password: Admin password
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        # Increase timeout for initial connections to remote servers
        self.timeout = httpx.Timeout(60.0, connect=30.0)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @retry(
        stop=stop_after_attempt(5),  # More attempts for initial connection
        wait=wait_exponential(multiplier=2, min=4, max=30),  # Longer waits between attempts
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectTimeout, httpx.ConnectError))
    )
    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method
            path: API path
            **kwargs: Additional request arguments
        """
        url = f"{self.url}{path}"
        headers = kwargs.pop('headers', {})

        # Add auth header if we have a token
        if self.token and 'Authorization' not in headers:
            headers['Authorization'] = f"Bearer {self.token}"

        # Disable SSL verification for self-signed certificates
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )

            # If unauthorized, try to refresh token once
            if response.status_code == 401 and path != "/api/auth":
                logger.info("Token expired, re-authenticating...")
                await self.authenticate()

                # Retry request with new token
                headers['Authorization'] = f"Bearer {self.token}"
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    **kwargs
                )

            return response

    async def authenticate(self) -> str:
        """
        Authenticate with Portainer

        Returns:
            JWT token
        """
        logger.info(f"Authenticating with Portainer at {self.url}")

        response = await self._request(
            "POST",
            "/api/auth",
            json={"username": self.username, "password": self.password}
        )

        if response.status_code != 200:
            raise PortainerError(f"Authentication failed: {response.text}")

        data = response.json()
        self.token = data["jwt"]
        logger.info("Successfully authenticated with Portainer")
        return self.token

    async def create_stack(self, name: str, compose: str, endpoint_id: int = 1,
                          env: Dict[str, str] = None) -> Dict:
        """
        Create a new stack

        Args:
            name: Stack name
            compose: Docker Compose content
            endpoint_id: Endpoint ID (default: 1 for local)
            env: Environment variables

        Returns:
            Stack information
        """
        if not self.token:
            await self.authenticate()

        logger.info(f"Creating stack '{name}' on endpoint {endpoint_id}")

        # Get Swarm ID (REQUIRED for stack creation)
        swarm_id = await self.get_swarm_id(endpoint_id)

        # Prepare environment variables
        env_list = []
        if env:
            env_list = [{"name": k, "value": v} for k, v in env.items()]

        # Prepare request body
        body = {
            "Name": name,
            "SwarmID": swarm_id,  # Required field for Swarm stacks
            "StackFileContent": compose,
            "Env": env_list
        }

        response = await self._request(
            "POST",
            "/api/stacks/create/swarm/string",  # Correct endpoint for Swarm stacks
            params={"endpointId": endpoint_id},
            json=body,
            headers=self._get_headers()
        )

        if response.status_code not in (200, 201):
            raise PortainerError(f"Failed to create stack: {response.text}")

        result = response.json()
        logger.info(f"Stack '{name}' created with ID {result['Id']}")
        return result

    async def get_stack(self, stack_id: int) -> Dict:
        """
        Get stack information

        Args:
            stack_id: Stack ID

        Returns:
            Stack details
        """
        if not self.token:
            await self.authenticate()

        response = await self._request(
            "GET",
            f"/api/stacks/{stack_id}",
            headers=self._get_headers()
        )

        if response.status_code == 404:
            raise PortainerError(f"Stack {stack_id} not found")
        elif response.status_code != 200:
            raise PortainerError(f"Failed to get stack: {response.text}")

        return response.json()

    async def get_stack_by_name(self, name: str) -> Optional[Dict]:
        """
        Get stack by name

        Args:
            name: Stack name

        Returns:
            Stack details or None if not found
        """
        stacks = await self.list_stacks()
        for stack in stacks:
            if stack["Name"] == name:
                return stack
        return None

    async def list_stacks(self) -> List[Dict]:
        """
        List all stacks

        Returns:
            List of stacks
        """
        if not self.token:
            await self.authenticate()

        response = await self._request(
            "GET",
            "/api/stacks",
            headers=self._get_headers()
        )

        if response.status_code != 200:
            raise PortainerError(f"Failed to list stacks: {response.text}")

        return response.json()

    async def delete_stack(self, stack_id: int, external: bool = False) -> bool:
        """
        Delete a stack

        Args:
            stack_id: Stack ID
            external: Whether volumes are external

        Returns:
            Success status
        """
        if not self.token:
            await self.authenticate()

        logger.info(f"Deleting stack {stack_id}")

        response = await self._request(
            "DELETE",
            f"/api/stacks/{stack_id}",
            params={"external": external},
            headers=self._get_headers()
        )

        if response.status_code == 204:
            logger.info(f"Stack {stack_id} deleted successfully")
            return True
        elif response.status_code == 404:
            logger.warning(f"Stack {stack_id} not found")
            return False
        else:
            raise PortainerError(f"Failed to delete stack: {response.text}")

    async def list_endpoints(self) -> List[Dict]:
        """
        List all endpoints (environments)

        Returns:
            List of endpoints
        """
        if not self.token:
            await self.authenticate()

        response = await self._request(
            "GET",
            "/api/endpoints",
            headers=self._get_headers()
        )

        if response.status_code != 200:
            raise PortainerError(f"Failed to list endpoints: {response.text}")

        return response.json()

    async def get_swarm_id(self, endpoint_id: int) -> str:
        """
        Get Docker Swarm ID for an endpoint

        Args:
            endpoint_id: Endpoint ID

        Returns:
            Swarm ID string

        Raises:
            PortainerError: If Swarm ID cannot be retrieved
        """
        if not self.token:
            await self.authenticate()

        logger.info(f"Getting Swarm ID for endpoint {endpoint_id}")

        response = await self._request(
            "GET",
            f"/api/endpoints/{endpoint_id}/docker/swarm",
            headers=self._get_headers()
        )

        if response.status_code != 200:
            raise PortainerError(f"Failed to get Swarm ID: {response.text}")

        data = response.json()
        swarm_id = data.get("ID")

        if not swarm_id:
            raise PortainerError("Swarm ID not found in response")

        logger.info(f"Got Swarm ID: {swarm_id}")
        return swarm_id

    async def create_endpoint(self, name: str = "primary",
                             endpoint_url: str = "tcp://tasks.agent:9001") -> Dict:
        """
        Create a new endpoint (environment) in Portainer

        Args:
            name: Endpoint name
            endpoint_url: Agent endpoint URL

        Returns:
            Created endpoint information
        """
        if not self.token:
            await self.authenticate()

        logger.info(f"Creating Portainer endpoint: {name}")

        # Create endpoint for Docker Swarm with agent
        # Type 2 = Agent environment
        body = {
            "Name": name,
            "Type": 2,  # 2 = Agent environment
            "URL": endpoint_url
        }

        response = await self._request(
            "POST",
            "/api/endpoints",
            json=body,
            headers=self._get_headers()
        )

        if response.status_code not in (200, 201):
            raise PortainerError(f"Failed to create endpoint: {response.text}")

        result = response.json()
        logger.info(f"Endpoint created with ID: {result.get('Id')}")
        return result

    async def get_endpoint(self, endpoint_id: int) -> Dict:
        """
        Get endpoint information

        Args:
            endpoint_id: Endpoint ID

        Returns:
            Endpoint details
        """
        if not self.token:
            await self.authenticate()

        response = await self._request(
            "GET",
            f"/api/endpoints/{endpoint_id}",
            headers=self._get_headers()
        )

        if response.status_code == 404:
            raise PortainerError(f"Endpoint {endpoint_id} not found")
        elif response.status_code != 200:
            raise PortainerError(f"Failed to get endpoint: {response.text}")

        return response.json()

    async def update_stack(self, stack_id: int, compose: str,
                          env: Dict[str, str] = None) -> Dict:
        """
        Update an existing stack

        Args:
            stack_id: Stack ID
            compose: New Docker Compose content
            env: Environment variables

        Returns:
            Updated stack information
        """
        if not self.token:
            await self.authenticate()

        logger.info(f"Updating stack {stack_id}")

        # Get current stack info
        stack = await self.get_stack(stack_id)
        endpoint_id = stack["EndpointId"]

        # Prepare environment variables
        env_list = []
        if env:
            env_list = [{"name": k, "value": v} for k, v in env.items()]

        # Prepare request body
        body = {
            "StackFileContent": compose,
            "Env": env_list,
            "Prune": False
        }

        response = await self._request(
            "PUT",
            f"/api/stacks/{stack_id}",
            params={"endpointId": endpoint_id},
            json=body,
            headers=self._get_headers()
        )

        if response.status_code != 200:
            raise PortainerError(f"Failed to update stack: {response.text}")

        result = response.json()
        logger.info(f"Stack {stack_id} updated successfully")
        return result

    async def get_stack_logs(self, stack_id: int, tail: int = 100) -> str:
        """
        Get stack logs

        Args:
            stack_id: Stack ID
            tail: Number of lines to return

        Returns:
            Log content
        """
        if not self.token:
            await self.authenticate()

        # Get stack info to find services
        stack = await self.get_stack(stack_id)

        # This would need to query individual service logs
        # Portainer doesn't have a direct stack logs endpoint
        # Implementation would depend on specific needs

        logger.warning("Stack logs not fully implemented yet")
        return f"Logs for stack {stack['Name']} (ID: {stack_id})"

    async def health_check(self) -> bool:
        """
        Check Portainer health

        Returns:
            True if healthy
        """
        try:
            response = await self._request("GET", "/api/system/status")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")  # Debug level to reduce noise during wait
            return False

    async def verify_health(self) -> bool:
        """Alias for health_check for compatibility"""
        return await self.health_check()

    async def initialize_admin(self, username: str = None, password: str = None) -> bool:
        """
        Initialize Portainer admin account on first setup

        This is called when Portainer is first installed and needs
        an admin account to be created.

        Args:
            username: Admin username (uses self.username if not provided)
            password: Admin password (uses self.password if not provided)

        Returns:
            True if initialization successful or already initialized
        """
        username = username or self.username
        password = password or self.password

        logger.info(f"Initializing Portainer admin account for {username}")

        # Check if already initialized by trying to authenticate
        try:
            await self.authenticate()
            logger.info("Portainer already initialized")
            return True
        except PortainerError:
            # Not initialized yet, proceed with initialization
            pass

        # Initialize admin account
        try:
            response = await self._request(
                "POST",
                "/api/users/admin/init",
                json={
                    "Username": username,
                    "Password": password
                }
            )

            if response.status_code in (200, 201):
                data = response.json()
                if data.get("Username") == username:
                    logger.info(f"Successfully initialized Portainer admin: {username}")
                    # Now authenticate to get token
                    await self.authenticate()
                    return True
                else:
                    logger.error(f"Unexpected response during init: {data}")
                    return False

            elif response.status_code == 409:
                # Already initialized
                logger.info("Portainer admin already initialized")
                return True

            else:
                logger.error(f"Failed to initialize admin: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error during admin initialization: {e}")
            return False

    async def wait_for_ready(self, max_attempts: int = 30, delay: int = 10) -> bool:
        """
        Wait for Portainer to be ready and accessible

        Args:
            max_attempts: Maximum number of attempts
            delay: Delay between attempts in seconds

        Returns:
            True if Portainer is ready
        """
        import asyncio

        logger.info(f"Waiting for Portainer to be ready (max {max_attempts * delay}s)...")

        for attempt in range(1, max_attempts + 1):
            try:
                if await self.health_check():
                    logger.info(f"Portainer is ready after {attempt} attempts")
                    return True
            except Exception as e:
                logger.debug(f"Attempt {attempt}/{max_attempts}: {e}")

            if attempt < max_attempts:
                logger.info(f"Waiting {delay}s before retry ({attempt}/{max_attempts})...")
                await asyncio.sleep(delay)

        logger.error(f"Portainer did not become ready after {max_attempts} attempts")
        return False