"""
Pydantic models for Provider API

Request and response models for cloud provider endpoints
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProviderInfo(BaseModel):
    """Information about a cloud provider"""
    name: str = Field(..., description="Provider name (hetzner, digitalocean, etc)")
    display_name: str = Field(..., description="Human-readable name")
    available: bool = Field(..., description="Whether provider is configured and available")
    configured: bool = Field(..., description="Whether provider has credentials configured")
    status: str = Field(..., description="Provider status (active, unconfigured, error)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "hetzner",
                "display_name": "Hetzner Cloud",
                "available": True,
                "configured": True,
                "status": "active"
            }
        }


class ProviderListResponse(BaseModel):
    """List of available providers"""
    providers: List[ProviderInfo] = Field(..., description="List of cloud providers")
    total: int = Field(..., description="Total number of providers")

    class Config:
        json_schema_extra = {
            "example": {
                "providers": [
                    {
                        "name": "hetzner",
                        "display_name": "Hetzner Cloud",
                        "available": True,
                        "configured": True,
                        "status": "active"
                    }
                ],
                "total": 1
            }
        }


class RegionInfo(BaseModel):
    """Information about a provider region"""
    id: str = Field(..., description="Region identifier")
    name: str = Field(..., description="Region name")
    country: str = Field(..., description="Country code")
    city: Optional[str] = Field(None, description="City name")
    available: bool = Field(..., description="Whether region is available")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "nbg1",
                "name": "Nuremberg 1",
                "country": "DE",
                "city": "Nuremberg",
                "available": True
            }
        }


class RegionListResponse(BaseModel):
    """List of regions for a provider"""
    provider: str = Field(..., description="Provider name")
    regions: List[RegionInfo] = Field(..., description="List of regions")
    total: int = Field(..., description="Total number of regions")

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "hetzner",
                "regions": [
                    {
                        "id": "nbg1",
                        "name": "Nuremberg 1",
                        "country": "DE",
                        "city": "Nuremberg",
                        "available": True
                    }
                ],
                "total": 1
            }
        }


class ServerTypeInfo(BaseModel):
    """Information about a server type/size"""
    id: str = Field(..., description="Server type identifier")
    name: str = Field(..., description="Server type name")
    description: str = Field(..., description="Server type description")
    cores: int = Field(..., description="Number of CPU cores")
    memory_gb: float = Field(..., description="Memory in GB")
    disk_gb: int = Field(..., description="Disk size in GB")
    price_monthly: Optional[float] = Field(None, description="Monthly price")
    available: bool = Field(..., description="Whether server type is available")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cx11",
                "name": "CX11",
                "description": "1 vCPU, 2 GB RAM, 20 GB SSD",
                "cores": 1,
                "memory_gb": 2.0,
                "disk_gb": 20,
                "price_monthly": 4.15,
                "available": True
            }
        }


class ServerTypeListResponse(BaseModel):
    """List of server types for a provider"""
    provider: str = Field(..., description="Provider name")
    server_types: List[ServerTypeInfo] = Field(..., description="List of server types")
    total: int = Field(..., description="Total number of server types")

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "hetzner",
                "server_types": [
                    {
                        "id": "cx11",
                        "name": "CX11",
                        "description": "1 vCPU, 2 GB RAM, 20 GB SSD",
                        "cores": 1,
                        "memory_gb": 2.0,
                        "disk_gb": 20,
                        "price_monthly": 4.15,
                        "available": True
                    }
                ],
                "total": 1
            }
        }


class ProviderDetailsResponse(BaseModel):
    """Detailed information about a provider"""
    name: str = Field(..., description="Provider name")
    display_name: str = Field(..., description="Human-readable name")
    available: bool = Field(..., description="Whether provider is available")
    configured: bool = Field(..., description="Whether provider is configured")
    status: str = Field(..., description="Provider status")
    regions_count: int = Field(..., description="Number of available regions")
    server_types_count: int = Field(..., description="Number of server types")
    capabilities: List[str] = Field(default_factory=list, description="Provider capabilities")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "hetzner",
                "display_name": "Hetzner Cloud",
                "available": True,
                "configured": True,
                "status": "active",
                "regions_count": 3,
                "server_types_count": 12,
                "capabilities": ["create_server", "delete_server", "resize_server"]
            }
        }
