# 🚀 LivChat Setup

**Automated server setup and deployment with AI control**

Deploy complete stacks (N8N, Chatwoot, Portainer) on VPS with one command - via Python or Claude AI.

> 🧪 **Beta aberto** - Sistema funcional, em desenvolvimento ativo

---

## ⚡ Instalação

```bash
# Python package
pip install livchat-setup

# MCP server (para usar com Claude)
npm install -g @pedrohnas/livchat-setup-mcp
```

## 🚀 Quick Start

### 1. Configure credenciais

```bash
# Start API server
livchat-setup serve

# Em outro terminal, configure via Claude ou Python:
# - Hetzner API token
# - Cloudflare API key + email
```

### 2. Deploy via Claude AI

```json
// Configure Claude Desktop (claude_desktop_config.json)
{
  "mcpServers": {
    "livchat-setup": {
      "command": "npx",
      "args": ["@pedrohnas/livchat-setup-mcp"]
    }
  }
}
```

**Comandos naturais:**
```
"Create server prod-01 type cx21 in region nbg1"
"Setup with DNS zone example.com subdomain prod"
"Deploy N8N"  → Auto-instala postgres + redis!
```

### 3. Deploy via Python

```python
from orchestrator import Orchestrator

orch = Orchestrator()
orch.init()

# Create + setup server (~3 min)
orch.create_server_sync("prod-01", "cx21", "nbg1")
orch.setup_server_sync("prod-01", zone_name="example.com", subdomain="prod")

# Deploy infrastructure + app
orch.deploy_app_sync("prod-01", "infrastructure")  # Traefik + Portainer
orch.deploy_app_sync("prod-01", "n8n")             # Auto-resolves dependencies!
```

## ✨ Principais Features

- **🤖 AI Control**: Gerencie servidores conversando com Claude
- **📦 Auto Dependencies**: Deploy N8N instala postgres + redis automaticamente
- **🌐 DNS Automático**: Apps recebem domínios prontos (n8n.lab.example.com)
- **⚡ Async Jobs**: Operações longas rodam em background com tracking
- **🔐 Secrets Management**: Credenciais criptografadas com Ansible Vault
- **🐳 Docker Swarm**: Orquestração completa com Traefik SSL automático

## 📦 Apps Disponíveis

| Categoria | Apps |
|-----------|------|
| **Infrastructure** | Traefik, Portainer |
| **Databases** | PostgreSQL, Redis |
| **Automation** | N8N (auto-instala postgres + redis) |
| **Communication** | Chatwoot |

**Cada app inclui:**
- Domain + SSL automático via Traefik
- Resolução de dependências
- Health checks

## 🔧 Configuração

### Secrets necessários

```bash
# Via MCP tool "manage-secrets" ou Python
hetzner_token          # API token Hetzner
cloudflare_api_key     # Cloudflare API key
cloudflare_email       # Email do Cloudflare
```

### Storage local

```
~/.livchat/
├── state.json              # Estado dos servidores + apps
├── credentials.vault       # Secrets criptografados
└── ssh_keys/              # Chaves SSH
```

## 🧪 Development

```bash
# Run tests
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
cd mcp-server && npm test    # MCP E2E tests

# Dev setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Structure:**
```
src/          → Core Python (orchestrator, providers, deployer)
apps/         → App definitions (YAML)
ansible/      → Playbooks (setup, deploy)
mcp-server/   → TypeScript MCP integration
```

## 📖 Docs

- **Architecture**: [CLAUDE.md](CLAUDE.md)
- **Plans**: [plans/](plans/)
- **API**: Run `livchat-setup docs`

## 🗺️ Roadmap

**v0.3.0** (próximo)
- DigitalOcean provider
- Web dashboard
- Backup automation

**v1.0.0** (futuro)
- Kubernetes support
- Multi-tenancy
- GitHub Actions integration

## 📄 Licença

Licença Provisória - ver [LICENSE](LICENSE) para detalhes

**Resumo:** Código aberto para aprendizado, uso comercial requer autorização

---

## 💝 Inspiração & Agradecimentos

**Willian - [Orion Design](https://oriondesign.art.br/)**
Projeto inspirado no [SetupOrion](https://github.com/oriondesign2015/SetupOrion)

**Tecnologias:**
- [Model Context Protocol](https://modelcontextprotocol.io) (Anthropic)
- [Ansible](https://www.ansible.com/) + [Docker Swarm](https://docs.docker.com/engine/swarm/) + [Traefik](https://traefik.io/)

---

**Made with ❤️ by LivChat Team**
