"""
TDD Tests for StateStore - Settings Management

Tests written FIRST before implementation.
"""

import pytest
from pathlib import Path
import json
import tempfile
from src.storage import StateStore


class TestStateStoreSettings:
    """Test settings management in StateStore"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def state_store(self, temp_dir):
        """Create StateStore instance for testing"""
        return StateStore(temp_dir)

    # TDD Test 1: get_setting returns None for missing key
    def test_get_setting_returns_none_for_missing_key(self, state_store):
        """Should return None when setting key doesn't exist"""
        result = state_store.get_setting("nonexistent_key")
        assert result is None

    # TDD Test 2: get_setting returns default value when provided
    def test_get_setting_returns_default_when_provided(self, state_store):
        """Should return default value when key doesn't exist"""
        result = state_store.get_setting("email", "default@example.com")
        assert result == "default@example.com"

    # TDD Test 3: set_setting stores value correctly
    def test_set_setting_stores_value(self, state_store):
        """Should store setting value in state.json"""
        state_store.set_setting("email", "admin@livchat.ai")

        # Verify it was stored
        result = state_store.get_setting("email")
        assert result == "admin@livchat.ai"

    # TDD Test 4: set_setting creates settings section if missing
    def test_set_setting_creates_settings_section(self, state_store):
        """Should create 'settings' section in state if it doesn't exist"""
        state_store.set_setting("name", "Pedro")

        # Load raw state and verify structure
        state_file = state_store.config_dir / "state.json"
        with open(state_file) as f:
            data = json.load(f)

        assert "settings" in data
        assert data["settings"]["name"] == "Pedro"

    # TDD Test 5: multiple settings stored correctly
    def test_multiple_settings_stored_correctly(self, state_store):
        """Should store multiple settings without overwriting each other"""
        state_store.set_setting("email", "admin@livchat.ai")
        state_store.set_setting("name", "Pedro")
        state_store.set_setting("surname", "Silva")
        state_store.set_setting("company_name", "LivChat")

        assert state_store.get_setting("email") == "admin@livchat.ai"
        assert state_store.get_setting("name") == "Pedro"
        assert state_store.get_setting("surname") == "Silva"
        assert state_store.get_setting("company_name") == "LivChat"

    # TDD Test 6: settings persist across instances
    def test_settings_persist_across_instances(self, temp_dir):
        """Settings should persist when creating new StateStore instance"""
        # First instance - set values
        store1 = StateStore(temp_dir)
        store1.set_setting("email", "persist@test.com")
        store1.set_setting("name", "Test User")

        # Second instance - should load persisted values
        store2 = StateStore(temp_dir)
        assert store2.get_setting("email") == "persist@test.com"
        assert store2.get_setting("name") == "Test User"

    # TDD Test 7: update existing setting
    def test_update_existing_setting(self, state_store):
        """Should update existing setting value"""
        state_store.set_setting("email", "old@example.com")
        state_store.set_setting("email", "new@example.com")

        result = state_store.get_setting("email")
        assert result == "new@example.com"

    # TDD Test 8: settings don't interfere with servers data
    def test_settings_dont_interfere_with_servers(self, state_store):
        """Settings and servers should coexist in state.json"""
        # Add a server
        state_store.add_server("test-server", {
            "provider": "hetzner",
            "ip": "1.2.3.4"
        })

        # Add settings
        state_store.set_setting("email", "admin@test.com")

        # Both should exist
        assert state_store.get_setting("email") == "admin@test.com"
        assert state_store.get_server("test-server") is not None
        assert state_store.get_server("test-server")["ip"] == "1.2.3.4"
