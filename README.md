# LivChat Setup

Automated server setup and application deployment system with AI integration via MCP.

## Features

- 🚀 Automated VPS creation and setup
- 🐳 Docker Swarm orchestration
- 📦 Application dependency management
- 🔐 Secure credential management
- 🤖 AI control via Model Context Protocol (MCP)
- ☁️ Multi-cloud provider support (starting with Hetzner)

## Installation

```bash
pip install livchat-setup
```

## Quick Start

```python
from livchat import LivChatSetup

# Initialize
setup = LivChatSetup()
setup.init()

# Configure provider
setup.configure_provider("hetzner", token="your-token")

# Create server
server = setup.create_server("prod-01", "cx21", "nbg1")
print(f"Server created: {server['ip']}")
```

## Documentation

See [DESIGN.md](DESIGN.md) for architecture details and [plans/](plans/) for implementation plans.

## License

MIT