# LivChat Setup - AI Context Document

> **Meta**: Este é o contexto da AI. Mantenha < 800 linhas, alta densidade de informação, refletindo estado REAL do código.

## 📝 How to Update This Document

### When to Update
- ✅ After implementing new core feature
- ✅ After architectural decision
- ✅ After changing file structure
- ❌ NOT for minor bug fixes

### Guidelines
- Verify information against actual code
- Keep concise (bullet points > paragraphs)
- Move details to `docs/`
- Update version + date at bottom

---

## 1. Executive Summary

**LivChat Setup** = Automated VPS infrastructure orchestration via AI (MCP)

**Core Value:**
- Deploy complete stacks (N8N, Chatwoot, etc) on VPS with one command
- AI-controlled via Claude (MCP protocol)
- Auto-dependency resolution (deploy N8N → auto-installs postgres + redis)

**Current State:** v0.2.5
- ✅ Hetzner provider
- ✅ Docker Swarm + Traefik
- ✅ 7 apps (Traefik, Portainer, Postgres, Redis, N8N, Chatwoot)
- ✅ MCP server (13 tools - manage-config REMOVED)
- ✅ Async job system
- ✅ Modular orchestrator (ProviderManager, ServerManager) - PLAN-08
- ✅ Settings in state.json (config.yaml EXTINTO)
- ✅ Critical bug fix: StateStore lazy loading (_loaded flag)

---

## 2. Architecture

```
User (Claude AI or Python)
        ↓
MCP Server (TypeScript) → FastAPI → Orchestrator
                                         ↓
                    ┌────────────────────┼────────────────────┐
                    ↓                    ↓                    ↓
              Storage Manager      App Registry        Job Executor
              (state + vault)      (YAML deps)         (background)
                    ↓                    ↓                    ↓
            Hetzner API          Portainer API        Cloudflare API
```

### Tech Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2
- **Orchestration**: Ansible 2.16+ (via Python API)
- **Storage**: File-based (state.json + credentials.vault)
- **Secrets**: Ansible Vault
- **MCP**: TypeScript/Node.js 18+
- **Container**: Docker Swarm + Traefik
- **Provider**: Hetzner Cloud

### v0.2.0+ Decisions
- ✅ **DNS mandatory** during setup-server (zone_name required)
- ✅ **Infrastructure bundle** - Traefik+Portainer deployed as app
- ✅ **ConfigStore REMOVED (v0.2.5)** - Only state.json + vault (2-file system)
- ✅ **Settings in state.json** - email, name, surname, company_name as defaults
- ✅ **Modular orchestrator** - ProviderManager, ServerManager (PLAN-08)

---

## 3. Core Components (IMPLEMENTED)

### Orchestrator (Modular - PLAN-08)
**New Structure** (`src/orchestrator/`):
- `provider_manager.py` - Provider configuration (46 linhas, 6 testes)
- `server_manager.py` - Server CRUD (155 linhas, 14 testes)
- `orchestrator_old.py` - Legacy (será migrado gradualmente)

**ProviderManager**:
- Configure cloud providers (Hetzner)
- Auto-initialize from vault tokens
- Thread-safe provider caching

**ServerManager**:
- `create()` - Create VPS with SSH key
- `list()` - List all servers
- `get()` - Get specific server
- `delete()` - Delete server

### Storage Manager (`storage.py`)
```python
~/.livchat/
├── state.json           # PRIMARY: servers, DNS, apps, settings
├── credentials.vault    # Encrypted secrets
└── ssh_keys/           # Auto-generated keys
```

**Rule v0.2.5**:
- Secrets → vault
- Settings (email, name, etc) → state.json (section "settings")
- Dynamic state → state.json

### App Registry (`app_registry.py`)
- **Single source of truth**: reads `apps/definitions/*.yaml`
- Resolves dependencies recursively
- Example: `n8n` → `[postgres, redis, n8n]`

### App Deployer (`app_deployer.py`)
- Deploy via Portainer API (apps) or Ansible (infrastructure)
- Auto-installs dependencies
- DNS + SSL automatic via Traefik

### Server Setup (`server_setup.py`)
- Base system preparation
- Docker + Swarm init
- **DNS configuration (required)**
- Does NOT install Traefik/Portainer (those are apps)

### Job System (`job_manager.py` + `job_executor.py`)
- Async operations (create-server, deploy-app)
- Background execution with progress tracking
- Log management with auto-cleanup

### SSH Manager (`ssh_manager.py`)
- Auto-generate Ed25519 keys
- Store in vault
- Add to Hetzner on server creation

---

## 4. Dependencies Map

### Visual Architecture (REAL - Validated from Code)
```
User (Claude AI / Python Direct)
        │
┌───────┴────────┐
│  MCP / FastAPI │  ← Entry points
└───────┬────────┘
        │
    ┌───▼───────────────────────────────────────┐
    │    Orchestrator (core.py) - FACADE        │
    └───┬───┬───┬───┬───┬───┬───┬───┬──────────┘
        │   │   │   │   │   │   │   │
  ┌─────┤   │   │   │   │   │   │   └────────────┐
  │     │   │   │   │   │   │   │                │
┌─▼─┐ ┌─▼┐ ┌▼┐ ┌▼┐ ┌▼──┐ ┌▼─┐ ┌▼───┐  ┌────────▼─┐
│Prv│ │Srv│ │D│ │D│ │SSH│ │App│ │Srv │  │ Storage  │
│Mgr│ │Mgr│ │M│ │N│ │Mgr│ │Reg│ │Set │  │ Manager  │
└─┬─┘ └─┬─┘ │g│ │S│ └───┘ └─┬─┘ └─┬──┘  ├──────────┤
  │     │   │r│ │ │         │     │     │State.json│
  │     │   └┬┘ └┬┘         │     │     │Vault     │
  │     │    │   │          │     │     └──────────┘
  │     │    │   │          │     │
┌─▼──┐  │  ┌─▼───▼──────────▼─────▼──┐
│Hetz│  │  │   App Deployer           │
│ner │  │  ├──────────────────────────┤
└────┘  │  │• Portainer API           │
        │  │• Cloudflare API          │
        │  └──────────────────────────┘
        │
   ┌────▼──────────┐
   │  Job System   │
   ├───────────────┤
   │• JobManager   │
   │• JobExecutor  │
   │• JobLogMgr    │
   └───────────────┘
```

### Component Dependencies (Bottom-Up)
**External Services** (Tier 6 - Leaves):
- `HetznerProvider` ← hcloud SDK
- `PortainerClient` ← httpx (HTTP)
- `CloudflareClient` ← cloudflare SDK
- `AnsibleRunner` ← ansible-runner + SSHKeyManager

**Storage Layer** (Tier 5):
- `StorageManager` ← StateStore + SecretsStore (AnsibleVault)
- `AppRegistry` ← YAML files + PasswordGenerator

**Service Layer** (Tier 4):
- `ServerSetup` ← AnsibleRunner + AppRegistry
- `AppDeployer` ← PortainerClient + CloudflareClient + AppRegistry
- `SSHKeyManager` ← StorageManager (vault)

**Managers** (Tier 3 - PLAN-08 Modular):
- `ProviderManager` ← StorageManager + HetznerProvider
- `ServerManager` ← StorageManager + ProviderManager + SSHKeyManager
- `DeploymentManager` ← StorageManager + AppRegistry + AppDeployer
- `DNSManager` ← StorageManager + CloudflareClient

**Job System** (Tier 3.5):
- `JobManager` ← StorageManager + JobLogManager
- `JobExecutor` ← JobManager + Orchestrator

**Facade** (Tier 2):
- `Orchestrator (core.py)` ← ALL managers + storage + integrations

**Entry Points** (Tier 1):
- `FastAPI` ← Orchestrator + JobManager
- `MCP Server` ← FastAPI (HTTP)

### Key Insights
1. **Facade Pattern**: Orchestrator delegates to specialized managers
2. **Dependency Inversion**: Managers depend on abstractions (ProviderInterface)
3. **Single Source of Truth**: AppRegistry reads YAML, not hardcoded
4. **Storage Isolation**: Only StorageManager touches disk directly
5. **Job Decoupling**: JobExecutor calls Orchestrator (not direct managers)

---

## 5. File Structure

```
LivChatSetup/
├── src/
│   ├── orchestrator.py      # Core
│   ├── storage.py           # State + Secrets
│   ├── app_registry.py      # Dependency resolver
│   ├── app_deployer.py      # Deploy logic
│   ├── server_setup.py      # Server setup
│   ├── job_manager.py       # Job tracking
│   ├── job_executor.py      # Background execution
│   ├── ssh_manager.py       # SSH keys
│   ├── providers/hetzner.py # Cloud provider
│   ├── integrations/        # Portainer, Cloudflare
│   └── api/                 # FastAPI
├── apps/definitions/        # YAML app definitions
├── ansible/playbooks/       # Ansible automation
├── mcp-server/             # TypeScript MCP
├── tests/                  # Unit, integration, e2e
├── plans/                  # Development plans
├── CLAUDE.md              # This file
├── TECH-DEBT.md           # Known issues
└── CHANGELOG.md           # Release notes
```

**Where to add:**
- New cloud provider: `src/providers/`
- New app: `apps/definitions/{category}/`
- New API endpoint: `src/api/routes/`

---

## 6. Development Practices

### Test-Driven Development
```bash
pytest tests/unit/        # < 3s total, use mocks
pytest tests/integration/ # < 10s, local resources only
pytest tests/e2e/        # < 5min, REAL APIs (LIVCHAT_E2E_REAL=true)
```

**Mock Pattern (CORRECT):**
```python
@pytest.fixture
def mock_deployer():
    deployer = AppDeployer(...)
    deployer.verify_health = AsyncMock(return_value={"healthy": True})
    return deployer
```

**DON'T mock httpx/requests** - mock at component level

### 🚨 Test-Before-Commit (MANDATORY)
**NEVER commit without running tests!**

```bash
# Pre-commit checklist:
pytest tests/unit/ -v                          # 1. Unit tests (REQUIRED)
cd mcp-server && npm run build                 # 2. TypeScript compile
cd mcp-server && export LIVCHAT_E2E_REAL=true && timeout 30m npm run test:e2e  # 3. E2E (for critical changes)
```

**E2E Required for:**
- ✅ storage.py changes
- ✅ orchestrator/job system changes
- ✅ deploy/setup logic changes
- ✅ Critical MCP tools (servers, apps, setup)

**E2E Duration:** 8-12 min | **Timeout:** 30min

### Planning Process
- Create plan in `plans/plan-XX.md` BEFORE major features
- Use Etapas + Tasks (not time estimates)
- Update CLAUDE.md after implementation

### Code Quality
- DRY principle
- Single responsibility
- See TECH-DEBT.md for known violations

### 🚫 NO Version Numbers in Code (CRITICAL RULE)
**NEVER add version numbers (v0.X.X) to code comments or MCP strings!**

**Why:** Instantly outdated, creates maintenance debt.

**❌ BAD:**
```python
# v0.2.0: DNS now required
```

**✅ GOOD:**
```python
# DNS now required
```

**Exception:** Only `__version__` in `__init__.py`

---

## 7. API & MCP Tools

### FastAPI Endpoints
```
GET  /health              # Health check
POST /servers             # Create server (async)
GET  /servers             # List servers
POST /apps/deploy         # Deploy app (async)
GET  /jobs/{id}           # Job status
```

### MCP Tools (13 total - manage-config REMOVED v0.2.5)
```typescript
manage-secrets          // Encrypted credentials (config.yaml EXTINTO)
get-provider-info       // Hetzner regions/types
create-server           // VPS creation (async)
list-servers            // Server list
setup-server            // Setup + DNS (async)
delete-server           // Destroy (async)
update-server-dns       // DNS adjustment
list-apps               // App catalog
deploy-app              // Deploy with deps (async)
undeploy-app            // Remove app (async)
list-deployed-apps      // Installed apps
get-job-status          // Async job status
list-jobs               // Job history
```

---

## 8. Deployment Workflow

### Standard Flow
```bash
# 1. Create server
create-server(name="prod", type="cx21", region="nbg1")
# → Job ID returned, server created in ~30s

# 2. Setup (DNS mandatory)
setup-server(name="prod", zone_name="example.com", subdomain="prod")
# → Installs Docker, Swarm, configures DNS

# 3. Deploy infrastructure
deploy-app(server="prod", app="infrastructure")
# → Traefik + Portainer (~2min)

# 4. Deploy app (auto-resolves deps)
deploy-app(server="prod", app="n8n")
# → Auto-installs postgres, redis, then n8n
# → DNS: n8n.prod.example.com
# → SSL: automatic via Traefik
```

### DNS-First Approach
- DNS configured during `setup-server` (not optional)
- Apps receive: `{app}.{subdomain}.{zone}` or `{app}.{zone}`
- Stored in `state.json` → `servers[].dns_config`

---

## 9. Key Decisions & Rationale

### Why DNS Mandatory?
- Apps need domains for Traefik routing
- SSL requires proper domain
- Simplifies user experience (no manual DNS)

### Why Infrastructure as App?
- v0.2.0 change: cleaner separation
- Traefik/Portainer can be redeployed independently
- setup-server focuses on base system only

### Why YAML for Apps?
- Single source of truth for dependencies
- Easy to add new apps (no code changes)
- Human-readable and versionable

### Why File-Based Storage?
- Simple, no database needed
- Easy backup/restore
- Sufficient for current scale (< 100 servers)

---

## 10. Known Limitations

See `TECH-DEBT.md` for complete list:
- Test coverage < 80% in some modules
- Some DRY violations in deployer logic
- Missing integration tests for full workflow
- No rollback mechanism for failed deploys

---

## 11. Quick Reference

### Common Tasks
```bash
# Start API server
livchat-setup serve --reload

# Run tests
pytest tests/unit/ -v

# Check job status
curl localhost:8000/jobs/{job_id}
```

### Debug
- Logs: Check job logs via `get-job-status`
- State: `~/.livchat/state.json`
- API: `http://localhost:8000/docs`

---

**Version:** 0.2.5 (PLAN-08 refactoring - modular orchestrator)
**Last Updated:** 2025-10-19
**Lines:** ~450 (target: < 800)
**Status:** Production-ready beta

---

## Links
- Details: `docs/ARCHITECTURE.md`
- Technical Debt: `TECH-DEBT.md`
- Release Notes: `CHANGELOG.md`
- Plans: `plans/`
