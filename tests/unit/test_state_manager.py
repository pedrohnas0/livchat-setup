"""Unit tests for StateStore dot notation methods"""

import pytest
import json
from pathlib import Path
from src.storage import StateStore


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create a temporary state directory"""
    state_dir = tmp_path / ".livchat"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def state_store(temp_state_dir):
    """Create a StateStore instance with temp directory"""
    store = StateStore(config_dir=temp_state_dir)
    # Initialize with some test data
    store._state = {
        "servers": {
            "prod": {
                "ip": "1.2.3.4",
                "dns_config": {
                    "zone_name": "example.com",
                    "subdomain": "app"
                },
                "status": "running"
            },
            "dev": {
                "ip": "5.6.7.8",
                "dns_config": {
                    "zone_name": "dev.com"
                }
            }
        },
        "settings": {
            "admin_email": "admin@example.com",
            "default_timezone": "America/Sao_Paulo"
        }
    }
    store._loaded = True
    return store


class TestGetByPath:
    """Test get_by_path() method"""

    def test_get_simple_path(self, state_store):
        """Should get value from simple path"""
        result = state_store.get_by_path("settings")
        assert result == {
            "admin_email": "admin@example.com",
            "default_timezone": "America/Sao_Paulo"
        }

    def test_get_nested_path(self, state_store):
        """Should get value from nested path"""
        result = state_store.get_by_path("servers.prod.ip")
        assert result == "1.2.3.4"

    def test_get_deep_nested_path(self, state_store):
        """Should get value from deeply nested path"""
        result = state_store.get_by_path("servers.prod.dns_config.zone_name")
        assert result == "example.com"

    def test_get_object_path(self, state_store):
        """Should get object from path"""
        result = state_store.get_by_path("servers.prod.dns_config")
        assert result == {
            "zone_name": "example.com",
            "subdomain": "app"
        }

    def test_get_nonexistent_path(self, state_store):
        """Should raise KeyError for nonexistent path"""
        with pytest.raises(KeyError) as exc_info:
            state_store.get_by_path("servers.nonexistent")
        assert "Path not found" in str(exc_info.value)

    def test_get_nonexistent_nested_path(self, state_store):
        """Should raise KeyError for nonexistent nested path"""
        with pytest.raises(KeyError) as exc_info:
            state_store.get_by_path("servers.prod.nonexistent.field")
        assert "Path not found" in str(exc_info.value)

    def test_get_root_level(self, state_store):
        """Should get entire state if no path"""
        result = state_store.get_by_path("")
        # Empty string should return root
        assert "servers" in result
        assert "settings" in result


class TestSetByPath:
    """Test set_by_path() method"""

    def test_set_simple_value(self, state_store):
        """Should set value at simple path"""
        state_store.set_by_path("settings.admin_email", "new@example.com")
        assert state_store._state["settings"]["admin_email"] == "new@example.com"

    def test_set_nested_value(self, state_store):
        """Should set value at nested path"""
        state_store.set_by_path("servers.prod.ip", "10.20.30.40")
        assert state_store._state["servers"]["prod"]["ip"] == "10.20.30.40"

    def test_set_deep_nested_value(self, state_store):
        """Should set value at deeply nested path"""
        state_store.set_by_path("servers.prod.dns_config.subdomain", "new-sub")
        assert state_store._state["servers"]["prod"]["dns_config"]["subdomain"] == "new-sub"

    def test_set_creates_intermediate_dicts(self, state_store):
        """Should create intermediate dictionaries if they don't exist"""
        state_store.set_by_path("servers.staging.ip", "192.168.1.1")
        assert state_store._state["servers"]["staging"]["ip"] == "192.168.1.1"

    def test_set_creates_deep_nested_path(self, state_store):
        """Should create deeply nested path"""
        state_store.set_by_path("new.nested.deep.value", "test")
        assert state_store._state["new"]["nested"]["deep"]["value"] == "test"

    def test_set_object_value(self, state_store):
        """Should set object as value"""
        new_dns = {"zone_name": "newzone.com", "subdomain": "api"}
        state_store.set_by_path("servers.prod.dns_config", new_dns)
        assert state_store._state["servers"]["prod"]["dns_config"] == new_dns

    def test_set_array_value(self, state_store):
        """Should set array as value"""
        apps = ["traefik", "portainer", "n8n"]
        state_store.set_by_path("servers.prod.applications", apps)
        assert state_store._state["servers"]["prod"]["applications"] == apps

    def test_set_overwrites_existing(self, state_store):
        """Should overwrite existing value"""
        original = state_store._state["servers"]["prod"]["status"]
        assert original == "running"

        state_store.set_by_path("servers.prod.status", "stopped")
        assert state_store._state["servers"]["prod"]["status"] == "stopped"


class TestDeleteByPath:
    """Test delete_by_path() method"""

    def test_delete_simple_key(self, state_store):
        """Should delete key at simple path"""
        state_store.delete_by_path("settings.admin_email")
        assert "admin_email" not in state_store._state["settings"]
        assert "default_timezone" in state_store._state["settings"]  # Other keys remain

    def test_delete_nested_key(self, state_store):
        """Should delete nested key"""
        state_store.delete_by_path("servers.prod.status")
        assert "status" not in state_store._state["servers"]["prod"]
        assert "ip" in state_store._state["servers"]["prod"]  # Other keys remain

    def test_delete_deep_nested_key(self, state_store):
        """Should delete deeply nested key"""
        state_store.delete_by_path("servers.prod.dns_config.subdomain")
        assert "subdomain" not in state_store._state["servers"]["prod"]["dns_config"]
        assert "zone_name" in state_store._state["servers"]["prod"]["dns_config"]

    def test_delete_nonexistent_key(self, state_store):
        """Should raise KeyError when deleting nonexistent key"""
        with pytest.raises(KeyError):
            state_store.delete_by_path("servers.nonexistent")

    def test_delete_nonexistent_nested_key(self, state_store):
        """Should raise KeyError when deleting nonexistent nested key"""
        with pytest.raises(KeyError):
            state_store.delete_by_path("servers.prod.nonexistent.field")


class TestListKeysAtPath:
    """Test list_keys_at_path() method"""

    def test_list_root_keys(self, state_store):
        """Should list keys at root level"""
        keys = state_store.list_keys_at_path(None)
        assert set(keys) == {"servers", "settings"}

    def test_list_empty_path_string(self, state_store):
        """Should list root keys with empty string"""
        keys = state_store.list_keys_at_path("")
        assert set(keys) == {"servers", "settings"}

    def test_list_nested_keys(self, state_store):
        """Should list keys at nested path"""
        keys = state_store.list_keys_at_path("servers")
        assert set(keys) == {"prod", "dev"}

    def test_list_deep_nested_keys(self, state_store):
        """Should list keys at deeply nested path"""
        keys = state_store.list_keys_at_path("servers.prod")
        assert set(keys) == {"ip", "dns_config", "status"}

    def test_list_object_keys(self, state_store):
        """Should list keys of nested object"""
        keys = state_store.list_keys_at_path("servers.prod.dns_config")
        assert set(keys) == {"zone_name", "subdomain"}

    def test_list_non_dict_value(self, state_store):
        """Should return empty list for non-dict value"""
        keys = state_store.list_keys_at_path("servers.prod.ip")
        assert keys == []

    def test_list_nonexistent_path(self, state_store):
        """Should raise KeyError for nonexistent path"""
        with pytest.raises(KeyError):
            state_store.list_keys_at_path("nonexistent")


class TestPersistence:
    """Test that dot notation methods trigger save()"""

    def test_set_by_path_saves_to_file(self, temp_state_dir):
        """Should save state to file after set_by_path()"""
        store = StateStore(config_dir=temp_state_dir)
        store._state = {"test": {}}
        store._loaded = True

        # Set value
        store.set_by_path("test.key", "value")

        # Verify file was written
        state_file = temp_state_dir / "state.json"
        assert state_file.exists()

        # Verify content
        with open(state_file, 'r') as f:
            data = json.load(f)
        assert data["test"]["key"] == "value"

    def test_delete_by_path_saves_to_file(self, temp_state_dir):
        """Should save state to file after delete_by_path()"""
        store = StateStore(config_dir=temp_state_dir)
        store._state = {"test": {"key1": "val1", "key2": "val2"}}
        store._loaded = True

        # Delete key
        store.delete_by_path("test.key1")

        # Verify file was written
        state_file = temp_state_dir / "state.json"
        with open(state_file, 'r') as f:
            data = json.load(f)

        assert "key1" not in data["test"]
        assert "key2" in data["test"]


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_get_with_dots_in_key(self, state_store):
        """Should handle keys that don't exist gracefully"""
        # This is a limitation - we can't have dots in keys with dot notation
        with pytest.raises(KeyError):
            state_store.get_by_path("servers.prod.dns_config.zone.name")

    def test_empty_path_component(self, state_store):
        """Should handle empty path components"""
        with pytest.raises(KeyError):
            state_store.get_by_path("servers..prod")

    def test_set_on_non_dict_parent(self, state_store):
        """Should handle setting on non-dict parent"""
        # servers.prod.ip is a string, can't set nested value
        with pytest.raises(TypeError):
            state_store.set_by_path("servers.prod.ip.nested", "value")

    def test_numeric_values(self, state_store):
        """Should handle numeric values correctly"""
        state_store.set_by_path("servers.prod.port", 8080)
        assert state_store.get_by_path("servers.prod.port") == 8080

    def test_boolean_values(self, state_store):
        """Should handle boolean values correctly"""
        state_store.set_by_path("servers.prod.enabled", True)
        assert state_store.get_by_path("servers.prod.enabled") is True

    def test_null_values(self, state_store):
        """Should handle None values correctly"""
        state_store.set_by_path("servers.prod.metadata", None)
        assert state_store.get_by_path("servers.prod.metadata") is None
