# Plan 05: N8N Stack Correction - SetupOrion Pattern Implementation

**Status**: 🟡 IN PROGRESS
**Created**: 2025-01-11
**Context**: Investigation revealed n8n.yaml is malformed - labels outside compose_template are ignored

---

## 📋 Contexto

### Situação Atual
Durante investigação de testes E2E, descobrimos que:
1. **n8n.yaml atual** tem labels na raiz (fora do `compose_template`)
2. **`AppRegistry.generate_compose()`** ignora labels da raiz quando há `compose_template`
3. **Ambos testes E2E** (direto e via API) criam stack SEM labels do Traefik
4. **Testes não validam** se labels foram aplicadas - apenas se deploy=success

### Padrão SetupOrion Correto
```yaml
compose_template: |
  services:
    n8n_editor:      # Serviço 1: Interface de edição
      deploy:
        labels:      # Labels AQUI, dentro do template
          - "traefik.enable=true"

    n8n_webhook:     # Serviço 2: Webhook endpoint
      deploy:
        labels:      # Labels AQUI também
          - "traefik.enable=true"

    n8n_worker:      # Serviço 3: Processamento background
      # SEM labels (backend)

    n8n_redis:       # Serviço 4: Redis dedicado
```

---

## 🎯 Objetivo

Corrigir `n8n.yaml` para seguir o padrão SetupOrion com:
- ✅ **3 serviços N8N**: editor, webhook, worker
- ✅ **1 serviço Redis**: dedicado para o N8N
- ✅ **Labels dentro do template**: deploy.labels em cada serviço
- ✅ **Configuração correta**: seguindo SetupOrion exatamente

---

## 📊 Descobertas do SetupOrion

### Estrutura dos Serviços

#### 1. N8N Editor (Interface de Edição)
```yaml
n8n_editor:
  image: n8nio/n8n:latest
  command: start
  environment:
    - DB_TYPE=postgresdb
    - DB_POSTGRESDB_DATABASE=n8n_queue
    - DB_POSTGRESDB_HOST=postgres
    - DB_POSTGRESDB_PORT=5432
    - DB_POSTGRESDB_USER=postgres
    - DB_POSTGRESDB_PASSWORD={{ vault.postgres_password }}
    - EXECUTIONS_MODE=queue
    - QUEUE_BULL_REDIS_HOST=n8n_redis
    - QUEUE_BULL_REDIS_PORT=6379
    - QUEUE_BULL_REDIS_DB=1
    - N8N_ENCRYPTION_KEY={{ encryption_key }}
    - N8N_HOST={{ domain }}
    - N8N_EDITOR_BASE_URL=https://{{ domain }}/
    - WEBHOOK_URL=https://{{ webhook_domain }}/
    - N8N_PROTOCOL=https
  deploy:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n_editor.rule=Host(`{{ domain }}`)"
      - "traefik.http.routers.n8n_editor.entrypoints=websecure"
      - "traefik.http.routers.n8n_editor.priority=1"
      - "traefik.http.routers.n8n_editor.tls.certresolver=letsencryptresolver"
      - "traefik.http.routers.n8n_editor.service=n8n_editor"
      - "traefik.http.services.n8n_editor.loadbalancer.server.port=5678"
      - "traefik.http.services.n8n_editor.loadbalancer.passHostHeader=1"
```

#### 2. N8N Webhook (Endpoint de Webhooks)
```yaml
n8n_webhook:
  image: n8nio/n8n:latest
  command: webhook
  environment:
    - DB_TYPE=postgresdb
    - DB_POSTGRESDB_DATABASE=n8n_queue
    - DB_POSTGRESDB_HOST=postgres
    - DB_POSTGRESDB_PORT=5432
    - DB_POSTGRESDB_USER=postgres
    - DB_POSTGRESDB_PASSWORD={{ vault.postgres_password }}
    - EXECUTIONS_MODE=queue
    - QUEUE_BULL_REDIS_HOST=n8n_redis
    - QUEUE_BULL_REDIS_PORT=6379
    - QUEUE_BULL_REDIS_DB=1
    - WEBHOOK_URL=https://{{ webhook_domain }}/
    - N8N_PROTOCOL=https
  deploy:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n_webhook.rule=(Host(`{{ webhook_domain }}`) && PathPrefix(`/webhook`))"
      - "traefik.http.routers.n8n_webhook.entrypoints=websecure"
      - "traefik.http.routers.n8n_webhook.priority=1"
      - "traefik.http.routers.n8n_webhook.tls.certresolver=letsencryptresolver"
      - "traefik.http.routers.n8n_webhook.service=n8n_webhook"
      - "traefik.http.services.n8n_webhook.loadbalancer.server.port=5678"
      - "traefik.http.services.n8n_webhook.loadbalancer.passHostHeader=1"
```

#### 3. N8N Worker (Processamento Background)
```yaml
n8n_worker:
  image: n8nio/n8n:latest
  command: worker --concurrency=10
  environment:
    - DB_TYPE=postgresdb
    - DB_POSTGRESDB_DATABASE=n8n_queue
    - DB_POSTGRESDB_HOST=postgres
    - DB_POSTGRESDB_PORT=5432
    - DB_POSTGRESDB_USER=postgres
    - DB_POSTGRESDB_PASSWORD={{ vault.postgres_password }}
    - EXECUTIONS_MODE=queue
    - QUEUE_BULL_REDIS_HOST=n8n_redis
    - QUEUE_BULL_REDIS_PORT=6379
    - QUEUE_BULL_REDIS_DB=1
    - WEBHOOK_URL=https://{{ webhook_domain }}/
    - N8N_PROTOCOL=https
  # SEM labels - worker é backend
```

#### 4. N8N Redis (Cache Dedicado)
```yaml
n8n_redis:
  image: redis:latest
  command: redis-server --appendonly yes
  volumes:
    - n8n_redis:/data
```

---

## 🧪 Estratégia de Testes TDD

### 1. Teste Unitário (PRIORITY: HIGH)
**Arquivo**: `tests/unit/test_app_registry.py`

**Teste já existe**: `test_generate_compose_with_template_and_labels()` ✅

**O que valida**:
- ✅ 3 serviços N8N (editor, webhook, worker)
- ✅ Labels dentro de `deploy.labels`
- ✅ Substituição de variáveis (`{{ domain }}`, `{{ vault.postgres_password }}`)
- ✅ Commands corretos (start, webhook, worker --concurrency=10)

**Status**: Teste passa com compose_template correto

### 2. Teste de Integração (NEW - TO CREATE)
**Arquivo**: `tests/integration/test_n8n_deployment.py`

```python
async def test_n8n_deployment_generates_correct_stack():
    """
    Integration test: Validate N8N stack has 3 services with Traefik labels
    """
    # 1. Load n8n.yaml
    registry = AppRegistry()
    registry.load_definition("apps/definitions/applications/n8n.yaml")

    # 2. Generate compose
    config = {
        "postgres_password": "test123",
        "domain": "edt.lab.livchat.ai",
        "webhook_domain": "whk.lab.livchat.ai"
    }
    compose = registry.generate_compose("n8n", config)

    # 3. Parse and validate
    compose_data = yaml.safe_load(compose)

    # Validate structure
    assert "services" in compose_data
    assert "n8n_editor" in compose_data["services"]
    assert "n8n_webhook" in compose_data["services"]
    assert "n8n_worker" in compose_data["services"]
    assert "n8n_redis" in compose_data["services"]

    # Validate labels
    editor = compose_data["services"]["n8n_editor"]
    assert "deploy" in editor
    assert "labels" in editor["deploy"]

    editor_labels = editor["deploy"]["labels"]
    assert "traefik.enable=true" in editor_labels
    assert "traefik.http.routers.n8n_editor.rule=Host(`edt.lab.livchat.ai`)" in editor_labels
```

### 3. Teste E2E (ENHANCE EXISTING)
**Arquivo**: `tests/e2e/test_complete_e2e_workflow.py`

**Adicionar validação**:
```python
# After N8N deployment
if n8n_result.get('success'):
    # ✅ NEW: Verify stack has correct structure
    stack_id = n8n_result.get('stack_id')

    # Get stack details from Portainer
    stack_info = await portainer.get_stack(stack_id)

    # Validate services
    services = stack_info.get('services', [])
    assert len(services) == 4, f"Expected 4 services, got {len(services)}"

    service_names = [s['name'] for s in services]
    assert 'n8n_editor' in service_names
    assert 'n8n_webhook' in service_names
    assert 'n8n_worker' in service_names
    assert 'n8n_redis' in service_names

    # Validate Traefik labels on editor
    editor_service = next(s for s in services if 'editor' in s['name'])
    labels = editor_service.get('deploy', {}).get('labels', [])
    assert any('traefik.enable=true' in label for label in labels)
```

---

## 📁 Arquivos a Modificar

### 1. `apps/definitions/applications/n8n.yaml` [CRITICAL]
**Ação**: Substituir completamente seguindo SetupOrion

**Estrutura**:
```yaml
name: n8n
category: automation
version: "1.25.1"
description: Workflow automation platform
deploy_method: portainer

dependencies:
  - postgres
  - redis  # Redis global, mas N8N usa o próprio

dns_prefix: edt

additional_dns:
  - prefix: whk
    comment: n8n webhook endpoint

compose_template: |
  version: '3.8'
  services:
    n8n_editor:
      # ... full config from SetupOrion

    n8n_webhook:
      # ... full config from SetupOrion

    n8n_worker:
      # ... full config from SetupOrion

    n8n_redis:
      # ... full config from SetupOrion

  volumes:
    n8n_redis:
      driver: local

  networks:
    livchat_network:
      external: true
      name: livchat_network
```

### 2. `tests/unit/test_app_registry.py` [MINOR ADJUSTMENT]
**Ação**: Verificar se teste existente ainda passa

**O teste já existe e está correto!** Apenas precisamos garantir que o n8n.yaml siga o padrão.

### 3. `tests/integration/test_n8n_deployment.py` [NEW FILE]
**Ação**: Criar novo teste de integração

### 4. `tests/e2e/test_complete_e2e_workflow.py` [ENHANCEMENT]
**Ação**: Adicionar validação de estrutura da stack

### 5. `tests/e2e/test_api_e2e_workflow.py` [ENHANCEMENT]
**Ação**: Adicionar validação de estrutura da stack

---

## ✅ Checklist de Implementação

### Etapa 1: Criar n8n.yaml Correto (SetupOrion Pattern)
- [ ] **Task 1.1**: Backup do n8n.yaml atual
- [ ] **Task 1.2**: Criar novo n8n.yaml com 4 serviços
- [ ] **Task 1.3**: Adicionar labels dentro de `deploy.labels` para editor
- [ ] **Task 1.4**: Adicionar labels dentro de `deploy.labels` para webhook
- [ ] **Task 1.5**: Configurar worker sem labels
- [ ] **Task 1.6**: Adicionar serviço n8n_redis dedicado
- [ ] **Task 1.7**: Configurar volume n8n_redis
- [ ] **Task 1.8**: Configurar variáveis de ambiente corretas
- [ ] **Task 1.9**: Adicionar N8N_ENCRYPTION_KEY

### Etapa 2: Validar com Teste Unitário Existente
- [ ] **Task 2.1**: Executar `pytest tests/unit/test_app_registry.py::TestAppRegistry::test_generate_compose_with_template_and_labels -xvs`
- [ ] **Task 2.2**: Verificar se teste passa
- [ ] **Task 2.3**: Corrigir n8n.yaml se teste falhar

### Etapa 3: Criar Teste de Integração
- [ ] **Task 3.1**: Criar `tests/integration/test_n8n_deployment.py`
- [ ] **Task 3.2**: Implementar teste de validação completa
- [ ] **Task 3.3**: Executar teste de integração
- [ ] **Task 3.4**: Verificar se passa

### Etapa 4: Adicionar Validações nos Testes E2E
- [ ] **Task 4.1**: Adicionar método `get_stack()` no PortainerClient (se não existir)
- [ ] **Task 4.2**: Adicionar validação em `test_complete_e2e_workflow.py`
- [ ] **Task 4.3**: Adicionar validação em `test_api_e2e_workflow.py`
- [ ] **Task 4.4**: Executar ambos testes E2E
- [ ] **Task 4.5**: Verificar se validações passam

### Etapa 5: Correções Adicionais Identificadas
- [ ] **Task 5.1**: Revisar `AppRegistry.generate_compose()` - considerar warning se labels na raiz
- [ ] **Task 5.2**: Adicionar validação no `AppRegistry.validate_app()` para detectar labels fora do template
- [ ] **Task 5.3**: Documentar padrão correto no CLAUDE.md

---

## 📦 Variáveis e Substituições

### Variáveis Necessárias no Config
```python
config = {
    "postgres_password": "...",     # Senha do PostgreSQL
    "domain": "edt.lab.livchat.ai",  # Domínio do editor
    "webhook_domain": "whk.lab.livchat.ai",  # Domínio do webhook
    "encryption_key": "...",         # Chave de criptografia do N8N (gerar)
    "admin_email": "...",           # Email para notificações
}
```

### Geração de encryption_key
```python
# ADICIONAR NO orchestrator.py ou security_utils.py
def generate_n8n_encryption_key():
    """Generate N8N encryption key (32 random characters)"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))
```

---

## 🎯 Critérios de Sucesso

### Must Have
- ✅ N8N stack com 4 serviços (editor, webhook, worker, redis)
- ✅ Labels do Traefik DENTRO do compose_template
- ✅ Teste unitário passa
- ✅ Teste E2E cria stack corretamente

### Should Have
- ✅ Teste de integração específico para N8N
- ✅ Validação nos testes E2E da estrutura da stack
- ✅ Geração automática de N8N_ENCRYPTION_KEY

### Nice to Have
- ⚪ Warning no AppRegistry se labels estiverem fora do template
- ⚪ Documentação do padrão correto no CLAUDE.md

---

## ⚠️ Considerações Importantes

### 1. Redis Dedicado vs Redis Global
**SetupOrion**: Usa Redis dedicado (`n8n_redis`)
**LivChat atual**: Tem Redis global

**Decisão**: Seguir SetupOrion e usar Redis dedicado para isolamento

### 2. Dependency Resolution
**N8N dependencies**: `[postgres, redis]`
**Problema**: Redis listado é o global, mas N8N usa o dedicado

**Solução**: Manter `redis` nas dependencies para garantir que Redis global existe (pode ser usado por outras apps), mas N8N usa o próprio

### 3. certresolver
**SetupOrion**: Usa `letsencryptresolver`
**LivChat**: Usa `letsencrypt`

**Decisão**: Manter `letsencrypt` (nosso padrão atual)

### 4. Priority nas Labels
**SetupOrion**: Usa `priority=1` nas labels
**Impacto**: Define prioridade de roteamento do Traefik

**Decisão**: Incluir `priority=1` seguindo SetupOrion

---

## 📊 Métricas de Sucesso

| Métrica | Valor Esperado |
|---------|----------------|
| **Teste unitário** | ✅ Passa |
| **Teste integração** | ✅ Passa |
| **Teste E2E direto** | ✅ Cria 4 serviços |
| **Teste E2E via API** | ✅ Cria 4 serviços |
| **Labels presentes** | ✅ Em editor e webhook |
| **Acesso via domínio** | ✅ Funciona após deploy |

---

## 🚀 Próximos Passos (Pós-Plan-05)

1. **Plan-06**: Implementar outros apps seguindo o padrão (Chatwoot, etc)
2. **Plan-07**: Sistema de validação automática de stacks
3. **Plan-08**: Dashboard de monitoramento de deployments

---

**Updated**: 2025-01-11
**Status**: 🟡 IN PROGRESS
