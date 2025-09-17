#!/usr/bin/env python3
"""Test real Hetzner API"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from __init__ import LivChatSetup

print("🚀 Testing Real Hetzner API")
print("=" * 50)

# Initialize
print("1. Initializing LivChat Setup...")
setup = LivChatSetup()
setup.init()

# Configure with real token
token