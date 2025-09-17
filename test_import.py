#!/usr/bin/env python3
"""Quick test to verify imports work"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("Testing imports...")

try:
    from __init__ import LivChatSetup
    print("✓ Main import works")

    from config import ConfigManager
    print("✓ ConfigManager import works")

    from state import StateManager
    print("✓ StateManager import works")

    from vault import SecretsManager
    print("✓ SecretsManager import works")

    from providers.hetzner import HetznerProvider
    print("✓ HetznerProvider import works")

    # Quick functionality test
    setup = LivChatSetup()
    print("✓ LivChatSetup instantiation works")

    print("\n✅ All imports successful! The renaming to src/ is complete.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)