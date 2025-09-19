# Plan 03: Integration Layer - Portainer, Cloudflare & App Registry

## 🟢 STATUS: CORE IMPLEMENTATION COMPLETE

### ✅ Implementação Concluída com Sucesso!
- **70% das tasks completas** (7 de 10)
- **77 testes unitários passando**
- **Todos os componentes core funcionais**
- **Inicialização automática do Portainer implementada**

### 📊 Resumo Executivo:
| Componente | Status | Testes | Observações |
|------------|--------|--------|-------------|
| Portainer Client | ✅ | 9/9 | JWT auth, CRUD stacks, auto-init |
| Cloudflare Client | ✅ | 10/10 | Global API Key, DNS management |
| App Registry | ✅ | 14/14 | YAML loader, dependency resolver |
| App Deployer | ✅ | 15/15 | Deploy orchestration, health checks |
| CLI Integration | ✅ | 29/29 | deploy-app, list-apps, etc |
| App Definitions | ✅ | ✅ | 5 apps: Portainer, PostgreSQL, Redis, N8N, Chatwoot |
| **Auto-init Portainer** | ✅ | ✅ | **EXTRA: Zero manual intervention!** |

### ⏳ Pendente:
- Integration Tests (Task 8)
- E2E Tests (Task 9)
- Documentation (Task 10)

## 📋 Contexto

Conforme **CLAUDE.md Phase 3: Integrations**, precisamos implementar:
- Portainer API client (próprio, sem SDKs de terceiros)
- Cloudflare API integration (SDK oficial)
- App Registry com definições YAML
- Post-deploy configurations

## 🎯 Objetivo

Criar a camada de integração para gerenciar aplicações via Portainer e DNS via Cloudflare, com sistema de App Registry para definir e deployar apps de forma padronizada.

## 🔐 Fluxo de Segurança e Inicialização

### Configuração Inicial Necessária
```bash
# 1. Configurar email do admin (usado no Portainer e outras apps)
livchat-setup configure --admin-email seu@email.com

# 2. Configurar Cloudflare (Global API Key)
livchat-setup configure --cloudflare-email cloudflare@email.com --cloudflare-key <global_api_key>

# 3. Configurar provider (Hetzner)
livchat-setup configure hetzner --token <hetzner_token>
```

### Gestão de Credenciais com Vault
- **Senhas Seguras**: 64 caracteres gerados automaticamente
- **Armazenamento**: Ansible Vault criptografado
- **Sem Hardcode**: Nenhum dado pessoal no código
- **Global API Key**: Armazenado com segurança no Vault

### Inicialização Automática do Portainer
A API do Portainer **suporta criação automática do primeiro admin** via `/api/users/admin/init`:
```
POST /api/users/admin/init
{
  "Username": "admin_email@example.com",
  "Password": "64_character_secure_password"
}
```
**Fluxo Implementado:**
1. Deploy do Portainer via Ansible
2. Aguarda Portainer ficar ready (health check)
3. Gera credenciais seguras (ou usa do Vault se existir)
4. Cria admin automaticamente via API
5. Salva credenciais no Vault
6. Mostra URL de acesso ao usuário
7. **Sem interação humana necessária!**

## 📊 Escopo Definitivo

### Componente 1: Portainer Client (Próprio)

```python
# src/integrations/portainer.py
class PortainerClient:
    """Cliente REST próprio para Portainer API v2.x"""

    def __init__(self, url: str, username: str, password: str):
        """Inicializa cliente com autenticação"""

    async def authenticate(self) -> str:
        """POST /api/auth - Retorna JWT token"""

    async def create_stack(self, name: str, compose: str, env: Dict) -> Dict:
        """POST /api/stacks - Deploy de stack"""

    async def get_stack(self, stack_id: int) -> Dict:
        """GET /api/stacks/{id} - Info da stack"""

    async def delete_stack(self, stack_id: int) -> bool:
        """DELETE /api/stacks/{id} - Remove stack"""

    async def list_endpoints(self) -> List[Dict]:
        """GET /api/endpoints - Lista environments"""
```

**Por que cliente próprio?** Controle total sobre a implementação, sem dependências externas, melhor para manutenção.

### Componente 2: Cloudflare Client (SDK Oficial com Global API Key)

```python
# src/integrations/cloudflare.py
class CloudflareClient:
    """Wrapper do SDK oficial cloudflare usando Global API Key + Email"""

    def __init__(self, email: str, global_api_key: str):
        """Inicializa com email + Global API Key
        self.client = Cloudflare(api_email=email, api_key=global_api_key)
        """

    async def list_zones(self) -> List[Zone]:
        """Lista todas as zonas DNS disponíveis (ex: livchat.ai)"""

    async def get_zone(self, zone_name: str) -> Zone:
        """Obtém zona específica por nome"""

    async def create_dns_record(self, zone_id: str, type: str, name: str,
                              content: str, proxied: bool = False,
                              comment: str = None) -> str:
        """Cria registro DNS genérico"""

    async def setup_server_dns(self, server: Dict, zone_name: str, subdomain: str = None):
        """Configura DNS principal do servidor (registro A do Portainer)
        - Cria: ptn.{subdomain}.{zone} ou ptn.{zone} -> IP
        - Comment: "portainer"
        - Proxied: false
        """

    async def add_app_dns(self, app_prefix: str, zone_name: str, subdomain: str = None,
                         comment: str = None):
        """Adiciona CNAME para aplicação
        - Cria: {app_prefix}.{subdomain}.{zone} -> ptn.{subdomain}.{zone}
        - Comment: nome da app
        - Proxied: false
        """
```

#### Padrão de DNS Implementado

**Template Padrão:**
```dns
;; A Records
ptn.seu-dominio.com.        1 IN  A 0.0.0.0 ; portainer cf_tags=cf-proxied:false

;; CNAME Records
log.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; dozzle cf_tags=cf-proxied:false
gfn.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; grafana cf_tags=cf-proxied:false
pga.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; pgadmin cf_tags=cf-proxied:false
rmq.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; rabbit cf_tags=cf-proxied:false
mno.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; minio cf_tags=cf-proxied:false
s3.seu-dominio.com.         1 IN  CNAME ptn.seu-dominio.com. ; backend minio cf_tags=cf-proxied:false
dir.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; directus cf_tags=cf-proxied:false
chat.seu-dominio.com.       1 IN  CNAME ptn.seu-dominio.com. ; chatwoot cf_tags=cf-proxied:false
evo.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; evolution cf_tags=cf-proxied:false
edt.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; n8n cf_tags=cf-proxied:false
whk.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; n8n webhook cf_tags=cf-proxied:false
pdf.seu-dominio.com.        1 IN  CNAME ptn.seu-dominio.com. ; pdf cf_tags=cf-proxied:false
```

**Com Subdomínio (lab, dev, ops, etc):**
```dns
;; A Records
ptn.lab.livchat.ai.         1 IN  A 168.119.89.45 ; portainer cf_tags=cf-proxied:false

;; CNAME Records
chat.lab.livchat.ai.        1 IN  CNAME ptn.lab.livchat.ai. ; chatwoot cf_tags=cf-proxied:false
edt.lab.livchat.ai.         1 IN  CNAME ptn.lab.livchat.ai. ; n8n cf_tags=cf-proxied:false
```

**Nomenclatura Padrão:**
- `ptn` - Portainer (SEMPRE registro A principal)
- `log` - Dozzle (logs)
- `gfn` - Grafana
- `pga` - pgAdmin
- `rmq` - RabbitMQ
- `mno` - MinIO
- `s3` - MinIO S3 backend
- `dir` - Directus
- `chat` - Chatwoot
- `evo` - Evolution API
- `edt` - N8N Editor
- `whk` - N8N Webhook
- `pdf` - PDF Service

**Regras:**
1. Proxy SEMPRE desativado (`cf-proxied:false`)
2. Comentários simples com nome da app
3. Todos CNAMEs apontam para `ptn.{subdomain}.{zone}`
4. Mudança de IP = atualizar apenas registro A do `ptn`

### Componente 3: App Registry

```python
# src/app_registry.py
class AppRegistry:
    """Sistema de registro e definição de aplicações"""

    def load_definitions(self, path: str = "apps/") -> None:
        """Carrega todas as definições YAML"""

    def get_app(self, name: str) -> AppDefinition:
        """Retorna definição de uma app"""

    def validate_app(self, app: AppDefinition) -> ValidationResult:
        """Valida schema e dependências"""

    def generate_compose(self, app: AppDefinition, config: Dict) -> str:
        """Gera docker-compose.yml para a app"""

    def resolve_dependencies(self, app_name: str) -> List[str]:
        """Resolve ordem de instalação com dependências"""
```

### Componente 4: App Deployer

```python
# src/app_deployer.py
class AppDeployer:
    """Orquestra deploy de aplicações"""

    def __init__(self, portainer: PortainerClient,
                 cloudflare: CloudflareClient,
                 registry: AppRegistry):
        """Injeta dependências"""

    async def deploy(self, server: Server, app_name: str, config: Dict) -> Result:
        """Deploy completo da aplicação"""

    async def configure_dns(self, server: Server, app: str, domain: str) -> Result:
        """Configura DNS para a aplicação"""

    async def verify_health(self, server: Server, app: str) -> HealthStatus:
        """Verifica saúde da aplicação"""

    async def rollback(self, server: Server, app: str) -> Result:
        """Rollback em caso de falha"""
```

### Componente 5: Definições YAML

```yaml
# apps/definitions/infrastructure/portainer.yaml
name: portainer
category: infrastructure
version: "2.19.4"
description: Container management platform

ports:
  - "9443:9443"  # HTTPS UI
  - "8000:8000"  # Edge agent

volumes:
  - portainer_data:/data

environment:
  - ADMIN_PASSWORD: "{{ vault.portainer_password }}"

deploy:
  mode: global
  placement:
    constraints:
      - node.role == manager

health_check:
  endpoint: https://localhost:9443
  interval: 30s
  retries: 3
```

## 🧪 Estratégia de Testes TDD

### Etapa 1: Portainer Client Tests
```python
# tests/unit/test_portainer_client.py

def test_authentication_success():
    """Testa autenticação bem sucedida"""

def test_authentication_failure():
    """Testa falha de autenticação"""

def test_create_stack():
    """Testa criação de stack com mock"""

def test_stack_not_found():
    """Testa erro 404 ao buscar stack"""

def test_retry_on_timeout():
    """Testa retry automático em timeout"""
```

### Etapa 2: Cloudflare Client Tests
```python
# tests/unit/test_cloudflare_client.py

def test_zone_listing():
    """Testa listagem de zonas DNS"""

def test_create_a_record():
    """Testa criação de registro A"""

def test_create_cname_record():
    """Testa criação de CNAME"""

def test_enable_proxy():
    """Testa ativação do proxy Cloudflare"""
```

### Etapa 3: App Registry Tests
```python
# tests/unit/test_app_registry.py

def test_load_yaml_definitions():
    """Testa carregamento de definições"""

def test_validate_app_schema():
    """Testa validação de schema YAML"""

def test_dependency_resolution():
    """Testa resolução de dependências"""

def test_circular_dependency_detection():
    """Testa detecção de dependência circular"""
```

### Etapa 4: Integration Tests
```python
# tests/integration/test_portainer_integration.py

@pytest.mark.integration
async def test_portainer_real_deployment():
    """Deploy real no Portainer local"""

# tests/integration/test_cloudflare_integration.py

@pytest.mark.integration
async def test_dns_record_lifecycle():
    """Cria, atualiza e deleta registro DNS"""
```

### Etapa 5: E2E Tests
```python
# tests/e2e/test_complete_app_deployment.py

@pytest.mark.e2e
async def test_deploy_postgres_with_dns():
    """Deploy completo: Postgres + DNS + Health check"""
```

## 📁 Estrutura de Arquivos

```
LivChatSetup/
├── src/
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── portainer.py       # Cliente REST próprio
│   │   └── cloudflare.py      # Wrapper do SDK oficial
│   ├── app_registry.py        # Sistema de registro
│   ├── app_deployer.py        # Orquestrador de deploy
│   └── orchestrator.py        # ATUALIZAR
│
├── apps/
│   ├── catalog.yaml           # Índice de apps
│   ├── schemas/
│   │   └── app-definition.json # JSON Schema para validação
│   └── definitions/
│       ├── infrastructure/
│       │   └── portainer.yaml
│       ├── databases/
│       │   ├── postgres.yaml
│       │   └── redis.yaml
│       └── applications/
│           ├── n8n.yaml
│           └── chatwoot.yaml
│
├── ansible/
│   └── playbooks/
│       └── portainer-deploy.yml
│
├── templates/
│   ├── portainer-stack.j2
│   └── app-compose.j2
│
└── tests/
    ├── unit/
    │   ├── test_portainer_client.py
    │   ├── test_cloudflare_client.py
    │   ├── test_app_registry.py
    │   └── test_app_deployer.py
    ├── integration/
    │   ├── test_portainer_integration.py
    │   └── test_cloudflare_integration.py
    └── e2e/
        └── test_complete_app_deployment.py
```

## ✅ Checklist de Implementação

### Task 1: Portainer Deployment
- [x] Criar playbook `portainer-deploy.yml`
- [x] Template Jinja2 para stack
- [x] Integrar no ServerSetup
- [ ] Test: Deploy em servidor real

### Task 2: Portainer Client ✅ COMPLETED
- [x] TDD: Escrever testes unitários
- [x] Implementar autenticação JWT
- [x] Implementar CRUD de stacks
- [x] Implementar gestão de endpoints
- [x] Test: Mock responses

### Task 3: Cloudflare Client ✅ COMPLETED
- [x] TDD: Escrever testes unitários
- [x] Wrapper do SDK oficial
- [x] Métodos para DNS records
- [x] Proxy e SSL config
- [x] Test: Com zona de teste (mocks)

### Task 4: App Registry ✅ COMPLETED
- [x] TDD: Escrever testes unitários
- [x] Schema JSON para validação
- [x] Loader de definições YAML
- [x] Dependency resolver
- [x] Template engine
- [x] Test: Validação de schemas

### Task 5: App Deployer ✅ COMPLETED
- [x] TDD: Escrever testes unitários
- [x] Orquestração de deploy
- [x] Configuração DNS automática
- [x] Health checks
- [x] Rollback mechanism
- [x] Test: Deploy mock

### Task 6: App Definitions ✅ COMPLETED
- [x] Definir schema padrão
- [x] Criar catalog.yaml
- [x] Portainer definition
- [x] Postgres definition
- [x] Redis definition
- [x] Test: Validar YAMLs
- [x] N8N definition (EXTRA)
- [x] Chatwoot definition (EXTRA)

### Task 7: CLI Integration ✅ COMPLETED
- [x] Comando `deploy-app`
- [x] Comando `list-apps`
- [x] Comando `setup-dns` (equivalente)
- [x] Comando `add-app-dns` (equivalente)
- [x] Comando `delete-app`
- [x] Comando `app-status`
- [x] Test: CLI commands (parcial)

### Task 8: Integration Tests ⏳ PENDING
- [ ] Portainer local test
- [ ] Cloudflare sandbox test
- [ ] App deployment test
- [ ] DNS configuration test

### Task 9: E2E Test ⏳ PENDING
- [ ] Setup servidor completo
- [ ] Deploy Portainer
- [ ] Deploy Postgres
- [ ] Configurar DNS
- [ ] Verificar health

### Task 10: Documentation ⏳ PENDING
- [ ] API documentation
- [ ] App definition guide
- [ ] Deployment examples
- [ ] Troubleshooting guide

## 📦 Dependências Novas

```txt
# requirements.txt
cloudflare>=3.0.0       # SDK oficial Cloudflare (suporta Global API Key)
httpx>=0.25.0          # Cliente HTTP async para Portainer
pyyaml>=6.0            # Parser YAML
jsonschema>=4.0        # Validação de schemas
tenacity>=8.0          # Retry logic
```

## 🗄️ State Management Simplificado

### Estrutura do state.json (MINIMAL)

```json
{
  "servers": {
    "srv1": {
      "name": "srv1",
      "ip": "168.119.89.45",
      "provider": "hetzner",
      "dns": {
        "zone": "livchat.ai",
        "subdomain": "lab"
      }
    },
    "srv2": {
      "name": "srv2",
      "ip": "192.168.1.100",
      "provider": "hetzner",
      "dns": {
        "zone": "livchat.ai",
        "subdomain": "dev"
      }
    }
  },
  "config": {
    "admin_email": "user@example.com",
    "default_zone": "livchat.ai",
    "cloudflare_email": "cloudflare@example.com"
  }
}
```

**Princípio:**
- ❌ NÃO armazenar registros DNS (consultar Cloudflare diretamente)
- ❌ NÃO armazenar lista de aplicações (consultar Portainer diretamente)
- ✅ Armazenar apenas dados essenciais e reutilizáveis
- ✅ Zone e subdomain para recriar DNS se necessário

## 🎮 CLI Commands

```bash
# Configurar Cloudflare
livchat-setup configure --cloudflare-email user@example.com --cloudflare-key <global_api_key>

# Deploy de aplicação com DNS automático
livchat-setup deploy-app <server> <app> [--zone livchat.ai] [--subdomain lab]

# Configurar DNS do servidor (cria registro A do Portainer)
livchat-setup setup-dns <server> --zone livchat.ai [--subdomain lab]

# Adicionar DNS para app específica (cria CNAME)
livchat-setup add-app-dns <server> <app> [--zone livchat.ai] [--subdomain lab]

# Listar zonas disponíveis no Cloudflare
livchat-setup list-zones

# Status da aplicação
livchat-setup app-status <server> <app>
```

## 🔄 Fluxo de Deploy com DNS

1. **Setup inicial do servidor:**
   ```bash
   # Cria servidor
   livchat-setup create-server srv1

   # Setup completo (Docker, Swarm, Traefik)
   livchat-setup setup-server srv1

   # Deploy Portainer + DNS
   livchat-setup deploy-portainer srv1 --zone livchat.ai --subdomain lab
   # Cria automaticamente: ptn.lab.livchat.ai -> IP (registro A)
   ```

2. **Deploy de aplicações:**
   ```bash
   # Deploy Chatwoot
   livchat-setup deploy-app srv1 chatwoot
   # Cria automaticamente: chat.lab.livchat.ai -> ptn.lab.livchat.ai (CNAME)

   # Deploy N8N
   livchat-setup deploy-app srv1 n8n
   # Cria automaticamente: edt.lab.livchat.ai -> ptn.lab.livchat.ai (CNAME)
   # Cria também: whk.lab.livchat.ai -> ptn.lab.livchat.ai (CNAME para webhook)
   ```

## 🎯 Critérios de Sucesso

```bash
# Comandos funcionando:
python -m src.cli deploy-app srv1 portainer
python -m src.cli deploy-app srv1 postgres --config password=secret
python -m src.cli configure-dns srv1 example.com
python -m src.cli list-apps

# Verificações:
curl -I https://portainer.srv1.example.com  # 200 OK
psql -h srv1.example.com -U postgres         # Conecta
dig srv1.example.com                         # Retorna IP correto
```

## 📊 Métricas

- **Cobertura de testes:** >85%
- **Deploy de app simples:** <2 minutos
- **Deploy com dependências:** <5 minutos
- **Configuração DNS:** <30 segundos
- **Apps catalogadas:** 10+ ao final

## ⚠️ Considerações Importantes

1. **Cliente Portainer próprio** para controle total e sem dependências externas
2. **SDK Cloudflare oficial** por ser bem mantido e type-safe
3. **Validação rigorosa** de definições YAML antes do deploy
4. **Idempotência** em todos os deploys
5. **Health checks** obrigatórios pós-deploy

## 🚀 Próximos Passos (Plan-04)

1. Deploy N8N com dependências completas
2. Sistema de backup automatizado
3. Monitoring com Grafana/Prometheus
4. Post-deploy API configurations
5. Multi-server app deployment

## 🎯 Funcionalidades Extras Implementadas

### Etapa 5: Recursos Adicionais ✅ COMPLETED
- [x] **Inicialização automática do Portainer** - Admin criado automaticamente via API
- [x] **Geração de senhas seguras** - 64 caracteres com PasswordGenerator
- [x] **Integração completa no Orchestrator** - AppDeployer e AppRegistry integrados
- [x] **Sistema de health check com retry** - Aguarda serviços ficarem prontos
- [x] **Método wait_for_ready** - Espera Portainer estar disponível antes de inicializar
- [x] **Armazenamento seguro de credenciais** - Vault criptografado com Ansible Vault

## 📊 Status

- **Fase:** ✅ Implementation COMPLETED
- **Início:** 2025-01-18
- **Conclusão:** 2025-01-19
- **Status:** 🟢 CORE FEATURES COMPLETED
- **Testes Unitários:** 77/77 passando ✅
- **Cobertura:** Tasks 1-7 completas (70%)

### Resumo de Progresso:
- ✅ **7 de 10 Tasks Completas**
- ✅ **Todos os componentes core implementados**
- ✅ **77 testes unitários passando**
- ✅ **Integração CLI funcional**
- ⏳ **Pendente:** Testes de integração/E2E e documentação

### Principais Conquistas:
1. **Portainer Client próprio** - Sem dependências externas
2. **Cloudflare com Global API Key** - Integração completa
3. **App Registry com YAML** - 5 apps definidas
4. **App Deployer funcional** - Deploy, DNS, health checks
5. **Auto-init do Portainer** - Zero interação manual
6. **Padrão de testes estabelecido** - Mock em nível de método

---

*Versão: 1.1.0*
*Data Criação: 2025-01-18*
*Data Conclusão Core: 2025-01-19*
*Status: Core Implementation Complete*
*Abordagem: TDD, Integration-first, Production-ready*