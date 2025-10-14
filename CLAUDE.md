# LivChat Setup - Design Document

## 1. Executive Summary

**LivChat Setup** é um sistema de automação e orquestração para gerenciamento de múltiplos servidores VPS, instalação automatizada de aplicações e configuração de infraestrutura. Inspirado no SetupOrion, mas com arquitetura modular, extensível e controlável via AI através do Model Context Protocol (MCP).

### Objetivos Principais
- Automatizar o setup completo de servidores desde a criação até deploy de aplicações
- Gerenciar múltiplos servidores simultaneamente
- Integração nativa com Portainer, Cloudflare e provedores cloud
- Controle total via AI (Claude) através de MCP
- Sistema de dependências inteligente entre aplicações

### Não-Objetivos (Escopo Excluído)
- Interface gráfica web (fase inicial)
- Suporte a Kubernetes (foco em Docker Swarm)
- Marketplace público de aplicações
- Multi-tenancy/SaaS (fase inicial)

## 2. Context & Problem

### Problema Atual
Desenvolvedores e empresas precisam configurar múltiplos servidores com diversas aplicações open-source. O processo manual é:
- Repetitivo e propenso a erros
- Demorado (horas por servidor)
- Difícil de padronizar
- Complexo para gerenciar dependências

### Limitações do SetupOrion
- Script monolítico em Bash
- Difícil manutenção e extensão
- Sem gerenciamento de estado
- Limitado a um servidor por vez
- Sem integração com AI

### Oportunidades de Melhoria
- Arquitetura modular em Python
- Gerenciamento de estado persistente
- Operações paralelas em múltiplos servidores
- API REST para integrações
- Controle via AI com MCP

## 3. Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User/Developer                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼────────┐          ┌─────────▼────────┐
│   Claude AI    │          │  Python Direct   │
│  (via MCP)     │          │   Execution      │
└───────┬────────┘          └─────────┬────────┘
        │                             │
┌───────▼─────────────────────────────▼────────┐
│           MCP Gateway (TypeScript)           │
│         Published on NPM (@livchat/mcp)      │
└───────────────────┬──────────────────────────┘
                    │ HTTP/WebSocket
┌───────────────────▼──────────────────────────┐
│         LivChat Setup Core (Python)          │
│              FastAPI + Ansible               │
├───────────────────────────────────────────────┤
│  ┌─────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Core   │  │  State   │  │  Secrets   │  │
│  │ Module  │  │ Manager  │  │  Manager   │  │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘  │
│       │            │               │          │
│  ┌────▼────────────▼───────────────▼──────┐  │
│  │         Orchestration Layer             │  │
│  └──────────────┬──────────────────────────┘  │
│                 │                              │
│  ┌──────────────▼──────────────────────────┐  │
│  │  Providers │ Apps │ Integrations        │  │
│  └──────────────────────────────────────────┘  │
└────────────────┬─────────────────────────────┘
                 │
    ┌────────────┼───────────────┐
    │            │               │
┌───▼───┐  ┌────▼────┐  ┌───────▼──────┐
│Hetzner│  │Portainer│  │  Cloudflare  │
│  API  │  │   API   │  │     API      │
└───────┘  └─────────┘  └──────────────┘
```

### 3.2 Technology Stack

**[DECIDIDO]**
- **Core**: Python 3.11+
- **Orchestration**: Ansible 2.16+ (via Python API)
- **API Framework**: FastAPI
- **Validation**: Pydantic v2
- **Storage**: File-based (.livchat/)
- **Secrets**: Ansible Vault
- **MCP Server**: TypeScript/Node.js 18+
- **Container Platform**: Docker Swarm
- **Reverse Proxy**: Traefik
- **Initial Provider**: Hetzner Cloud

**[DECIDIDO v0.2.0]**
- **Storage Simplificado**: config.yaml EXTINTO - apenas state.json + credentials.vault
- **DNS Obrigatório**: Configurado no setup-server (zone_name required, subdomain optional)
- **Base Infrastructure**: Traefik+Portainer são apps, não parte do setup

**[EM DISCUSSÃO]**
- **Database Future**: SQLite como opção para estado complexo

## 4. Core Components

### 4.1 Modules Description

#### **Core Module** [DECIDIDO]
```python
class CoreOrchestrator:
    """Orquestração central e coordenação de módulos"""

    responsibilities = [
        "Coordenar fluxo de trabalho completo",
        "Gerenciar comunicação entre módulos",
        "Sistema de eventos/hooks",
        "Rollback em caso de falha",
        "Logging centralizado"
    ]
```

#### **Storage Manager** [DECIDIDO - v0.2.0 SIMPLIFICADO]
```python
class StorageManager:
    """Gerenciamento unificado de persistência"""

    def __init__(self):
        self.state = StateStore()        # Estado JSON (PRIMARY)
        self.secrets = SecretsStore()    # Vault criptografado
        # config.yaml REMOVIDO - complexidade desnecessária

    storage_path = "~/.livchat/"

    files = {
        "state.json": "Estado dos servidores, DNS configs e deployments (PRIMARY)",
        "credentials.vault": "Secrets criptografados com Ansible Vault"
        # config.yaml EXTINTO - tudo vai para state.json
    }

    features = [
        "Interface unificada para toda persistência",
        "Backup automático antes de mudanças",
        "Validação de integridade",
        "Gerenciamento centralizado do ~/.livchat/"
    ]

    # DECISÃO v0.2.0: config.yaml adiciona complexidade sem valor
    # Tudo que era config agora vai no state.json ou é passado como parâmetro
```

#### 🔐 **Storage Decision Matrix** [DECIDIDO]

**REGRA DE OURO**: Se é segredo/credencial, vai no VAULT. Se é preferência/configuração, vai no CONFIG.

| Tipo de Dado | Local | Motivo | Exemplo |
|--------------|-------|--------|---------|
| **API Tokens** | `credentials.vault` | 🔒 Sensível | `hetzner_token`, `cloudflare_api_key` |
| **Passwords** | `credentials.vault` | 🔒 Sensível | `db_password`, `admin_pass` |
| **SSH Private Keys** | `credentials.vault` | 🔒 Sensível | `server_ssh_key` |
| **Preferências** | `config.yaml` | 📝 Não-sensível | `default_region: nbg1` |
| **Defaults de Apps** | `config.yaml` | 📝 Não-sensível | `postgres_version: "14"` |
| **Estado de Servidores** | `state.json` | 🔄 Dinâmico | Server IPs, status, apps instaladas |

**Exemplos Práticos:**

```yaml
# ✅ config.yaml (não-sensível)
general:
  default_provider: hetzner
  default_region: ash          # ← Preferência, não secret
  admin_email: admin@example.com

apps:
  defaults:
    postgres_version: "14"
    redis_version: "latest"
```

```yaml
# ✅ credentials.vault (criptografado)
# Acessível apenas via orchestrator.storage.secrets.get_secret()
hetzner_token: "abc123xyz..."
cloudflare_api_key: "def456..."
cloudflare_email: "admin@livchat.ai"
ssh_private_key: "-----BEGIN..."
```

```json
// ✅ state.json (estado dinâmico)
{
  "servers": [
    {
      "name": "prod-server",
      "ip": "1.2.3.4",
      "provider": "hetzner",
      "provider_server_id": "12345678"  // ← Não é secret, é ID público
    }
  ]
}
```

**⚠️ Erros Comuns a Evitar:**

1. ❌ **NUNCA** colocar tokens no `config.yaml`
   ```yaml
   # ERRADO!
   providers:
     hetzner:
       token: "abc123"  # ← Arquivo não criptografado!
   ```

2. ❌ **NUNCA** colocar preferências no `vault`
   ```python
   # ERRADO!
   secrets.set_secret("default_region", "nbg1")  # ← Não é secret!
   ```

3. ✅ **SEMPRE** usar vault para credenciais
   ```python
   # CORRETO!
   api_token = orchestrator.storage.secrets.get_secret(f"{provider}_token")
   ```

**🔍 Como Decidir:**

Pergunte-se: **"Se eu commitasse isso no GitHub, teria problemas?"**
- **SIM**: Vai no `credentials.vault`
- **NÃO**: Vai no `config.yaml` ou `state.json`

#### **Provider Module** [PARCIALMENTE DECIDIDO]
```python
class ProviderInterface(ABC):
    """Interface base para todos os providers"""

    @abstractmethod
    def create_server(self, config: ServerConfig) -> Server
    @abstractmethod
    def delete_server(self, server_id: str) -> bool
    @abstractmethod
    def list_servers(self) -> List[Server]

class HetznerProvider(ProviderInterface):
    """Implementação inicial - Hetzner Cloud"""
    # [DECIDIDO] - Primeira implementação

class DigitalOceanProvider(ProviderInterface):
    """Futura implementação"""
    # [PLANEJADO] - Estrutura pronta para expansão
```

#### **SSH Manager** [DECIDIDO]
```python
class SSHManager:
    """Gerenciamento de chaves SSH e autenticação"""

    responsibilities = [
        "Gerar pares de chaves Ed25519/RSA",
        "Armazenar chaves seguramente no Vault",
        "Gerenciar chaves no provider (Hetzner/DO)",
        "Manter permissões corretas (600)",
        "Rotação automática de chaves"
    ]
```

#### **Ansible Runner** [DECIDIDO]
```python
class AnsibleRunner:
    """Execução de playbooks Ansible via Python API"""

    responsibilities = [
        "Executar playbooks via ansible-runner",
        "Gerar inventory dinâmico",
        "Executar comandos ad-hoc",
        "Coletar logs e resultados",
        "Gerenciar variáveis e secrets"
    ]
```

#### **Server Setup** [DECIDIDO - v0.2.0 DNS-FIRST]
```python
class ServerSetup:
    """Orquestração do setup completo de servidores"""

    responsibilities = [
        "Coordenar setup inicial (update, timezone, etc)",
        "Instalar Docker e iniciar Swarm",
        "Configurar DNS OBRIGATÓRIO (zone_name + subdomain opcional)",
        "Salvar DNS config no state.json",
        "Verificar health checks",
        "Rollback em caso de falha"
    ]

    # MUDANÇA v0.2.0: Traefik/Portainer NÃO são parte do setup!
    # São deployados via deploy-app como bundle "base-infrastructure"
```

#### **Dependency Resolver** [DECIDIDO - NOVO]
```python
class DependencyResolver:
    """Sistema inteligente de resolução de dependências"""

    def resolve_install_order(self, apps: List[str]) -> List[str]:
        """
        Exemplo: [n8n] -> [postgres, redis, n8n]
        """

    def validate_dependencies(self, app: AppDefinition) -> ValidationResult:
        """Verifica se todas as dependências podem ser satisfeitas"""

    def configure_dependency(self, parent_app: str, dependency: str):
        """
        Configura dependência para app pai
        Ex: Criar banco 'n8n_queue' no postgres
        """
```

#### **App Registry** [DECIDIDO]
```python
@dataclass
class AppDefinition:
    name: str
    version: str
    deploy_method: str  # "ansible" for infrastructure, "portainer" for apps
    dependencies: List[AppDependency]
    requirements: ResourceRequirements
    environment: Dict[str, str]
    health_check: HealthCheckConfig
    post_install_hooks: List[PostInstallHook]

    # Exemplo: N8N
    example = {
        "name": "n8n",
        "deploy_method": "portainer",  # Deployed via Portainer API
        "dependencies": [
            {"name": "postgres", "config": {"database": "n8n_queue"}},
            {"name": "redis", "config": {"db": 1}}
        ],
        "requirements": {"min_ram_mb": 1024, "min_cpu_cores": 1}
    }

    # Exemplo: Traefik
    infrastructure_example = {
        "name": "traefik",
        "deploy_method": "ansible",  # Deployed via Ansible playbook
        "compose": "...",  # Docker compose definition inline
    }
```

#### **Post-Deploy Configuration** [DECIDIDO - NOVO]
```python
class PostDeployConfiguration:
    """Configurações automáticas pós-deploy via APIs"""

    async def configure_grafana(self, url: str, admin_pass: str):
        """
        - Criar datasources via API
        - Importar dashboards JSON
        - Configurar alertas
        """

    async def configure_n8n(self, url: str):
        """
        - Configurar webhooks
        - Instalar community nodes
        """
```

### 4.2 Dependencies Map

```
Core Orchestrator
    ├── Storage Manager (persistência unificada)
    │   ├── ConfigStore (YAML)
    │   ├── StateStore (JSON)
    │   └── SecretsStore (Vault)
    ├── SSH Manager
    │   └── Storage Manager (para vault)
    ├── Dependency Resolver (parte do orchestrator.py)
    ├── Server Setup
    │   └── Ansible Runner
    ├── Ansible Runner
    │   └── SSH Manager (para conexão)
    ├── Provider Module
    │   ├── Cloud API Manager
    │   └── SSH Manager (para adicionar keys)
    ├── Integrations
    │   ├── Portainer API
    │   └── Cloudflare API
    └── API Server (FastAPI)
        └── Routes

MCP Gateway → API Server → Core Orchestrator
```

## 5. Key Features & Requirements

### 5.1 Dependency Resolution [DECIDIDO]
```python
# Sistema inspirado em package managers
dependencies = {
    "n8n": ["postgres", "redis"],
    "chatwoot": ["postgres", "redis", "sidekiq"],
    "wordpress": ["mysql"],
}

# Resolução automática de ordem
# Input: ["n8n", "wordpress"]
# Output: ["postgres", "redis", "mysql", "n8n", "wordpress"]
```

### 5.2 Multi-Server Management [DECIDIDO]
```python
# Operações paralelas
async def deploy_to_all_servers(app: str, servers: List[Server]):
    tasks = [deploy_app(server, app) for server in servers]
    results = await asyncio.gather(*tasks)
    return results
```

### 5.3 Application Lifecycle [DECIDIDO]
```
1. Pre-Install
   └── Verificar recursos
   └── Resolver dependências
   └── Preparar ambiente

2. Install
   └── Deploy via Portainer/Docker
   └── Configurar networks
   └── Setup volumes

3. Post-Install
   └── Health checks
   └── Configuração via API
   └── Registro no estado

4. Monitor
   └── Verificação contínua
   └── Alertas
   └── Métricas
```

### 5.4 Security [DECIDIDO]
- **Secrets**: Ansible Vault com senha mestra
- **SSH Keys**: Geração e rotação automática
- **API Auth**: Bearer tokens + rate limiting
- **Audit Log**: Todas as ações registradas

## 6. Data Models

### 6.1 Server Model [DECIDIDO]
```python
class Server:
    id: str
    name: str
    provider: str  # "hetzner"
    ip_address: str
    status: ServerStatus
    resources: ResourceInfo
    created_at: datetime
    ssh_key_id: str
    applications: List[str]
    metadata: Dict[str, Any]
```

### 6.2 Application Model [DECIDIDO]
```python
class Application:
    name: str
    version: str
    server_id: str
    status: AppStatus
    domain: Optional[str]
    ports: List[PortMapping]
    volumes: List[VolumeMount]
    environment: Dict[str, str]
    dependencies: List[str]
    installed_at: datetime
```

### 6.3 Storage Model [DECIDIDO - v0.2.0 SIMPLIFICADO]
```json
// state.json - ÚNICA fonte de configuração e estado
{
  "servers": [
    {
      "name": "manager-server",
      "ip": "1.2.3.4",
      "provider": "hetzner",
      "dns_config": {
        "zone_name": "livchat.ai",     // OBRIGATÓRIO no setup
        "subdomain": "lab"              // OPCIONAL
      },
      "applications": ["base-infrastructure", "n8n"]
    }
  ]
}

// config.yaml - EXTINTO
// Tudo agora é state.json (dinâmico) ou parâmetros explícitos nas tools
```

## 7. File Structure

### 7.1 Directory Organization [DECIDIDO]

```
LivChatSetup/
├── src/                      # All Python source code
│   ├── __init__.py          # Package exports only
│   ├── orchestrator.py      # Core orchestration + dependency resolution
│   ├── storage.py           # Unified config + state + secrets management
│   ├── ssh_manager.py      # SSH key management
│   ├── ansible_runner.py   # Ansible Python API wrapper
│   ├── server_setup.py     # Server setup orchestration
│   ├── cli.py              # CLI entry point
│   ├── providers/          # Cloud provider implementations
│   │   ├── __init__.py     # Base interface
│   │   ├── base.py         # Abstract provider class
│   │   └── hetzner.py      # Hetzner implementation
│   ├── integrations/       # External service integrations
│   │   ├── __init__.py
│   │   ├── portainer.py    # Portainer API client
│   │   └── cloudflare.py   # Cloudflare API client
│   └── api/                # REST API (FastAPI)
│       ├── __init__.py
│       ├── server.py       # FastAPI application
│       ├── routes/         # API endpoints
│       └── schemas/        # Pydantic models
│
├── apps/                    # Application definitions (YAML)
│   ├── catalog.yaml        # App registry
│   └── definitions/        # All stack definitions with deploy_method
│       ├── infrastructure/ # Infrastructure stacks (deploy_method: ansible)
│       │   ├── traefik.yaml
│       │   └── portainer.yaml
│       ├── databases/      # Database stacks (deploy_method: portainer)
│       │   ├── postgres.yaml
│       │   └── redis.yaml
│       └── applications/   # Application stacks (deploy_method: portainer)
│           ├── n8n.yaml
│           └── chatwoot.yaml
│
├── ansible/                # Ansible automation
│   ├── playbooks/
│   │   ├── base-setup.yml     # System preparation
│   │   ├── docker-install.yml # Docker installation
│   │   ├── swarm-init.yml     # Swarm initialization
│   │   └── app-deploy.yml     # Generic app deployment
│   ├── roles/
│   ├── inventory/
│   │   └── dynamic.py         # Dynamic inventory script
│   └── group_vars/
│
├── mcp-server/            # MCP Server (TypeScript)
│   ├── src/
│   │   ├── server.ts
│   │   └── tools/
│   ├── package.json
│   └── tsconfig.json
│
├── tests/                 # Test suite (TDD approach)
│   ├── unit/             # Unit tests for isolated components
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
│
├── plans/                 # Development planning documents
│   ├── plan-01.md        # Refactoring plan
│   └── ...               # Future sprint plans
│
├── docs/                  # Documentation
│   ├── guides/
│   └── api/
│
├── scripts/               # Utility scripts
│   ├── install.sh
│   └── dev-setup.sh
│
├── venv/                  # Python virtual environment (git-ignored)
│
├── .livchat/             # User config directory (in $HOME)
│   ├── state.json        # Estado completo (servidores, DNS, apps)
│   ├── credentials.vault # Encrypted secrets
│   └── ssh_keys/         # SSH keys directory
│   # config.yaml REMOVIDO em v0.2.0 - complexidade desnecessária
│
├── pyproject.toml        # Python project configuration
├── requirements.txt      # Python dependencies
├── Makefile             # Common tasks automation
├── CLAUDE.md            # This design document
└── README.md            # Project documentation
```

### 7.2 Rationale [DECIDIDO]

**Por que esta estrutura?**

1. **`src/` centralizado**: TODO código Python em um único diretório
   - Integrations DENTRO de src/ (não espalhado)
   - API DENTRO de src/ (não separado)
   - Imports claros e consistentes

2. **`storage.py` unificado**: Gerenciamento centralizado de persistência
   - Config, State e Secrets em um só lugar
   - ~400 linhas é tamanho ideal
   - Ainda modular internamente (classes separadas)
   - Ponto único para gerenciar ~/.livchat/

3. **`orchestrator.py` explícito**: Lógica principal fora de __init__.py
   - __init__.py apenas para exports públicos (padrão Python)
   - Inclui DependencyResolver (intimamente relacionado)
   - Fácil de encontrar o código principal

4. **Separação por tipo de conteúdo**:
   - `src/` → Todo código Python
   - `apps/` → Definições YAML (dados, não código)
   - `ansible/` → Playbooks (automação)
   - `mcp-server/` → TypeScript (projeto isolado)

5. **Estrutura escalável**: Pronta para crescer
   - `providers/` → Fácil adicionar novos
   - `integrations/` → Fácil adicionar serviços
   - `api/routes/` → Fácil adicionar endpoints

**Decisões importantes:**
- **NO** código Python fora de `src/` (exceto scripts auxiliares)
- **NO** lógica de negócio em `__init__.py` (anti-pattern)
- **YES** consolidação onde faz sentido (storage.py)
- **YES** subpastas quando há múltiplos arquivos relacionados
- Apps definidas em YAML, não em Python
- Testes seguem estrutura de src/

## 8. API Design

### 8.1 REST Endpoints [A DESENVOLVER]
```python
# FastAPI routes
POST   /servers                 # Criar servidor
GET    /servers                 # Listar servidores
GET    /servers/{id}           # Detalhes do servidor
DELETE /servers/{id}           # Destruir servidor

POST   /servers/{id}/apps      # Instalar app
GET    /servers/{id}/apps      # Listar apps
DELETE /servers/{id}/apps/{app} # Desinstalar app

GET    /apps                   # Catálogo de apps
GET    /apps/{name}           # Detalhes da app

POST   /deployments            # Novo deployment
GET    /deployments            # Histórico

# Webhooks
POST   /webhooks/portainer     # Eventos do Portainer
POST   /webhooks/health        # Health checks
```

### 8.2 MCP Tools [DECIDIDO - v0.2.0 ATUALIZADO]
```typescript
tools = [
    "manage-config",           // Configs não-sensíveis
    "manage-secrets",          // Credenciais criptografadas
    "get-provider-info",       // Info de regions/server-types
    "create-server",           // Criar VPS
    "list-servers",            // Listar servidores
    "setup-server",            // Setup + DNS (zone_name OBRIGATÓRIO)
    "delete-server",           // Destruir servidor
    "update-server-dns",       // Ajustar DNS pós-setup (v0.2.0 NEW)
    "list-apps",               // Catálogo de apps
    "deploy-app",              // Instalar app (valida base-infrastructure + DNS)
    "undeploy-app",            // Desinstalar app
    "list-deployed-apps",      // Apps instaladas no servidor
    "get-job-status",          // Status do job assíncrono
    "list-jobs"                // Histórico de jobs
]

// REMOVIDO em v0.2.0: "configure-server-dns" (agora parte de setup-server)
```

### 8.3 Error Handling [A DESENVOLVER]
```python
class APIError:
    code: str  # "SERVER_CREATION_FAILED"
    message: str
    details: Dict[str, Any]
    retry_after: Optional[int]
```

## 9. Deployment Scenarios

### 9.1 Local Development [DECIDIDO]
```bash
# Python local
pip install livchat-setup
livchat-setup start --dev

# MCP apontando para local
LIVCHAT_API_URL=http://localhost:8000
```

### 9.2 Cloud Deployment [PLANEJADO]
```bash
# Docker
docker run -d \
  -p 8000:8000 \
  -v ~/.livchat:/app/.livchat \
  livchat/setup-server

# Com docker-compose
docker-compose up -d
```

### 9.3 Hybrid Setup [DECIDIDO]
```python
# Desenvolvimento local, servidores na cloud
config = {
    "api": "local",
    "servers": "production",
    "storage": "local"
}
```

## 10. Implementation Phases

### Phase 1: Core & Base [✅ COMPLETED]
- [x] Design document
- [x] Project structure
- [x] Core orchestrator
- [x] State manager
- [x] Basic API
📄 **Plan-01:** Initial refactoring and base structure

### Phase 2: Provider & Apps [✅ COMPLETED]
- [x] Hetzner provider
- [x] Ansible runner
- [x] Dependency resolver (Básico implementado)
- [x] Basic apps (Traefik deployado com sucesso)
📄 **Plan-02:** Ansible Runner + SSH Keys + Base Infrastructure

### Phase 3: Integrations [✅ COMPLETED]
- [ ] Portainer API (cliente próprio)
- [ ] Cloudflare API (SDK oficial)
- [ ] App Registry com YAML
- [ ] Post-deploy configs
📄 **Plan-03:** Integration Layer - Portainer, Cloudflare & App Registry

### Phase 4: MCP Gateway [⚪ PLANNED]
- [ ] TypeScript server
- [ ] Tool implementations
- [ ] NPM package

### Phase 5: Testing & Polish [⚪ PLANNED]
- [ ] Unit tests completos
- [ ] Integration tests
- [ ] Documentation
- [ ] Docker image

## 11. Development Practices

### Development Environment
- **Virtual Environment**: Sempre usar `venv/` para desenvolvimento
  ```bash
  source venv/bin/activate  # Ativar antes de qualquer execução
  pip install -r requirements.txt
  ```

### Test-Driven Development (TDD)
- **Escrever testes ANTES da implementação** quando possível
- **Mínimo 80% de cobertura** para código crítico (storage, orchestrator)
- **Executar testes frequentemente** durante desenvolvimento
  ```bash
  pytest tests/unit/  # Durante desenvolvimento
  pytest --cov=src    # Verificar cobertura
  ```

### 🚨 Padrões de Mock para Testes Rápidos
```python
# PADRÃO CORRETO - Mock no nível do método
class TestMyComponent:
    @pytest.fixture
    def app_deployer(self):
        deployer = AppDeployer(...)
        # Mock métodos que fariam I/O
        deployer.verify_health = AsyncMock(return_value={"healthy": True})
        deployer.check_health = AsyncMock(return_value={"status": "ok"})
        return deployer

# PADRÃO ERRADO - Mock de bibliotecas HTTP
@patch('httpx.AsyncClient')  # ❌ NÃO FAZER
@patch('requests.get')       # ❌ NÃO FAZER

# REGRA DE OURO: Se o teste demora > 3 segundos, está fazendo I/O real!
```

### Planning Process
- **Documentar planos em `plans/`** antes de implementações grandes
- **Revisar e atualizar** planos conforme desenvolvimento evolui
- **Usar Etapas e Tasks** ao invés de prazos temporais (dias/semanas)
- **TDD approach** com testes escritos antes da implementação

### Plan Structure Standard
Todos os planos de desenvolvimento devem seguir esta estrutura:

1. **📋 Contexto**: Referência ao CLAUDE.md e status atual
2. **🎯 Objetivo**: Meta clara e mensurável
3. **📊 Escopo Definitivo**: Componentes detalhados com código exemplo
4. **🧪 Estratégia de Testes TDD**: Test-first approach
5. **📁 Estrutura de Arquivos**: Coerente com CLAUDE.md
6. **✅ Checklist de Implementação**:
   - Organizado por **Etapas** (não dias/semanas)
   - Cada etapa com **Tasks** numeradas
   - Formato: `Etapa 1: Component Name`
     - `Task 1: Specific action`
     - `Task 2: Another action`
7. **📦 Dependências Novas**: Packages necessários
8. **🎮 CLI Commands**: Novos comandos a implementar
9. **🎯 Critérios de Sucesso**: Verificações objetivas
10. **📊 Métricas**: KPIs mensuráveis (sem prazos temporais)
11. **⚠️ Considerações Importantes**: Decisões técnicas
12. **🚀 Próximos Passos**: Visão do próximo plan
13. **📊 Status**: Tracking do progresso

**Status Legend para Plans:**
- 🔵 **READY TO START**: Planejado e pronto
- 🟡 **IN PROGRESS**: Em desenvolvimento
- ✅ **COMPLETED**: Fase concluída
- 🔴 **BLOCKED**: Aguardando dependências

## 12. Testing Strategy

### 🚨 PADRÕES OBRIGATÓRIOS DE TESTES

#### **Unit Tests** [IMPLEMENTADO]
```python
# pytest + pytest-asyncio
tests/unit/

# REGRAS FUNDAMENTAIS:
# 1. SEMPRE usar mocks - NUNCA fazer chamadas reais (HTTP, filesystem, etc)
# 2. Mock direto nos métodos do cliente, não no httpx/requests
# 3. Usar AsyncMock para métodos async
# 4. Testes devem rodar em < 3 segundos TOTAL
# 5. Usar fixtures para criar mocks reutilizáveis

# EXEMPLO CORRETO:
@pytest.fixture
def mock_client():
    client = PortainerClient()
    client._request = AsyncMock(return_value={"jwt": "token"})
    client.verify_health = AsyncMock(return_value={"healthy": True})
    return client

# EXEMPLO ERRADO:
@patch('httpx.AsyncClient')  # NÃO fazer isso em unit tests!
async def test_something(mock_httpx):
    pass  # Isso causa timeouts e testes lentos
```

### Integration Tests [IMPLEMENTADO]
```python
# tests/integration/

# REGRAS:
# 1. Podem usar recursos LOCAIS (filesystem temporário, SQLite em memória)
# 2. NÃO devem fazer chamadas para APIs externas
# 3. Podem testar interação entre múltiplos componentes
# 4. Usar temp directories para isolamento
# 5. PODEM usar mocks para serviços externos

# Scenarios:
- Deploy N8N com dependências (mocked)
- Multi-server deployment (local state)
- Rollback após falha
- Configuração via API (local)
- Workflow completo com mocks
```

### E2E Tests [IMPLEMENTADO]
```python
# tests/e2e/

# REGRAS:
# 1. SEMPRE fazem chamadas REAIS (sem mocks!)
# 2. Controlado por variável de ambiente: LIVCHAT_E2E_REAL=true
# 3. NÃO devem ter fallback para mocks (isso seria integration test)
# 4. Cleanup obrigatório após testes
# 5. Testam o sistema COMPLETO end-to-end

# EXEMPLO:
@pytest.fixture
def use_real_infrastructure():
    return os.environ.get("LIVCHAT_E2E_REAL", "false") == "true"

def test_real_server_creation(use_real_infrastructure):
    if use_real_infrastructure:
        # Chamadas reais para Hetzner, Cloudflare, etc
        server = create_real_server()
    else:
        # Use mocks
        server = mock_server()
```

### 📊 Métricas de Performance dos Testes
- **Unit tests**: < 3 segundos total
- **Integration tests**: < 10 segundos total
- **E2E tests**: < 5 minutos (quando reais)
- **Cobertura mínima**: 80% para componentes críticos

## 12. Security Considerations

### Authentication [A DESENVOLVER]
```python
# API Keys para MCP
headers = {
    "Authorization": "Bearer livchat_key_xxx",
    "X-Request-ID": "uuid"
}
```

### Rate Limiting [A DESENVOLVER]
```python
limits = {
    "create_server": "5/hour",
    "api_calls": "1000/hour"
}
```

### Secrets Management [DECIDIDO]
- Ansible Vault para credenciais
- Rotação automática de SSH keys
- Sem hardcode de secrets

## 13. Future Enhancements

### Confirmed Roadmap [PLANEJADO]
1. **Q1 2025**: DigitalOcean provider
2. **Q2 2025**: Web dashboard básico
3. **Q3 2025**: Marketplace de apps
4. **Q4 2025**: Backup automatizado

### Under Consideration [IDEIAS]
- Kubernetes support
- Terraform integration
- GitHub Actions integration
- Multi-tenancy/SaaS mode
- Mobile app

## 14. Open Questions

### Technical Decisions Pending
1. **Config Format**: YAML vs JSON vs TOML?
2. **SQLite Integration**: Quando migrar de JSON?
3. **Plugin System**: Como permitir apps customizadas?
4. **Monitoring**: Prometheus/Grafana built-in?

### Business Decisions
1. **Licensing**: MIT, Apache 2.0, ou proprietário?
2. **Cloud Service**: Oferecer SaaS?
3. **Support Model**: Community vs Enterprise?

## 15. Success Metrics

### Technical KPIs
- Setup time: < 5 minutos por servidor
- Deployment success rate: > 95%
- API response time: < 200ms p95
- Zero-downtime updates

### User KPIs
- Servers managed: 100+ simultâneo
- Apps catalog: 50+ aplicações
- Community contributors: 10+

## 16. Appendix

### A. Glossary
- **MCP**: Model Context Protocol
- **Provider**: Cloud service (Hetzner, DO, etc)
- **Stack**: Conjunto de apps relacionadas
- **Deployment**: Instância de uma app

### B. References
- [SetupOrion](https://github.com/oriondesign2015/SetupOrion)
- [MCP Specification](https://modelcontextprotocol.io)
- [Ansible Python API](https://docs.ansible.com/ansible/latest/dev_guide/developing_api.html)

### C. Status Legend
- **[DECIDIDO]**: Decisão final tomada
- **[EM DISCUSSÃO]**: Aberto para refinamento
- **[A DESENVOLVER]**: Ainda não detalhado
- **[PLANEJADO]**: Roadmap futuro
- **[IDEIAS]**: Possibilidades sendo exploradas

---

*Document Version: 1.0.0*
*Last Updated: 2024-12-16*
*Status: Draft for Approval*