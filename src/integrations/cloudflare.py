"""
Cloudflare API client using official SDK with Global API Key
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from cloudflare import Cloudflare

logger = logging.getLogger(__name__)


class CloudflareError(Exception):
    """Cloudflare API error"""
    pass


@dataclass
class DNSConfig:
    """DNS configuration for a server"""
    zone_name: str
    subdomain: Optional[str] = None

    @property
    def base_domain(self) -> str:
        """Get base domain for DNS records"""
        if self.subdomain:
            return f"{self.subdomain}.{self.zone_name}"
        return self.zone_name

    def get_record_name(self, prefix: str) -> str:
        """Get full record name with prefix"""
        if self.subdomain:
            return f"{prefix}.{self.subdomain}.{self.zone_name}"
        return f"{prefix}.{self.zone_name}"


class CloudflareClient:
    """
    Cloudflare API client using official SDK with Global API Key

    Uses email + Global API Key authentication for full zone management
    """

    # Standard app prefixes mapping
    APP_PREFIXES = {
        "portainer": "ptn",
        "dozzle": "log",
        "grafana": "gfn",
        "pgadmin": "pga",
        "rabbitmq": "rmq",
        "minio": "mno",
        "minio-s3": "s3",
        "directus": "dir",
        "chatwoot": "chat",
        "evolution": "evo",
        "n8n": "edt",
        "n8n-webhook": "whk",
        "pdf": "pdf",
        "wordpress": "wp",
        "nextcloud": "nc",
    }

    def __init__(self, email: str, global_api_key: str):
        """
        Initialize Cloudflare client with Global API Key

        Args:
            email: Cloudflare account email
            global_api_key: Global API Key from Cloudflare dashboard
        """
        self.email = email
        self.api_key = global_api_key
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize the Cloudflare SDK client"""
        try:
            self.client = Cloudflare(
                api_email=self.email,
                api_key=self.api_key
            )
            logger.info(f"Cloudflare client initialized with email: {self.email}")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudflare client: {e}")
            raise CloudflareError(f"Failed to initialize Cloudflare client: {e}")

    async def list_zones(self) -> List[Dict]:
        """
        List all DNS zones available

        Returns:
            List of zone dictionaries
        """
        try:
            zones_response = self.client.zones.list()
            # Convert to list to get proper length and iterate
            zones = list(zones_response)
            logger.info(f"Found {len(zones)} zones")

            # Handle both SDK objects and dict responses (for mocking)
            result = []
            for z in zones:
                if isinstance(z, dict):
                    result.append(z)
                else:
                    result.append({"id": z.id, "name": z.name})
            return result
        except Exception as e:
            logger.error(f"Failed to list zones: {e}")
            raise CloudflareError(f"Failed to list zones: {e}")

    async def get_zone(self, zone_name: str) -> Optional[Dict]:
        """
        Get zone by name

        Args:
            zone_name: Name of the zone (e.g., "livchat.ai")

        Returns:
            Zone dictionary or None if not found
        """
        try:
            zones_response = self.client.zones.list(name=zone_name)
            # Convert to list to properly access elements
            zones = list(zones_response)

            if zones and len(zones) > 0:
                zone = zones[0]
                # Handle both SDK objects and dict responses
                if isinstance(zone, dict):
                    logger.info(f"Found zone: {zone_name} (ID: {zone['id']})")
                    return zone
                else:
                    logger.info(f"Found zone: {zone_name} (ID: {zone.id})")
                    return {"id": zone.id, "name": zone.name}

            logger.warning(f"Zone not found: {zone_name}")
            return None

        except Exception as e:
            logger.error(f"Failed to get zone {zone_name}: {e}")
            raise CloudflareError(f"Failed to get zone: {e}")

    async def create_dns_record(self, zone_id: str, type: str, name: str,
                              content: str, proxied: bool = False,
                              comment: str = None, ttl: int = 1) -> Dict:
        """
        Create a DNS record

        Args:
            zone_id: Zone ID
            type: Record type (A, CNAME, etc.)
            name: Record name
            content: Record content (IP for A, target for CNAME)
            proxied: Enable Cloudflare proxy (always False for our use)
            comment: Comment for the record
            ttl: TTL (1 = automatic)

        Returns:
            Created record dictionary
        """
        try:
            logger.info(f"Creating {type} record: {name} -> {content}")

            # Create record using SDK
            record = self.client.dns.records.create(
                zone_id=zone_id,
                type=type,
                name=name,
                content=content,
                proxied=proxied,
                comment=comment,
                ttl=ttl
            )

            # Handle both SDK objects and dict responses
            if isinstance(record, dict):
                logger.info(f"Created {type} record: {name} (ID: {record['id']})")
                return record
            else:
                logger.info(f"Created {type} record: {name} (ID: {record.id})")
                return {
                    "id": record.id,
                    "type": record.type,
                    "name": record.name,
                    "content": record.content,
                    "proxied": record.proxied,
                    "comment": getattr(record, 'comment', comment)
                }

        except Exception as e:
            logger.error(f"Failed to create DNS record: {e}")
            raise CloudflareError(f"Failed to create DNS record: {e}")

    async def setup_server_dns(self, server: Dict, zone_name: str,
                              subdomain: Optional[str] = None) -> Dict:
        """
        Setup server DNS with A record for Portainer

        Creates/Updates: ptn.{subdomain}.{zone} -> server_ip

        Args:
            server: Server dictionary with 'name' and 'ip' keys
            zone_name: Zone name (e.g., "livchat.ai")
            subdomain: Optional subdomain (e.g., "lab", "dev")

        Returns:
            Result dictionary
        """
        try:
            # Get zone
            zone = await self.get_zone(zone_name)
            if not zone:
                raise CloudflareError(f"Zone {zone_name} not found")

            # Build DNS config
            dns_config = DNSConfig(zone_name, subdomain)
            record_name = dns_config.get_record_name("ptn")

            # Check if record already exists
            existing = await self.get_dns_record(zone["id"], record_name, "A")
            if existing:
                # Check if IP is correct
                if existing["content"] == server["ip"]:
                    logger.info(f"A record already exists with correct IP: {record_name} -> {server['ip']}")
                    return {
                        "success": True,
                        "record_name": record_name,
                        "record_type": "A",
                        "record_id": existing["id"],
                        "message": "Record already exists with correct IP"
                    }
                else:
                    # IP is different, update it
                    logger.warning(f"A record exists with wrong IP: {record_name} -> {existing['content']} (expected: {server['ip']})")
                    record = await self.update_dns_record(
                        zone_id=zone["id"],
                        record_id=existing["id"],
                        type="A",
                        name=record_name,
                        content=server["ip"],
                        proxied=False,
                        comment="portainer"
                    )
                    logger.info(f"Updated DNS record: {record_name} -> {server['ip']}")
                    return {
                        "success": True,
                        "record_name": record_name,
                        "record_type": "A",
                        "record_id": record["id"],
                        "zone_id": zone["id"],
                        "server_ip": server["ip"],
                        "message": f"Record updated from {existing['content']} to {server['ip']}"
                    }

            # Create new A record for Portainer
            record = await self.create_dns_record(
                zone_id=zone["id"],
                type="A",
                name=record_name,
                content=server["ip"],
                proxied=False,
                comment="portainer"
            )

            logger.info(f"Server DNS configured: {record_name} -> {server['ip']}")

            return {
                "success": True,
                "record_name": record_name,
                "record_type": "A",
                "record_id": record["id"],
                "zone_id": zone["id"],
                "server_ip": server["ip"],
                "message": "New record created"
            }

        except Exception as e:
            logger.error(f"Failed to setup server DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def add_app_dns(self, app_prefix: str, zone_name: str,
                         subdomain: Optional[str] = None,
                         comment: Optional[str] = None) -> Dict:
        """
        Add/Update CNAME record for application

        Creates/Updates: {app_prefix}.{subdomain}.{zone} -> ptn.{subdomain}.{zone}

        Args:
            app_prefix: App prefix (e.g., "chat", "edt", "whk")
            zone_name: Zone name (e.g., "livchat.ai")
            subdomain: Optional subdomain (e.g., "lab", "dev")
            comment: Optional comment (defaults to app_prefix)

        Returns:
            Result dictionary
        """
        try:
            # Get zone
            zone = await self.get_zone(zone_name)
            if not zone:
                raise CloudflareError(f"Zone {zone_name} not found")

            # Build DNS config
            dns_config = DNSConfig(zone_name, subdomain)
            record_name = dns_config.get_record_name(app_prefix)
            target = dns_config.get_record_name("ptn")

            # Check if record already exists
            existing = await self.get_dns_record(zone["id"], record_name, "CNAME")
            if existing:
                # Check if target is correct
                if existing["content"] == target:
                    logger.info(f"CNAME record already exists with correct target: {record_name} -> {target}")
                    return {
                        "success": True,
                        "record_name": record_name,
                        "target": target,
                        "record_id": existing["id"],
                        "message": "Record already exists with correct target"
                    }
                else:
                    # Target is different, update it
                    logger.warning(f"CNAME record exists with wrong target: {record_name} -> {existing['content']} (expected: {target})")
                    record = await self.update_dns_record(
                        zone_id=zone["id"],
                        record_id=existing["id"],
                        type="CNAME",
                        name=record_name,
                        content=target,
                        proxied=False,
                        comment=comment or app_prefix
                    )
                    logger.info(f"Updated CNAME record: {record_name} -> {target}")
                    return {
                        "success": True,
                        "record_name": record_name,
                        "target": target,
                        "record_id": record["id"],
                        "zone_id": zone["id"],
                        "message": f"Record updated from {existing['content']} to {target}"
                    }

            # Create new CNAME record
            record = await self.create_dns_record(
                zone_id=zone["id"],
                type="CNAME",
                name=record_name,
                content=target,
                proxied=False,
                comment=comment or app_prefix
            )

            logger.info(f"App DNS configured: {record_name} -> {target}")

            return {
                "success": True,
                "record_name": record_name,
                "target": target,
                "record_id": record["id"],
                "zone_id": zone["id"],
                "message": "New record created"
            }

        except Exception as e:
            logger.error(f"Failed to add app DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def add_app_with_standard_prefix(self, app_name: str, zone_name: str,
                                          subdomain: Optional[str] = None) -> List[Dict]:
        """
        Add DNS for app using standard prefix mapping

        Args:
            app_name: Application name (e.g., "chatwoot", "n8n")
            zone_name: Zone name
            subdomain: Optional subdomain

        Returns:
            List of created records
        """
        results = []

        # Get standard prefix for app
        prefix = self.APP_PREFIXES.get(app_name.lower())
        if not prefix:
            logger.warning(f"No standard prefix for app: {app_name}")
            prefix = app_name[:3].lower()  # Use first 3 letters as fallback

        # Add main app DNS
        result = await self.add_app_dns(
            app_prefix=prefix,
            zone_name=zone_name,
            subdomain=subdomain,
            comment=app_name
        )
        results.append(result)

        # Special case: N8N needs webhook subdomain too
        if app_name.lower() == "n8n":
            webhook_result = await self.add_app_dns(
                app_prefix="whk",
                zone_name=zone_name,
                subdomain=subdomain,
                comment="n8n webhook"
            )
            results.append(webhook_result)

        # Special case: MinIO needs S3 subdomain too
        if app_name.lower() == "minio":
            s3_result = await self.add_app_dns(
                app_prefix="s3",
                zone_name=zone_name,
                subdomain=subdomain,
                comment="backend minio"
            )
            results.append(s3_result)

        return results

    async def list_dns_records(self, zone_id: str, type: Optional[str] = None) -> List[Dict]:
        """
        List DNS records for a zone

        Args:
            zone_id: Zone ID
            type: Optional record type filter

        Returns:
            List of record dictionaries
        """
        try:
            # Get records from API
            if type:
                records_response = self.client.dns.records.list(
                    zone_id=zone_id,
                    type=type
                )
            else:
                records_response = self.client.dns.records.list(
                    zone_id=zone_id
                )

            # Convert to list to properly iterate
            records = list(records_response)

            # Convert to dict
            result = []
            for record in records:
                if isinstance(record, dict):
                    result.append(record)
                else:
                    result.append({
                        "id": record.id,
                        "type": record.type,
                        "name": record.name,
                        "content": record.content,
                        "proxied": record.proxied,
                        "comment": getattr(record, 'comment', None)
                    })

            logger.info(f"Found {len(result)} DNS records")
            return result

        except Exception as e:
            logger.error(f"Failed to list DNS records: {e}")
            raise CloudflareError(f"Failed to list DNS records: {e}")

    async def get_dns_record(self, zone_id: str, name: str,
                           type: Optional[str] = None) -> Optional[Dict]:
        """
        Get specific DNS record

        Args:
            zone_id: Zone ID
            name: Record name
            type: Optional record type

        Returns:
            Record dictionary or None
        """
        try:
            records = await self.list_dns_records(zone_id, type)

            for record in records:
                if record["name"] == name:
                    return record

            return None

        except Exception as e:
            logger.error(f"Failed to get DNS record: {e}")
            return None

    async def update_dns_record(self, zone_id: str, record_id: str,
                              type: str, name: str, content: str,
                              proxied: bool = False, comment: str = None,
                              ttl: int = 1) -> Dict:
        """
        Update an existing DNS record

        Args:
            zone_id: Zone ID
            record_id: Record ID to update
            type: Record type (A, CNAME, etc.)
            name: Record name
            content: New record content (IP for A, target for CNAME)
            proxied: Enable Cloudflare proxy
            comment: Comment for the record
            ttl: TTL (1 = automatic)

        Returns:
            Updated record dictionary
        """
        try:
            logger.info(f"Updating {type} record: {name} -> {content}")

            # Update record using SDK
            record = self.client.dns.records.update(
                zone_id=zone_id,
                dns_record_id=record_id,
                type=type,
                name=name,
                content=content,
                proxied=proxied,
                comment=comment,
                ttl=ttl
            )

            # Handle both SDK objects and dict responses
            if isinstance(record, dict):
                logger.info(f"Updated {type} record: {name} (ID: {record['id']})")
                return record
            else:
                logger.info(f"Updated {type} record: {name} (ID: {record.id})")
                return {
                    "id": record.id,
                    "type": record.type,
                    "name": record.name,
                    "content": record.content,
                    "proxied": record.proxied,
                    "comment": getattr(record, 'comment', comment)
                }

        except Exception as e:
            logger.error(f"Failed to update DNS record: {e}")
            raise CloudflareError(f"Failed to update DNS record: {e}")

    async def delete_dns_record(self, zone_id: str, record_id: str) -> bool:
        """
        Delete a DNS record

        Args:
            zone_id: Zone ID
            record_id: Record ID

        Returns:
            Success status
        """
        try:
            self.client.dns.records.delete(
                zone_id=zone_id,
                dns_record_id=record_id
            )
            logger.info(f"Deleted DNS record: {record_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete DNS record: {e}")
            raise CloudflareError(f"Failed to delete DNS record: {e}")

    async def cleanup_server_dns(self, zone_name: str, subdomain: Optional[str] = None) -> Dict:
        """
        Clean up all DNS records for a server

        Args:
            zone_name: Zone name
            subdomain: Optional subdomain

        Returns:
            Result dictionary with deletion count
        """
        try:
            # Get zone
            zone = await self.get_zone(zone_name)
            if not zone:
                return {"success": False, "error": "Zone not found"}

            # Get all records
            records = await self.list_dns_records(zone["id"])

            # Build pattern to match
            dns_config = DNSConfig(zone_name, subdomain)
            pattern = dns_config.base_domain

            # Delete matching records
            deleted = 0
            for record in records:
                if pattern in record["name"]:
                    await self.delete_dns_record(zone["id"], record["id"])
                    deleted += 1
                    logger.info(f"Deleted record: {record['name']}")

            return {
                "success": True,
                "deleted_count": deleted,
                "zone": zone_name,
                "subdomain": subdomain
            }

        except Exception as e:
            logger.error(f"Failed to cleanup DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }