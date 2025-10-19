"""
Provider routes for LivChatSetup API

Endpoints for cloud provider management:
- GET /api/providers - List available providers
- GET /api/providers/{name} - Get provider details
- GET /api/providers/{name}/regions - List provider regions
- GET /api/providers/{name}/server-types - List provider server types
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging
from typing import Dict, Any

try:
    from ..dependencies import get_orchestrator
    from ..models.provider import (
        ProviderInfo,
        ProviderListResponse,
        ProviderDetailsResponse,
        RegionInfo,
        RegionListResponse,
        ServerTypeInfo,
        ServerTypeListResponse
    )
    from ...orchestrator import Orchestrator
    from ...providers.hetzner import HetznerProvider
except ImportError:
    from src.api.dependencies import get_orchestrator
    from src.api.models.provider import (
        ProviderInfo,
        ProviderListResponse,
        ProviderDetailsResponse,
        RegionInfo,
        RegionListResponse,
        ServerTypeInfo,
        ServerTypeListResponse
    )
    from src.orchestrator import Orchestrator
    from src.providers.hetzner import HetznerProvider

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/providers", tags=["Providers"])

# Provider registry - maps provider names to their classes
PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "hetzner": {
        "class": HetznerProvider,
        "display_name": "Hetzner Cloud",
        "capabilities": ["create_server", "delete_server", "list_servers", "ssh_keys"]
    }
}


def get_provider_instance(provider_name: str, orchestrator: Orchestrator) -> Any:
    """
    Get provider instance by name

    Raises:
        HTTPException: If provider not found or not configured
    """
    if provider_name not in PROVIDER_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' not found"
        )

    provider_info = PROVIDER_REGISTRY[provider_name]
    provider_class = provider_info["class"]

    # Get API token from vault (encrypted storage)
    api_token = orchestrator.storage.secrets.get_secret(f"{provider_name}_token")

    if not api_token:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_name}' is not configured. Use manage-secrets to set {provider_name}_token"
        )

    # Create provider instance
    try:
        provider = provider_class(api_token=api_token)
        return provider
    except Exception as e:
        logger.error(f"Failed to initialize provider {provider_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize provider: {str(e)}"
        )


def check_provider_configured(provider_name: str, orchestrator: Orchestrator) -> bool:
    """Check if provider has credentials configured"""
    api_token = orchestrator.storage.secrets.get_secret(f"{provider_name}_token")
    return api_token is not None and api_token != ""


@router.get("", response_model=ProviderListResponse)
async def list_providers(
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List all available cloud providers

    Returns information about all supported providers, including their
    configuration status and availability.
    """
    try:
        providers = []

        for provider_name, provider_info in PROVIDER_REGISTRY.items():
            configured = check_provider_configured(provider_name, orchestrator)

            # Determine status
            if configured:
                status = "active"
            else:
                status = "unconfigured"

            providers.append(
                ProviderInfo(
                    name=provider_name,
                    display_name=provider_info["display_name"],
                    available=True,  # Provider is available in code
                    configured=configured,
                    status=status
                )
            )

        return ProviderListResponse(
            providers=providers,
            total=len(providers)
        )

    except Exception as e:
        logger.error(f"Failed to list providers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}", response_model=ProviderDetailsResponse)
async def get_provider(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get provider details

    Returns complete information about a specific cloud provider,
    including configuration status and capabilities.

    Raises:
        404: Provider not found
    """
    if name not in PROVIDER_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{name}' not found"
        )

    try:
        provider_info = PROVIDER_REGISTRY[name]
        configured = check_provider_configured(name, orchestrator)

        # Get regions and server types count
        regions_count = 0
        server_types_count = 0

        if configured:
            try:
                provider = get_provider_instance(name, orchestrator)
                regions = provider.get_available_locations()
                server_types = provider.get_available_server_types()
                regions_count = len(regions) if regions else 0
                server_types_count = len(server_types) if server_types else 0
                status_val = "active"
            except Exception as e:
                logger.warning(f"Failed to get provider details: {e}")
                status_val = "error"
        else:
            status_val = "unconfigured"

        return ProviderDetailsResponse(
            name=name,
            display_name=provider_info["display_name"],
            available=True,
            configured=configured,
            status=status_val,
            regions_count=regions_count,
            server_types_count=server_types_count,
            capabilities=provider_info["capabilities"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/regions", response_model=RegionListResponse)
async def list_regions(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List regions for a provider

    Returns all available regions/locations for the specified provider.

    Raises:
        404: Provider not found
        500: Provider not configured or API error
    """
    try:
        provider = get_provider_instance(name, orchestrator)

        # Get locations from provider
        locations = provider.get_available_locations()

        # Convert to RegionInfo models
        regions = [
            RegionInfo(
                id=str(loc.get("id", loc.get("name", ""))),
                name=loc.get("name", ""),
                country=loc.get("country", ""),
                city=loc.get("city"),
                available=True
            )
            for loc in locations
        ]

        return RegionListResponse(
            provider=name,
            regions=regions,
            total=len(regions)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list regions for {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/server-types", response_model=ServerTypeListResponse)
async def list_server_types(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List server types for a provider

    Returns all available server types/sizes for the specified provider.

    Raises:
        404: Provider not found
        500: Provider not configured or API error
    """
    try:
        provider = get_provider_instance(name, orchestrator)

        # Get server types from provider
        types = provider.get_available_server_types()

        # Convert to ServerTypeInfo models
        server_types = [
            ServerTypeInfo(
                id=str(st.get("id", "")),
                name=st.get("name", ""),
                description=st.get("description", ""),
                cores=st.get("cores", 0),
                memory_gb=st.get("memory", 0) / 1024.0 if st.get("memory") else 0.0,  # Convert MB to GB
                disk_gb=st.get("disk", 0),
                price_monthly=st.get("prices", [{}])[0].get("price_monthly", {}).get("gross") if st.get("prices") else None,
                available=True
            )
            for st in types
        ]

        return ServerTypeListResponse(
            provider=name,
            server_types=server_types,
            total=len(server_types)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list server types for {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
