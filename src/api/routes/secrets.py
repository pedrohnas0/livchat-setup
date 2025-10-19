"""
Secrets routes for LivChatSetup API

Endpoints for secrets management (Ansible Vault):
- GET /api/secrets - List secret keys (without values)
- GET /api/secrets/{key} - Get secret value
- PUT /api/secrets/{key} - Set secret value
- DELETE /api/secrets/{key} - Delete secret
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging

try:
    from ..dependencies import get_orchestrator
    from ..models.secrets import (
        SecretListResponse,
        SecretGetResponse,
        SecretSetRequest,
        SecretSetResponse,
        SecretDeleteResponse
    )
    from ...orchestrator import Orchestrator
except ImportError:
    from src.api.dependencies import get_orchestrator
    from src.api.models.secrets import (
        SecretListResponse,
        SecretGetResponse,
        SecretSetRequest,
        SecretSetResponse,
        SecretDeleteResponse
    )
    from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/secrets", tags=["Secrets"])


@router.get("", response_model=SecretListResponse)
async def list_secret_keys(
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List all secret keys (without values)

    Returns only the keys stored in the Ansible Vault, not the actual values.
    This is safe to expose as keys are not sensitive (e.g., 'hetzner_token').

    Returns:
        SecretListResponse with list of secret keys
    """
    try:
        keys = orchestrator.storage.secrets.list_secret_keys()

        return SecretListResponse(
            keys=keys,
            total=len(keys)
        )

    except Exception as e:
        logger.error(f"Failed to list secret keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}", response_model=SecretGetResponse)
async def get_secret(
    key: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get secret value by key

    Retrieves and decrypts a secret from the Ansible Vault.

    Args:
        key: Secret key to retrieve

    Returns:
        SecretGetResponse with key and decrypted value

    Raises:
        404: Secret not found
    """
    try:
        value = orchestrator.storage.secrets.get_secret(key)

        if value is None:
            raise HTTPException(
                status_code=404,
                detail=f"Secret '{key}' not found in vault"
            )

        return SecretGetResponse(
            key=key,
            value=value
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get secret {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{key}", response_model=SecretSetResponse)
async def set_secret(
    key: str,
    request: SecretSetRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Set secret value

    Encrypts and stores a secret in the Ansible Vault.
    If the secret already exists, it will be overwritten.

    **Important secrets:**
    - `hetzner_token`: Required for Hetzner Cloud provider
    - `cloudflare_email`: Required for Cloudflare DNS
    - `cloudflare_api_key`: Required for Cloudflare DNS
    - `{app}_password`: Generated passwords for deployed apps

    Args:
        key: Secret key to set
        request: Secret value in request body

    Returns:
        SecretSetResponse with success status
    """
    try:
        orchestrator.storage.secrets.set_secret(key, request.value)

        logger.info(f"Secret '{key}' saved to vault")

        # Provide helpful hints for important secrets
        hints = {
            "hetzner_token": "Hetzner token configured. You can now create servers with the Hetzner provider.",
            "cloudflare_email": "Cloudflare email configured. Don't forget to set 'cloudflare_api_key' as well.",
            "cloudflare_api_key": "Cloudflare API key configured. DNS management is now available."
        }

        message = hints.get(key, f"Secret '{key}' saved successfully to vault")

        return SecretSetResponse(
            success=True,
            message=message,
            key=key
        )

    except Exception as e:
        logger.error(f"Failed to set secret {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key}", response_model=SecretDeleteResponse)
async def delete_secret(
    key: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Delete secret from vault

    Permanently removes a secret from the Ansible Vault.

    Args:
        key: Secret key to delete

    Returns:
        SecretDeleteResponse with success status

    Raises:
        404: Secret not found
    """
    try:
        success = orchestrator.storage.secrets.remove_secret(key)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Secret '{key}' not found in vault"
            )

        logger.info(f"Secret '{key}' deleted from vault")

        return SecretDeleteResponse(
            success=True,
            message=f"Secret '{key}' deleted from vault",
            key=key
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete secret {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
