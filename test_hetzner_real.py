#!/usr/bin/env python3
"""Test real Hetzner server creation"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from __init__ import LivChatSetup

# API token
TOKEN = "8dg9O3tlbHwK5zX3mwgKbd9GKLE8G0joKfRAxDcSi6rRUYsA4didSfApM6R066xh"

print("🚀 HETZNER REAL API TEST")
print("=" * 50)

try:
    # Initialize
    print("\n1. Initializing LivChat Setup...")
    setup = LivChatSetup()
    setup.init()
    print("   ✅ Initialized")

    # Configure Hetzner
    print("\n2. Configuring Hetzner provider...")
    setup.configure_provider("hetzner", TOKEN)
    print("   ✅ Provider configured")

    # List current servers
    print("\n3. Checking existing servers...")
    existing = setup.provider.list_servers()
    print(f"   Found {len(existing)} existing servers")
    for server in existing:
        print(f"   - {server['name']}: {server['ip']}")

    # Create test server
    print("\n4. Creating test server...")
    print("   Server type: cpx11 (cheapest)")
    print("   Location: nbg1 (Nuremberg)")
    print("   Name: test-server-01")

    server = setup.create_server(
        name="test-server-01",
        server_type="cpx11",  # Cheapest option
        region="nbg1"
    )

    print(f"\n   ✅ Server created successfully!")
    print(f"   ID: {server['id']}")
    print(f"   IP: {server['ip']}")
    print(f"   Status: {server['status']}")

    # Wait a bit
    print("\n5. Waiting 10 seconds before cleanup...")
    time.sleep(10)

    # Delete server
    print("\n6. Deleting test server...")
    if setup.delete_server("test-server-01"):
        print("   ✅ Server deleted successfully")
    else:
        print("   ⚠️  Failed to delete server")

    print("\n✅ TEST COMPLETE!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n⚠️  Attempting cleanup...")

    # Try to cleanup
    try:
        if 'setup' in locals():
            servers = setup.list_servers()
            if "test-server-01" in servers:
                setup.delete_server("test-server-01")
                print("   ✅ Cleanup successful")
    except:
        print("   ❌ Cleanup failed - please check Hetzner console")