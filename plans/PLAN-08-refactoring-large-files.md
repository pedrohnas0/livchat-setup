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

### Fase 1: orchestrator.py (Prioridade MÁXIMA) - 🟡 EM PROGRESSO
- [x] Mapear todos os métodos e responsabilidades
- [x] Criar estrutura src/orchestrator/
- [x] Implementar ProviderManager (46 linhas, 6 tests)
- [x] Implementar ServerManager (151 linhas, 14 tests)
- [ ] 🟡 Implementar DeploymentManager (em progresso)
- [ ] Implementar DNSManager
- [ ] Implementar IntegrationManager
- [ ] Implementar core.py (facade pattern)
- [ ] Atualizar imports em toda codebase
- [ ] Rodar testes unitários
- [ ] Rodar testes de integração
- [ ] Rodar E2E test (obrigatório)

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

- 🟡 **EM PROGRESSO** (Fase 1 - 40% completa)
- Criado: 2025-10-19
- Atualizado: 2025-10-19 (v0.2.5)
- Progresso:
  - ✅ ProviderManager (46 linhas, 6 tests)
  - ✅ ServerManager (151 linhas, 14 tests)
  - 🟡 DeploymentManager (próximo)
  - ⚪ DNSManager
  - ⚪ IntegrationManager
  - ⚪ core.py facade
- Estimativa restante: ~30h
- Prioridade: **CRÍTICA** (fundação para manutenibilidade)
