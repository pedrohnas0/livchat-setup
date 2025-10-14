"""
Pydantic models for Server API

Request and response models for server-related endpoints
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class ServerCreateRequest(BaseModel):
    """Request to create a new server"""
    name: str = Field(..., min_length=1, max_length=50, description="Server name (unique)")
    server_type: str = Field("cx21", description="Server type (e.g., cx21, cx31)")
    region: str = Field("nbg1", description="Region (e.g., nbg1, fsn1, hel1)")
    image: str = Field("ubuntu-22.04", description="OS image")
    ssh_keys: Optional[List[str]] = Field(None, description="SSH key names to add")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "production-1",
                "server_type": "cx21",
                "region": "nbg1",
                "image": "ubuntu-22.04",
                "ssh_keys": ["main-key"]
            }
        }


class ServerSetupRequest(BaseModel):
    """Request to setup a server (v0.2.0: DNS now required)"""
    # Infrastructure configuration
    ssl_email: str = Field("admin@example.com", description="Email for Let's Encrypt SSL certificates")
    network_name: str = Field("livchat_network", description="Docker Swarm overlay network name")
    timezone: str = Field("America/Sao_Paulo", description="Server timezone")

    # DNS configuration (v0.2.0: REQUIRED)
    zone_name: str = Field(..., min_length=3, description="DNS zone/domain registered in Cloudflare (REQUIRED)")
    subdomain: Optional[str] = Field(None, description="Subdomain prefix (optional, ex: 'lab', 'dev', 'prod')")

    class Config:
        json_schema_extra = {
            "example": {
                "ssl_email": "admin@example.com",
                "network_name": "livchat_network",
                "timezone": "America/Sao_Paulo",
                "zone_name": "livchat.ai",
                "subdomain": "lab"
            }
        }


class ServerInfo(BaseModel):
    """Server information"""
    name: str = Field(..., description="Server name")
    provider: str = Field(..., description="Provider (hetzner, digitalocean, etc.)")
    server_type: str = Field(..., description="Server type")
    region: str = Field(..., description="Region")
    ip_address: Optional[str] = Field(None, description="Public IP address")
    status: str = Field(..., description="Server status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "production-1",
                "provider": "hetzner",
                "server_type": "cx21",
                "region": "nbg1",
                "ip_address": "123.45.67.89",
                "status": "running",
                "created_at": "2024-12-16T10:00:00",
                "metadata": {
                    "provider_id": "12345",
                    "setup_completed": True,
                    "docker_installed": True,
                    "swarm_initialized": True
                }
            }
        }


class ServerListResponse(BaseModel):
    """List of servers"""
    servers: List[ServerInfo] = Field(..., description="List of servers")
    total: int = Field(..., description="Total number of servers")

    class Config:
        json_schema_extra = {
            "example": {
                "servers": [
                    {
                        "name": "production-1",
                        "provider": "hetzner",
                        "server_type": "cx21",
                        "region": "nbg1",
                        "ip_address": "123.45.67.89",
                        "status": "running",
                        "created_at": "2024-12-16T10:00:00",
                        "metadata": {}
                    }
                ],
                "total": 1
            }
        }


class ServerCreateResponse(BaseModel):
    """Response from server creation (returns job)"""
    job_id: str = Field(..., description="Job ID for tracking creation progress")
    message: str = Field(..., description="Status message")
    server_name: str = Field(..., description="Name of server being created")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "create_server-abc123",
                "message": "Server creation started",
                "server_name": "production-1"
            }
        }


class ServerDeleteResponse(BaseModel):
    """Response from server deletion (returns job)"""
    job_id: str = Field(..., description="Job ID for tracking deletion progress")
    message: str = Field(..., description="Status message")
    server_name: str = Field(..., description="Name of server being deleted")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "delete_server-abc123",
                "message": "Server deletion started",
                "server_name": "production-1"
            }
        }


class ServerSetupResponse(BaseModel):
    """Response from server setup (returns job)"""
    job_id: str = Field(..., description="Job ID for tracking setup progress")
    message: str = Field(..., description="Status message")
    server_name: str = Field(..., description="Name of server being setup")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "setup_server-abc123",
                "message": "Server setup started",
                "server_name": "production-1"
            }
        }


class DNSConfig(BaseModel):
    """DNS configuration"""
    zone_name: str = Field(..., description="DNS zone/domain (ex: 'livchat.ai', 'example.com')")
    subdomain: Optional[str] = Field(None, description="Subdomain prefix (ex: 'lab', 'dev', 'prod')")

    class Config:
        json_schema_extra = {
            "example": {
                "zone_name": "livchat.ai",
                "subdomain": "lab"
            }
        }


class DNSConfigureRequest(BaseModel):
    """Request to configure DNS for a server"""
    zone_name: str = Field(..., min_length=3, description="DNS zone/domain registered in Cloudflare")
    subdomain: Optional[str] = Field(None, description="Subdomain prefix (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "zone_name": "livchat.ai",
                "subdomain": "lab"
            }
        }


class DNSConfigureResponse(BaseModel):
    """Response from DNS configuration"""
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Success message")
    server_name: str = Field(..., description="Server name")
    dns_config: DNSConfig = Field(..., description="DNS configuration")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "DNS configuration saved for server 'production-1'",
                "server_name": "production-1",
                "dns_config": {
                    "zone_name": "livchat.ai",
                    "subdomain": "lab"
                }
            }
        }


class DNSGetResponse(BaseModel):
    """Response from getting DNS configuration"""
    server_name: str = Field(..., description="Server name")
    dns_config: DNSConfig = Field(..., description="DNS configuration")

    class Config:
        json_schema_extra = {
            "example": {
                "server_name": "production-1",
                "dns_config": {
                    "zone_name": "livchat.ai",
                    "subdomain": "lab"
                }
            }
        }
