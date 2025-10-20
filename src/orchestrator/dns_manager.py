"""
DNS Manager - Handles DNS configuration for servers and applications

Extracted from orchestrator.py for better modularity (PLAN-08)
"""
import logging
from typing import Optional, Dict, Any

try:
    from ..storage import StorageManager
except ImportError:
    from storage import StorageManager

logger = logging.getLogger(__name__)


class DNSManager:
    """
    Manages DNS configuration for servers and applications

    Responsibilities:
    - Setup DNS records for servers (Portainer A records)
    - Add DNS records for applications
    - Integrate with Cloudflare client
    - Save DNS configuration to state
    """

    def __init__(self, storage: StorageManager, cloudflare=None):
        """
        Initialize DNSManager

        Args:
            storage: Storage manager instance
            cloudflare: Optional Cloudflare client
        """
        self.storage = storage
        self.cloudflare = cloudflare

    async def setup_dns_for_server(
        self,
        server_name: str,
        zone_name: str,
        subdomain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Setup DNS records for a server (Portainer A record)

        Args:
            server_name: Name of the server
            zone_name: Cloudflare zone name (e.g., "livchat.ai")
            subdomain: Optional subdomain (e.g., "lab", "dev")

        Returns:
            Result dictionary with DNS setup status
        """
        if not self.cloudflare:
            return {
                "success": False,
                "error": "Cloudflare not configured. Run configure_cloudflare first."
            }

        server = self.storage.state.get_server(server_name)
        if not server:
            return {
                "success": False,
                "error": f"Server {server_name} not found"
            }

        try:
            # Setup DNS A record for Portainer
            result = await self.cloudflare.setup_server_dns(
                server={"name": server_name, "ip": server["ip"]},
                zone_name=zone_name,
                subdomain=subdomain
            )

            if result["success"]:
                # Save DNS config to state (only zone and subdomain)
                dns_config = {
                    "zone_name": zone_name,
                    "subdomain": subdomain
                }
                server["dns_config"] = dns_config
                self.storage.state.update_server(server_name, server)

                logger.info(f"DNS configured for server {server_name}: {result['record_name']}")

            return result

        except Exception as e:
            logger.error(f"Failed to setup DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def add_app_dns(
        self,
        app_name: str,
        zone_name: str,
        subdomain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add DNS records for an application

        Args:
            app_name: Application name (e.g., "chatwoot", "n8n")
            zone_name: Cloudflare zone name
            subdomain: Optional subdomain

        Returns:
            Result dictionary with DNS setup status
        """
        if not self.cloudflare:
            return {
                "success": False,
                "error": "Cloudflare not configured. Run configure_cloudflare first."
            }

        try:
            # Use standard prefix mapping for the app
            results = await self.cloudflare.add_app_with_standard_prefix(
                app_name=app_name,
                zone_name=zone_name,
                subdomain=subdomain
            )

            # Return summary
            success_count = sum(1 for r in results if r.get("success"))
            return {
                "success": success_count > 0,
                "app": app_name,
                "records_created": success_count,
                "details": results
            }

        except Exception as e:
            logger.error(f"Failed to add app DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
