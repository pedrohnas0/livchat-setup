# PLAN-08: Refatoração de Arquivos Grandes

## 📋 Contexto

**Problema:** Múltiplos arquivos excedem 400 linhas (meta de qualidade)

**Descoberta crítica:**
```
orchestrator.py    - 1130 linhas 🚨 CRÍTICO
server_setup.py    - 746 linhas  🚨 CRÍTICO
storage.py         - 661 linhas  🚨 CRÍTICO
app_deployer.py    - 642 linhas  🚨 CRÍTICO
cloudflare.py      - 623 linhas  🚨 ALTO
portainer.py       - 575 linhas  🚨 ALTO
app_registry.py    - 491 linhas  ⚠️ MÉDIO
job_manager.py     - 456 linhas  ⚠️ MÉDIO
cli.py             - 407 linhas  ⚠️ MÉDIO
```

**Total:** 6.645 linhas em 9 arquivos (precisa ser dividido)

**Meta:** Arquivos < 400 linhas cada

---

## 🎯 Objetivo

Dividir arquivos grandes em módulos menores mantendo:
1. ✅ Coesão funcional
2. ✅ Single Responsibility Principle
3. ✅ Facilidade de teste
4. ✅ Imports claros

---

## 📊 Priorização (Ordem de Refatoração)

### Prioridade 1: CRÍTICA (> 700 linhas)

**1. orchestrator.py (1130 linhas) - MAIOR ARQUIVO**
**2. server_setup.py (746 linhas)**

### Prioridade 2: ALTA (600-700 linhas)

**3. storage.py (661 linhas)**
**4. app_deployer.py (642 linhas)**
**5. cloudflare.py (623 linhas)**
**6. portainer.py (575 linhas)**

### Prioridade 3: MÉDIA (400-500 linhas)

**7. app_registry.py (491 linhas)**
**8. job_manager.py (456 linhas)**
**9. cli.py (407 linhas)**

---

## 🔨 REFATORAÇÃO #1: orchestrator.py (1130 linhas)

### Análise Atual

**Responsabilidades identificadas:**
```bash
# Grep analysis:
- Server management (create, delete, list, get)
- DNS configuration (setup_dns_for_server, add_app_dns)
- Provider configuration
- App deployment (deploy_app, deploy_app_sync)
- SSH setup
- Server setup orchestration
- Cloudflare integration
- Portainer integration
```

**Problema:** God Class - responsabilidades demais!

### Proposta de Divisão

```
src/orchestrator/
├── __init__.py              # Facade pattern - API pública
├── core.py                  # Core orchestrator (~150 linhas)
├── server_manager.py        # Server CRUD (~200 linhas)
├── deployment_manager.py    # App deployment (~250 linhas)
├── dns_manager.py           # DNS operations (~150 linhas)
├── provider_manager.py      # Provider setup (~100 linhas)
└── integration_manager.py   # Cloudflare, Portainer (~150 linhas)
```

**Benefícios:**
- Módulos coesos (< 250 linhas cada)
- Testável individualmente
- Fácil de entender

### Código de Migração

**ANTES:**
```python
# orchestrator.py (1130 linhas)
class Orchestrator:
    def create_server(self):
        ...
    def deploy_app(self):
        ...
    def setup_dns(self):
        ...
    # + 50 métodos
```

**DEPOIS:**
```python
# orchestrator/core.py
class Orchestrator:
    def __init__(self):
        self.server_manager = ServerManager(self.storage)
        self.deployment_manager = DeploymentManager(self.storage, self.app_registry)
        self.dns_manager = DNSManager(self.cloudflare_client)

    def create_server(self, *args):
        return self.server_manager.create(*args)

    def deploy_app(self, *args):
        return self.deployment_manager.deploy(*args)

# orchestrator/server_manager.py
class ServerManager:
    def create(self, name, server_type, location):
        ...
    def delete(self, name):
        ...
```

**Estimativa:** 16h (dividir + testes)

---

## 🔨 REFATORAÇÃO #2: server_setup.py (746 linhas)

### Análise Atual

**Responsabilidades:**
```bash
- Base setup (apt update, timezone, etc)
- Docker installation
- Swarm initialization
- Stack deployment (Traefik, Portainer)
- Infrastructure deployment via YAML
```

### Proposta de Divisão

```
src/server_setup/
├── __init__.py              # Facade
├── coordinator.py           # Orquestração (~150 linhas)
├── base_setup.py            # System prep (~150 linhas)
├── docker_setup.py          # Docker + Swarm (~150 linhas)
├── stack_deployer.py        # Stack deployment (~200 linhas)
└── utils.py                 # SSH wait, connectivity (~100 linhas)
```

**Estimativa:** 12h

---

## 🔨 REFATORAÇÃO #3: storage.py (661 linhas)

### Análise Atual

**Classes:** ConfigStore (120 linhas) + StateStore (235 linhas) + SecretsStore (162 linhas) + StorageManager (70 linhas)

### Proposta de Divisão

**JÁ BEM DIVIDIDO internamente!**

**Opção:**
```
src/storage/
├── __init__.py              # Re-export tudo
├── config_store.py          # ConfigStore (150 linhas)
├── state_store.py           # StateStore (250 linhas)
├── secrets_store.py         # SecretsStore (200 linhas)
└── manager.py               # StorageManager (80 linhas)
```

**Estimativa:** 6h (baixa prioridade, já bem organizado)

---

## 🔨 REFATORAÇÃO #4: app_deployer.py (642 linhas)

### Análise (precisa investigar métodos)

**Provável divisão:**
```
src/deployment/
├── __init__.py
├── app_deployer.py          # Coordenação (~200 linhas)
├── dependency_resolver.py   # Resolve deps (~150 linhas)
├── dns_configurator.py      # DNS setup (~150 linhas)
└── health_checker.py        # Health checks (~150 linhas)
```

**Estimativa:** 10h

---

## 🔨 REFATORAÇÕES #5-6: Integrations

### cloudflare.py (623 linhas) + portainer.py (575 linhas)

**Análise:** Provavelmente muitos métodos de API

**Opção 1:** Dividir por funcionalidade (zones, DNS, records)
**Opção 2:** Manter (clients de API podem ser grandes, é aceitável)

**Decisão:** Investigar depois (baixa prioridade se código é só wrapper de API)

**Estimativa:** 8h cada (se necessário)

---

## 🧪 TDD: Refatoração de Testes

### Problema Atual

**Estrutura confusa:**
```
tests/
├── unit/
│   ├── api/                    # ✅ Organizado
│   └── test_*.py               # ❌ Tudo junto sem estrutura
├── integration/                # ❌ Sem organização
└── e2e/                        # ❌ Sem organização
```

**Problemas:**
1. Testes quebrados com mudanças recentes
2. Estrutura não reflete src/
3. Difícil encontrar testes de um módulo específico

### Estrutura Proposta

**Espelhar src/ exatamente:**
```
tests/
├── unit/
│   ├── orchestrator/           # Quando dividirmos
│   │   ├── test_core.py
│   │   ├── test_server_manager.py
│   │   └── test_deployment_manager.py
│   ├── server_setup/
│   │   ├── test_coordinator.py
│   │   └── test_docker_setup.py
│   ├── storage/
│   │   ├── test_config_store.py
│   │   ├── test_state_store.py
│   │   └── test_secrets_store.py
│   ├── providers/
│   │   ├── test_base.py
│   │   └── test_hetzner.py
│   ├── integrations/
│   │   ├── test_portainer.py
│   │   └── test_cloudflare.py
│   ├── api/                    # ✅ Já organizado
│   └── utils/
│       └── test_dns_utils.py
├── integration/
│   ├── test_full_deployment.py
│   ├── test_server_lifecycle.py
│   └── test_app_deployment.py
└── e2e/
    └── test_complete_workflow.py
```

### Abordagem TDD para Refatoração

**Para cada módulo dividido:**

1. **ANTES de mover código:**
   ```bash
   # Criar testes para comportamento existente
   pytest tests/unit/test_orchestrator.py -v  # Garante que funciona
   ```

2. **Durante divisão:**
   ```bash
   # Criar testes para CADA novo módulo
   tests/unit/orchestrator/test_server_manager.py

   # Testar isoladamente
   pytest tests/unit/orchestrator/test_server_manager.py -v
   ```

3. **Após divisão:**
   ```bash
   # Rodar TODOS os testes
   pytest tests/ -v

   # Verificar cobertura não caiu
   pytest --cov=src --cov-report=term-missing
   ```

### Meta de Cobertura

**Mínimo:** 80% nos módulos refatorados
**Ideal:** 90%+ nos novos módulos

## ✅ Checklist de Implementação

### Fase 0: Reestruturar Testes (PRIMEIRO!)
- [ ] Criar estrutura tests/unit/ espelhando src/
- [ ] Mover testes existentes para pastas corretas
- [ ] Fixar testes quebrados
- [ ] Rodar suite completa - tudo verde
- [ ] Baseline: pytest --cov=src (registrar %)

### Fase 1: orchestrator.py (Prioridade MÁXIMA) - 🟡 EM PROGRESSO (~85% completo)

#### ✅ Managers Implementados (Completo)
- [x] Mapear todos os métodos e responsabilidades
- [x] Criar estrutura src/orchestrator/
- [x] Implementar ProviderManager (46 linhas, 6 tests) ✅
- [x] Implementar ServerManager (151 linhas, 14 tests) ✅
- [x] Implementar DeploymentManager (387 linhas, tests passing) ✅
- [x] Implementar DNSManager (120 linhas) ✅

#### 🟡 Core.py - QUASE COMPLETO (Falta Infraestrutura)

**STATUS ATUAL:**
- ✅ Facade pattern implementado
- ✅ Todos os managers inicializados e conectados
- ✅ Delegação funcionando para: servers, deployment, DNS, provider
- ❌ FALTANDO: Métodos de infraestrutura (deploy_traefik, deploy_portainer, setup_server)

**PROBLEMA DESCOBERTO:**
- `orchestrator_old.py` (1130 linhas) ainda está sendo usado por `infrastructure_executor.py` e `server_executor.py`
- E2E test falha porque `core.py` não tem métodos de infraestrutura
- Portainer authentication failing: orchestrator_old.py inicializa cliente, mas core.py cria novo cliente

**SOLUÇÃO (Padrão DELEGATION):**
```python
# orchestrator_old.py usa DELEGATION (padrão correto):
def deploy_traefik(self, server_name: str, ssl_email: str = None) -> bool:
    server = self.get_server(server_name)
    if not server:
        return False

    config = {}
    if ssl_email:
        config["ssl_email"] = ssl_email

    result = self.server_setup.deploy_traefik(server, config)  # ← DELEGA
    return result.success

# core.py precisa do MESMO PADRÃO (não copiar lógica toda)
```

#### 📋 Checklist Detalhado: Completar core.py

**Etapa 1: Adicionar Componentes de Infraestrutura**
- [ ] Importar `AnsibleRunner` e `ServerSetup` em core.py
- [ ] Adicionar ao `__init__`:
  ```python
  self.ansible_runner = AnsibleRunner(self.ssh_manager)
  self.server_setup = ServerSetup(self.ansible_runner, self.storage)
  ```

**Etapa 2: Métodos Thin Wrappers (Infraestrutura)**
- [ ] Adicionar `deploy_traefik(server_name, ssl_email)` - delegado a server_setup (2-5 linhas)
  ```python
  def deploy_traefik(self, server_name: str, ssl_email: str = None) -> bool:
      server = self.get_server(server_name)
      if not server:
          return False

      config = {}
      if ssl_email:
          config["ssl_email"] = ssl_email

      result = self.server_setup.deploy_traefik(server, config)
      return result.success
  ```

- [ ] Adicionar `deploy_portainer(server_name, config)` - wrapper + admin init (~30 linhas)
  ```python
  def deploy_portainer(self, server_name: str, config: Dict = None) -> bool:
      server = self.get_server(server_name)
      if not server:
          return False

      # Deploy via server_setup
      result = self.server_setup.deploy_portainer(server, config or {})

      if result.success:
          # Admin initialization (reusa código existente)
          server_ip = server.get("ip")
          portainer_password = self.storage.secrets.get_secret(f"portainer_password_{server_name}")

          # Create and SAVE Portainer client for reuse
          self.portainer = PortainerClient(...)

          # Initialize admin (async)
          import asyncio
          ready = asyncio.run(self.portainer.wait_for_ready(...))
          if ready:
              asyncio.run(self.portainer.initialize_admin())

      return result.success
  ```

- [ ] Adicionar `setup_server(server_name, zone_name, subdomain, config)` - delega a server_setup (~15 linhas)
  ```python
  def setup_server(self, server_name: str, zone_name: str,
                   subdomain: Optional[str] = None,
                   config: Optional[Dict] = None) -> Dict[str, Any]:
      server = self.get_server(server_name)
      if not server:
          raise ValueError(f"Server {server_name} not found")

      # Save DNS config to state
      dns_config = {"zone_name": zone_name}
      if subdomain:
          dns_config["subdomain"] = subdomain

      server["dns_config"] = dns_config
      self.storage.state.update_server(server_name, server)

      # Delegate to server_setup
      result = self.server_setup.full_setup(server, config)

      # Update state
      if result.success:
          server["setup_status"] = "complete"
      else:
          server["setup_status"] = f"failed_at_{result.step}"

      self.storage.state.update_server(server_name, server)

      return {
          "success": result.success,
          "message": result.message,
          "server": server_name,
          "dns_config": dns_config
      }
  ```

**Etapa 3: Métodos CLI (Opcionais - apenas se usados)**
- [ ] Adicionar `install_docker(server_name)` - delegado a server_setup (2-5 linhas)
- [ ] Adicionar `init_swarm(server_name, network_name)` - delegado a server_setup (2-5 linhas)

**Etapa 4: Validação**
- [ ] Rodar testes unitários: `pytest tests/unit/orchestrator/ -v`
- [ ] Rodar E2E test: `cd mcp-server && npm run test:e2e` (OBRIGATÓRIO)
- [ ] Verificar Portainer authentication funcionando
- [ ] Verificar infrastructure deployment completo

**Etapa 5: Cleanup Final**
- [ ] Deletar `orchestrator_old.py` (após E2E passar)
- [ ] Atualizar imports em `infrastructure_executor.py` e `server_executor.py`
- [ ] Commitar mudanças

### Fase 2: server_setup.py
- [ ] Criar estrutura src/server_setup/
- [ ] Dividir em módulos
- [ ] Atualizar imports
- [ ] Testes

### Fase 3: app_deployer.py
- [ ] Criar estrutura src/deployment/
- [ ] Dividir em módulos
- [ ] Atualizar imports
- [ ] Testes

### Fase 4: storage.py (Opcional)
- [ ] Criar src/storage/
- [ ] Separar classes
- [ ] Manter compatibilidade

---

## 📦 Dependências

- Nenhuma nova dependência
- Apenas reorganização interna

---

## 🎯 Critérios de Sucesso

1. ✅ Nenhum arquivo src/ > 400 linhas
2. ✅ Todos os testes passando
3. ✅ Imports claros e sem ciclos
4. ✅ Cada módulo tem single responsibility
5. ✅ Cobertura de testes mantida ou melhorada

---

## 📊 Métricas

**Antes:** 9 arquivos > 400 linhas (6.645 linhas total)
**Depois:** ~30 arquivos < 300 linhas cada (mesmas linhas, melhor organizadas)

**Redução de complexidade:**
- orchestrator.py: 1130 → ~6 arquivos de 150-250 linhas
- server_setup.py: 746 → ~5 arquivos de 150 linhas
- app_deployer.py: 642 → ~4 arquivos de 150 linhas

**Benefício:** Arquivos menores = mais fácil entender, testar e manter

---

## ⚠️ Riscos

1. **Breaking changes nos imports**
   - Mitigação: Manter exports públicos em __init__.py

2. **Testes quebrados**
   - Mitigação: Rodar suite completa após cada fase

3. **Ciclos de import**
   - Mitigação: Dependency injection, não imports diretos

---

## 🚀 Próximos Passos

**Depois desta refatoração:**
- PLAN-09: Eliminar Duplicações DRY
- PLAN-10: Atualizar CLAUDE.md

---

## 📊 Status

- 🟡 **EM PROGRESSO** (Fase 1 - 85% completa)
- Criado: 2025-10-19
- Atualizado: 2025-10-19 (v0.2.6 - após investigação profunda)
- Progresso Fase 1:
  - ✅ ProviderManager (46 linhas, 6 tests) - COMPLETO
  - ✅ ServerManager (151 linhas, 14 tests) - COMPLETO
  - ✅ DeploymentManager (387 linhas, tests passing) - COMPLETO
  - ✅ DNSManager (120 linhas) - COMPLETO
  - 🟡 core.py facade (283 linhas) - FALTA INFRAESTRUTURA
    - ✅ Facade pattern implementado
    - ✅ Todos os managers conectados
    - ❌ **FALTAM 3 MÉTODOS**: deploy_traefik, deploy_portainer, setup_server
- Bloqueio Atual:
  - orchestrator_old.py (1130 linhas) ainda em uso
  - E2E test falhando por falta de métodos de infraestrutura em core.py
  - Portainer authentication failing (dois orchestradores coexistindo)
- Próximos Passos (15 minutos de trabalho):
  1. Adicionar ansible_runner + server_setup ao core.py __init__
  2. Adicionar 3 thin wrapper methods (deploy_traefik, deploy_portainer, setup_server)
  3. Rodar E2E test para validar
  4. Deletar orchestrator_old.py
- Estimativa restante: **~1-2h** (último sprint!)
- Prioridade: **CRÍTICA** (fundação para manutenibilidade)

## 🎯 Descobertas da Investigação Profunda

### Problema Raiz Identificado
**Dual Orchestrator Problem:**
- `orchestrator_old.py` usado por `infrastructure_executor.py` e `server_executor.py`
- `orchestrator/core.py` usado por deployment (via job executors)
- Portainer client não compartilhado entre os dois → authentication failing
- E2E test failing porque core.py não tem métodos de infraestrutura

### Solução Elegante (Delegation Pattern)
**NÃO copiar lógica toda para core.py** (seria voltar ao arquivo gigante)
**SIM usar thin wrappers** que delegam para server_setup.py (padrão existente)

```python
# PADRÃO CORRETO (já usado em orchestrator_old.py):
def deploy_traefik(self, server_name: str, ssl_email: str = None) -> bool:
    server = self.get_server(server_name)
    if not server:
        return False

    config = {}
    if ssl_email:
        config["ssl_email"] = ssl_email

    result = self.server_setup.deploy_traefik(server, config)  # ← DELEGA
    return result.success

# RESULTADO: core.py fica pequeno (~350 linhas), lógica fica em server_setup.py
```

### Benefícios da Arquitetura Final
- **orchestrator/core.py**: ~350 linhas (facade + thin wrappers)
- **orchestrator/provider_manager.py**: 46 linhas
- **orchestrator/server_manager.py**: 151 linhas
- **orchestrator/deployment_manager.py**: 387 linhas
- **orchestrator/dns_manager.py**: 120 linhas
- **Total**: ~1054 linhas em 5 arquivos bem organizados
- **vs. orchestrator_old.py**: 1130 linhas em 1 arquivo monolítico
- **Ganho**: Modularidade + testabilidade + manutenibilidade
