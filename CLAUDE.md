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

**[EM DISCUSSÃO]**
- **Config Format**: YAML vs JSON (tendência: YAML para configs, JSON para estado)
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

#### **State Manager** [DECIDIDO]
```python
class StateManager:
    """Persistência e gestão de estado local"""

    storage_path = "~/.livchat/"

    files = {
        "servers.json": "Estado dos servidores",
        "deployments.json": "Histórico de deployments",
        "config.yaml": "Configurações globais",
        "credentials.vault": "Secrets criptografados"
    }

    features = [
        "CRUD operations",
        "Versionamento de estado",
        "Backup automático antes de mudanças",
        "Validação de integridade"
    ]
```

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
    dependencies: List[AppDependency]
    requirements: ResourceRequirements
    environment: Dict[str, str]
    health_check: HealthCheckConfig
    post_install_hooks: List[PostInstallHook]

    # Exemplo: N8N
    example = {
        "name": "n8n",
        "dependencies": [
            {"name": "postgres", "config": {"database": "n8n_queue"}},
            {"name": "redis", "config": {"db": 1}}
        ],
        "requirements": {"min_ram_mb": 1024, "min_cpu_cores": 1}
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
    ├── State Manager (estado persistente)
    ├── Secrets Manager (credenciais)
    ├── Provider Module
    │   └── Connection Manager (SSH/API)
    ├── Dependency Resolver
    │   └── App Registry (catálogo)
    ├── Ansible Runner
    │   └── Connection Manager
    ├── Integration Module
    │   ├── Portainer API
    │   └── Cloudflare API
    └── Monitoring Module

MCP Gateway → Core Orchestrator (via API)
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

### 6.3 Configuration Model [EM DISCUSSÃO]
```yaml
# .livchat/config.yaml
general:
  default_provider: hetzner
  default_region: nbg1

providers:
  hetzner:
    regions: [nbg1, fsn1, hel1]

apps:
  defaults:
    postgres_version: "14"
    redis_version: "latest"
```

## 7. File Structure

### 7.1 Directory Organization [DECIDIDO]

```
livchat-setup/
├── src/                      # Core source code
│   ├── __init__.py
│   ├── core/                 # Core orchestration
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   └── dependencies.py
│   ├── config/               # Configuration management
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── state/                # State management
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── secrets/              # Secrets management
│   │   ├── __init__.py
│   │   └── vault.py
│   ├── providers/            # Provider implementations
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── hetzner.py
│   └── cli.py               # CLI entry point
│
├── apps/                     # Application definitions
│   ├── catalog.yaml          # App registry
│   └── definitions/
│       ├── databases/
│       │   ├── postgres.yaml
│       │   └── redis.yaml
│       └── applications/
│           ├── n8n.yaml
│           └── chatwoot.yaml
│
├── ansible/                  # Ansible playbooks
│   ├── playbooks/
│   │   ├── base-setup.yml
│   │   └── app-deploy.yml
│   ├── roles/
│   ├── inventory/
│   └── group_vars/
│
├── integrations/             # External integrations
│   ├── __init__.py
│   ├── portainer.py
│   └── cloudflare.py
│
├── api/                      # FastAPI REST API [FUTURO]
│   ├── __init__.py
│   ├── main.py
│   ├── routes/
│   └── schemas/
│
├── mcp-server/              # MCP Server (TypeScript)
│   ├── src/
│   │   ├── server.ts
│   │   └── tools/
│   ├── package.json
│   └── tsconfig.json
│
├── tests/                   # Tests
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                    # Documentation
│   ├── guides/
│   └── api/
│
├── scripts/                 # Utility scripts
│   ├── install.sh
│   └── dev-setup.sh
│
├── .livchat/               # Default config location (user home)
│   ├── config.yaml
│   ├── state.json
│   └── credentials.vault
│
├── pyproject.toml          # Python project config
├── requirements.txt        # Python dependencies
├── Makefile               # Common tasks
├── DESIGN.md              # This document
└── README.md
```

### 7.2 Rationale [DECIDIDO]

**Por que esta estrutura?**

1. **`src/` flat**: Evita redundância de `src/livchat/`, código mais direto
2. **Separação clara**: Core, apps, ansible, integrations são distintos
3. **Apps como YAML**: Facilita adicionar novas aplicações sem código
4. **MCP isolado**: TypeScript separado do Python
5. **`.livchat/` padrão**: Configuração do usuário fora do código

**Decisões importantes:**
- Sem `src/livchat/` redundante - mais direto
- Apps definidas em YAML, não em Python
- Ansible separado mas integrado
- MCP como projeto independente
- Testes próximos ao código que testam

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

### 8.2 MCP Tools [DECIDIDO]
```typescript
tools = [
    "listar-servidores",
    "criar-servidor",
    "destruir-servidor",
    "instalar-app",
    "desinstalar-app",
    "configurar-dns",
    "verificar-status",
    "executar-comando",
    "ver-logs",
    "backup-servidor"
]
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

### Phase 1: Core & Base [Weeks 1-2]
- [x] Design document
- [ ] Project structure
- [ ] Core orchestrator
- [ ] State manager
- [ ] Basic API

### Phase 2: Provider & Apps [Weeks 3-4]
- [ ] Hetzner provider
- [ ] Ansible runner
- [ ] Dependency resolver
- [ ] Basic apps (postgres, redis)

### Phase 3: Integrations [Week 5]
- [ ] Portainer API
- [ ] Cloudflare API
- [ ] Post-deploy configs

### Phase 4: MCP Gateway [Week 6]
- [ ] TypeScript server
- [ ] Tool implementations
- [ ] NPM package

### Phase 5: Testing & Polish [Weeks 7-8]
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation
- [ ] Docker image

## 11. Testing Strategy

### Unit Tests [A DESENVOLVER]
```python
# pytest + pytest-asyncio
tests/
├── test_providers/
├── test_dependencies/
├── test_state/
└── test_api/
```

### Integration Tests [A DESENVOLVER]
```python
# Scenarios
- Deploy N8N com dependências
- Multi-server deployment
- Rollback após falha
- Configuração via API
```

### E2E Tests [A DESENVOLVER]
```python
# Via MCP
- Criar servidor via Claude
- Instalar stack completa
- Verificar funcionamento
```

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