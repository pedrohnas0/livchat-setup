"""Configuration and fixtures for E2E tests

This module provides:
- Automatic credential loading from vault or environment
- Shared fixtures for E2E tests
- Test markers for real vs mock infrastructure
"""

import os
import pytest
from pathlib import Path
from src.storage import StorageManager


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "real: mark test to run with real infrastructure (requires LIVCHAT_E2E_REAL=true)"
    )
    config.addinivalue_line(
        "markers", "mock: mark test to run with mocked infrastructure (default)"
    )


def load_credentials_to_env():
    """
    Load credentials from vault to environment variables if not already set
    This runs once per test session
    """
    credentials_map = {
        "hetzner_token": "HETZNER_TOKEN",
        "cloudflare_email": "CLOUDFLARE_EMAIL",
        "cloudflare_api_key": "CLOUDFLARE_API_KEY",
        "admin_email": "ADMIN_EMAIL"
    }

    try:
        storage = StorageManager()

        for vault_key, env_var in credentials_map.items():
            # Skip if already in environment
            if os.environ.get(env_var):
                continue

            # Try to load from vault
            value = storage.secrets.get_secret(vault_key)
            if value:
                os.environ[env_var] = value
                print(f"📦 Loaded {vault_key} from vault → {env_var}")
    except Exception as e:
        print(f"⚠️  Could not load credentials from vault: {e}")


# Load credentials once when pytest starts
load_credentials_to_env()


@pytest.fixture(scope="session")
def use_real_infrastructure():
    """Check if we should use real infrastructure"""
    return os.environ.get("LIVCHAT_E2E_REAL", "false").lower() == "true"


@pytest.fixture(scope="session")
def keep_on_failure():
    """Check if we should keep resources on test failure"""
    return os.environ.get("LIVCHAT_E2E_KEEP_ON_FAILURE", "false").lower() == "true"


@pytest.fixture(scope="session")
def hetzner_token():
    """Get Hetzner token from environment"""
    token = os.environ.get("HETZNER_TOKEN")
    if not token:
        pytest.skip("HETZNER_TOKEN not available")
    return token


@pytest.fixture(scope="session")
def cloudflare_credentials():
    """Get Cloudflare credentials from environment"""
    return {
        "email": os.environ.get("CLOUDFLARE_EMAIL"),
        "api_key": os.environ.get("CLOUDFLARE_API_KEY")
    }


@pytest.fixture
def test_server_name():
    """Generate unique test server name"""
    import time
    timestamp = int(time.time())
    return f"e2e-test-{timestamp}"


@pytest.fixture
def cleanup_tracker():
    """Track resources for cleanup"""
    resources = {
        "servers": [],
        "dns_records": []
    }
    yield resources

    # Cleanup code can be added here if needed
    if resources["servers"]:
        print(f"\n⚠️  Servers created during test: {resources['servers']}")
    if resources["dns_records"]:
        print(f"⚠️  DNS records created: {resources['dns_records']}")