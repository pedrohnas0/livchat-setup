# LivChat Setup v0.2.0

Automated server setup and application deployment system with AI integration via MCP.

**v0.2.0 - DNS-First Architecture**: Mandatory DNS configuration during server setup for seamless application deployment.

## 🎯 Features

- 🚀 **Automated VPS Creation**: One-command server provisioning on Hetzner Cloud
- 🌐 **DNS-First Architecture** (v0.2.0): Mandatory DNS configuration with automatic domain assignment
- 🐳 **Docker Swarm Orchestration**: Full container orchestration with service management
- 📦 **Smart Dependency Resolution**: Automatic installation of required services (like npm install!)
- 🏗️ **Infrastructure as Apps**: Traefik and Portainer deployed as applications
- 🔐 **Secure Credential Management**: Ansible Vault encryption for all secrets
- 🤖 **AI Control via MCP**: Full integration with Claude via Model Context Protocol
- ☁️ **Multi-Cloud Ready**: Currently supports Hetzner, designed for easy provider addition

## 📦 Installation

### Python Package (Core)

```bash
pip install livchat-setup
```

### MCP Server (AI Integration)

```bash
npm install -g @pedrohnas/livchat-setup-mcp
```

## 🚀 Quick Start

### Via MCP (with Claude)

1. Configure MCP in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "livchat-setup": {
      "command": "npx",
      "args": ["@pedrohnas/livchat-setup-mcp"],
      "env": {
        "LIVCHAT_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

2. Start the API server:

```bash
# Start API (terminal 1)
livchat-setup serve
```

3. Use via Claude:

```
"Create a server called prod-01 on Hetzner with type cx21 in region nbg1"
"Setup the server with DNS zone example.com and subdomain prod"
"Deploy the infrastructure bundle (Traefik + Portainer)"
"Deploy N8N on prod-01"  # Will auto-install postgres + redis!
```

### Via Python API

```python
from orchestrator import Orchestrator

# Initialize
orch = Orchestrator()
orch.init()

# Configure provider
orch.configure_provider("hetzner", "your-hetzner-token")

# Create server (takes ~30s)
server = orch.create_server_sync("prod-01", "cx21", "nbg1")

# Setup with DNS (v0.2.0: DNS is MANDATORY!)
result = orch.setup_server_sync(
    "prod-01",
    zone_name="example.com",    # REQUIRED
    subdomain="prod",            # OPTIONAL
    ssl_email="admin@example.com"
)

# Deploy infrastructure bundle
orch.deploy_infrastructure_sync("prod-01")

# Deploy N8N (auto-installs postgres + redis)
orch.deploy_app_sync("prod-01", "n8n")
```

## 🌟 What's New in v0.2.0

### DNS-First Architecture

DNS is now **mandatory** during server setup, not optional:

```python
# ✅ v0.2.0 (CORRECT)
orch.setup_server_sync(
    "my-server",
    zone_name="example.com",     # REQUIRED!
    subdomain="lab"              # Optional
)

# ❌ OLD WAY (no longer works)
orch.setup_server("my-server")  # Missing DNS → ERROR!
```

### Infrastructure as Apps

Traefik and Portainer are now deployed **after** setup via `deploy-app`:

```bash
# v0.2.0 Workflow:
1. create-server      # Create VPS
2. setup-server       # Install Docker + Swarm + DNS config
3. deploy-app(infrastructure)  # Deploy Traefik + Portainer
4. deploy-app(n8n)    # Deploy applications
```

### Automatic Dependency Resolution

Like `npm install`, dependencies are automatically installed:

```python
# Deploy N8N
orch.deploy_app_sync("server", "n8n")

# System automatically installs:
# 1. postgres (dependency)
# 2. redis (dependency)
# 3. n8n (requested app)

# Result: All 3 apps running! 🎉
```

### Domain Auto-Building

Applications automatically get correct domains from DNS config:

```python
# Server setup with:
zone_name="livchat.ai"
subdomain="lab"

# Applications get domains automatically:
# - Portainer: ptn.lab.livchat.ai
# - N8N: edt.lab.livchat.ai
# - Postgres: pg.lab.livchat.ai
```

## 📚 Available Applications

- **Infrastructure**: Traefik, Portainer
- **Databases**: PostgreSQL, Redis
- **Automation**: N8N
- **Communication**: Chatwoot

Each app has automatic:
- ✅ Domain configuration
- ✅ SSL certificates (via Traefik)
- ✅ Dependency resolution
- ✅ Health checks

## 🔧 Configuration

### Storage Location

All configs stored in `~/.livchat/`:

```
~/.livchat/
├── state.json              # Server state + DNS configs
├── credentials.vault       # Encrypted secrets (Ansible Vault)
└── ssh_keys/              # SSH keys for server access
```

### Required Secrets

Configure via MCP `manage-secrets` tool or directly:

```bash
# Hetzner API token (required for server creation)
HETZNER_TOKEN="your-token-here"

# Cloudflare credentials (required for DNS)
CLOUDFLARE_API_KEY="your-api-key"
CLOUDFLARE_EMAIL="your-email"
```

## 🧪 Development

### Run Tests

```bash
# E2E tests (validates full workflow)
cd mcp-server
npm run test:e2e

# Unit tests (Python)
pytest tests/unit/

# Integration tests
pytest tests/integration/
```

### Project Structure

```
LivChatSetup/
├── src/                   # Python core
│   ├── orchestrator.py    # Main orchestration
│   ├── app_registry.py    # App dependency resolution
│   ├── app_deployer.py    # Deployment logic
│   └── providers/         # Cloud providers
├── mcp-server/            # MCP integration (TypeScript)
├── apps/                  # App definitions (YAML)
└── ansible/               # Automation playbooks
```

## 📖 Documentation

- [CLAUDE.md](CLAUDE.md) - Full architecture and design decisions
- [plans/](plans/) - Development plans and sprint docs
- API Docs - Run `livchat-setup docs` after install

## 🐛 Known Issues (v0.2.0)

- Unit tests need async/await refactoring (~43 tests disabled)
- E2E tests: ✅ 100% passing
- Manual testing: ✅ Fully validated

## 🗺️ Roadmap

### v0.3.0 (Planned)
- [ ] DigitalOcean provider support
- [ ] Web dashboard UI
- [ ] App marketplace expansion
- [ ] Backup automation
- [ ] Multi-region deployments

### v1.0.0 (Future)
- [ ] Kubernetes support
- [ ] Multi-tenancy/SaaS mode
- [ ] GitHub Actions integration
- [ ] Mobile app

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [SetupOrion](https://github.com/oriondesign2015/SetupOrion)
- Built with [Model Context Protocol](https://modelcontextprotocol.io)
- Powered by [Ansible](https://www.ansible.com/), [Docker Swarm](https://docs.docker.com/engine/swarm/), and [Traefik](https://traefik.io/)

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/pedrohnas/livchat-setup/issues)
- **Email**: team@livchat.ai
- **Docs**: [Full Documentation](https://github.com/pedrohnas/livchat-setup/blob/main/CLAUDE.md)

---

**Made with ❤️ by LivChat Team**

*v0.2.0 - DNS-First Architecture Release*
