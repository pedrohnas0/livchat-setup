#!/usr/bin/env python3
"""Test script for LivChat Setup initial flow"""

import sys
import shutil
from pathlib import Path
import tempfile

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from __init__ import LivChatSetup


def test_init():
    """Test 1: Initialization"""
    print("=" * 50)
    print("TEST 1: Initialization")
    print("=" * 50)

    # Use temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".livchat_test"

        setup = LivChatSetup(config_dir)
        setup.init()

        # Verify files were created
        assert config_dir.exists(), "Config directory not created"
        assert (config_dir / "config.yaml").exists(), "Config file not created"
        assert (config_dir / "state.json").exists(), "State file not created"
        assert (config_dir / ".vault_password").exists(), "Vault password not created"
        assert (config_dir / "credentials.vault").exists(), "Vault file not created"

        print("✅ Initialization successful")
        print(f"   Config dir: {config_dir}")
        print(f"   Files created: config.yaml, state.json, credentials.vault")
        return True


def test_config():
    """Test 2: Configuration management"""
    print("\n" + "=" * 50)
    print("TEST 2: Configuration Management")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".livchat_test"

        setup = LivChatSetup(config_dir)
        setup.init()

        # Test setting and getting config
        setup.config.set("test_key", "test_value")
        value = setup.config.get("test_key")
        assert value == "test_value", f"Config get/set failed: {value}"

        # Test nested config
        setup.config.set("nested.key", "nested_value")
        nested_value = setup.config.get("nested.key")
        assert nested_value == "nested_value", f"Nested config failed: {nested_value}"

        # Test persistence
        setup2 = LivChatSetup(config_dir)
        persisted_value = setup2.config.get("test_key")
        assert persisted_value == "test_value", f"Config persistence failed: {persisted_value}"

        print("✅ Configuration management working")
        print(f"   Set/Get: OK")
        print(f"   Nested keys: OK")
        print(f"   Persistence: OK")
        return True


def test_secrets():
    """Test 3: Secrets management"""
    print("\n" + "=" * 50)
    print("TEST 3: Secrets Management")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".livchat_test"

        setup = LivChatSetup(config_dir)
        setup.init()

        # Test setting and getting secrets
        setup.secrets.set_secret("test_token", "secret123")
        token = setup.secrets.get_secret("test_token")
        assert token == "secret123", f"Secret get/set failed: {token}"

        # Verify encryption (secret should not be in plain text)
        vault_content = (config_dir / "credentials.vault").read_text()
        assert "secret123" not in vault_content, "Secret not encrypted!"
        assert "$ANSIBLE_VAULT" in vault_content, "Not using Ansible Vault format"

        # Test persistence
        setup2 = LivChatSetup(config_dir)
        persisted_token = setup2.secrets.get_secret("test_token")
        assert persisted_token == "secret123", f"Secret persistence failed: {persisted_token}"

        print("✅ Secrets management working")
        print(f"   Encryption: OK (using Ansible Vault)")
        print(f"   Set/Get: OK")
        print(f"   Persistence: OK")
        return True


def test_state():
    """Test 4: State management"""
    print("\n" + "=" * 50)
    print("TEST 4: State Management")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".livchat_test"

        setup = LivChatSetup(config_dir)
        setup.init()

        # Test adding server to state
        server_data = {
            "provider": "hetzner",
            "id": "123456",
            "ip": "192.168.1.100",
            "type": "cx21",
            "region": "nbg1",
        }

        setup.state.add_server("test-server", server_data)

        # Test getting server
        server = setup.state.get_server("test-server")
        assert server is not None, "Server not found"
        assert server["ip"] == "192.168.1.100", f"Server IP mismatch: {server['ip']}"
        assert "created_at" in server, "Timestamp not added"

        # Test listing servers
        servers = setup.state.list_servers()
        assert len(servers) == 1, f"Expected 1 server, got {len(servers)}"

        # Test persistence
        setup2 = LivChatSetup(config_dir)
        persisted_server = setup2.state.get_server("test-server")
        assert persisted_server is not None, "State not persisted"
        assert persisted_server["ip"] == "192.168.1.100", "Persisted server data mismatch"

        # Test removing server
        setup.state.remove_server("test-server")
        server = setup.state.get_server("test-server")
        assert server is None, "Server not removed"

        print("✅ State management working")
        print(f"   Add server: OK")
        print(f"   Get server: OK")
        print(f"   List servers: OK")
        print(f"   Remove server: OK")
        print(f"   Persistence: OK")
        return True


def test_provider_mock():
    """Test 5: Provider integration (mock)"""
    print("\n" + "=" * 50)
    print("TEST 5: Provider Integration (Mock)")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".livchat_test"

        setup = LivChatSetup(config_dir)
        setup.init()

        # Configure provider with fake token
        setup.configure_provider("hetzner", "fake_test_token")

        # Verify token was saved securely
        saved_token = setup.secrets.get_secret("hetzner_token")
        assert saved_token == "fake_test_token", "Token not saved correctly"

        # Verify provider config
        provider = setup.config.get("provider")
        assert provider == "hetzner", f"Provider config not set: {provider}"

        print("✅ Provider configuration working")
        print(f"   Token saved: OK (encrypted)")
        print(f"   Config updated: OK")
        print(f"   Provider: hetzner")
        return True


def test_complete_flow():
    """Test 6: Complete user flow"""
    print("\n" + "=" * 50)
    print("TEST 6: Complete User Flow")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".livchat_test"

        # Step 1: Initialize
        setup = LivChatSetup(config_dir)
        setup.init()
        print("✅ Step 1: Initialized")

        # Step 2: Configure provider
        setup.configure_provider("hetzner", "fake_token")
        print("✅ Step 2: Provider configured")

        # Step 3: Simulate server creation (without actual API call)
        # We'll mock the server data as if it was created
        mock_server = {
            "id": "999999",
            "name": "test-flow-server",
            "provider": "hetzner",
            "ip": "10.0.0.1",
            "type": "cx21",
            "region": "nbg1",
            "status": "running"
        }
        setup.state.add_server("test-flow-server", mock_server)
        print("✅ Step 3: Server 'created' (mock)")

        # Step 4: List servers
        servers = setup.list_servers()
        assert len(servers) == 1, "Server not in list"
        assert "test-flow-server" in servers, "Server name not found"
        print("✅ Step 4: Server listed")

        # Step 5: Get specific server
        server = setup.get_server("test-flow-server")
        assert server is not None, "Server not found"
        assert server["ip"] == "10.0.0.1", "Server data mismatch"
        print("✅ Step 5: Server retrieved")

        print("\n✅ Complete flow successful!")
        return True


def main():
    """Run all tests"""
    print("\n🚀 LIVCHAT SETUP - TEST SUITE")
    print("Testing basic functionality...\n")

    tests = [
        test_init,
        test_config,
        test_secrets,
        test_state,
        test_provider_mock,
        test_complete_flow,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed: {e}")
            failed += 1
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(tests)}")
        return 1

    print("\n🎉 All tests passed! LivChat Setup is working correctly.")
    print("\n📝 Next steps:")
    print("1. Get a real Hetzner API token")
    print("2. Test actual server creation")
    print("3. Implement Ansible integration")
    print("4. Add application deployment")
    return 0


if __name__ == "__main__":
    sys.exit(main())