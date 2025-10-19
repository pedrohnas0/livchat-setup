# Test Failures Analysis - Fase 0.3

**Data:** 2025-10-19
**Status:** 52 falhas, 356 passando (87% sucesso)
**Tempo de execução:** 36.43s

---

## 📊 Sumário

```
Total de testes: 408
✅ Passando: 356 (87%)
❌ Falhando: 52 (13%)
⚠️ Warnings: 287
```

---

## 🔍 Categorização de Erros

### 1. **Async/Await Issues** (18 falhas) - CRÍTICO
**Problema:** Testes não estão usando `await` em métodos assíncronos

**Arquivos afetados:**
- `test_job_manager.py` - 13 falhas
  - `AttributeError: 'coroutine' object has no attribute 'job_type'`
  - `AttributeError: 'coroutine' object has no attribute 'job_id'`
  - `assert <coroutine object JobManager.cancel_job...> is False`

- `test_job_executors.py` - 3 falhas
  - `assert <coroutine object AsyncMockMixin._execute_mock_call...> is True`

- `test_job_executor.py` - 1 falha
  - `AttributeError: 'coroutine' object has no attribute 'status'`

**Solução:** Adicionar `await` antes das chamadas de métodos async

---

### 2. **DNS v0.2.0 Breaking Changes** (14 falhas) - ESPERADO
**Problema:** Testes não atualizados para arquitetura DNS-first

**Arquivos afetados:**
- `test_job_executors.py` - 2 falhas
  - `ValueError: zone_name is required for server setup (v0.2.0)`

- `test_app_deployer.py` - 6 falhas
  - `assert False is True` (DNS validation)
  - `'DNS not configured on server. DNS is required for all app deployments.'`

- `test_routes_servers.py` - 6 falhas
  - `KeyError: 'dns_info'` (campo renomeado para dns_config)
  - `assert 422 == 202` (validação de schema)

**Solução:** Atualizar testes para incluir `zone_name` obrigatório

---

### 3. **Provider API Tests** (5 falhas) - MOCK ISSUE
**Problema:** Mocks de provider não configurados corretamente

**Arquivos afetados:**
- `test_routes_providers.py` - 5 falhas
  - `assert 400 == 200` (esperava sucesso, recebeu bad request)
  - `assert 400 == 500` (esperava erro, recebeu bad request)

**Solução:** Revisar mocks do HetznerProvider

---

### 4. **Path/File Errors** (2 falhas) - BUG
**Problema:** Caminhos incorretos

**Arquivos afetados:**
- `test_infrastructure_executors.py` - 2 falhas
  - `FileNotFoundError: '/home/pedro/dev/sandbox/LivChatSetup/tests/src/server_setup.py'`
  - `FileNotFoundError: '/home/pedro/dev/sandbox/LivChatSetup/tests/unit/e2e/test_complete_e2e_workflow.py'`

**Solução:** Corrigir caminhos hardcoded nos testes

---

### 5. **Schema/API Changes** (8 falhas) - BREAKING CHANGES
**Problema:** Mudanças de schema não refletidas em testes

**Arquivos afetados:**
- `test_routes_servers.py` - 4 falhas
  - `KeyError: 'name'` (campo esperado não presente)
  - `assert 422 == 202` (validação de request body)

- `test_routes_apps.py` - 2 falhas
  - `assert 0 == 1` (deployed apps count)

- `test_cloudflare.py` - 2 falhas
  - `KeyError: 'portainer'`
  - `KeyError: 'deleted'`

**Solução:** Atualizar schemas esperados nos testes

---

### 6. **Domain/DNS Parameter Translation** (3 falhas) - REFACTORING
**Problema:** Migração de `domain` para `dns_domain` incompleta

**Arquivos afetados:**
- `test_infrastructure_executors.py` - 2 falhas
  - `AssertionError: Should not have dns_domain when domain is None`
  - `AssertionError: Config should contain 'dns_domain'`

- `test_server_setup.py` - 2 falhas
  - `AssertionError: assert 3 == 4` (contagem de playbooks)
  - `AssertionError: assert None == 'custom@domain.com'`

**Solução:** Completar migração de parâmetros domain → dns_domain

---

### 7. **Other** (2 falhas)
- `test_app_deployer.py::test_concurrent_deployments` - `assert 0 >= 1`

---

## 🎯 Plano de Correção (Priorização)

### **Alta Prioridade - Fase 1** (18 falhas)
1. ✅ **Async/Await Issues** - Adicionar await em todos os testes async
   - Files: `test_job_manager.py`, `test_job_executors.py`, `test_job_executor.py`
   - Estimativa: 30-45 min

### **Média Prioridade - Fase 2** (14 falhas)
2. 🟡 **DNS v0.2.0 Changes** - Atualizar testes para DNS-first
   - Files: `test_app_deployer.py`, `test_routes_servers.py`, `test_job_executors.py`
   - Estimativa: 1h

### **Média Prioridade - Fase 3** (10 falhas)
3. 🟡 **Schema/API + Provider Mocks**
   - Files: `test_routes_providers.py`, `test_routes_apps.py`, `test_cloudflare.py`
   - Estimativa: 45 min

### **Baixa Prioridade - Fase 4** (10 falhas)
4. 🟢 **Domain Translation + Paths + Others**
   - Files: `test_infrastructure_executors.py`, `test_server_setup.py`
   - Estimativa: 30 min

---

## 📝 Notas

- **Warnings (287):** Principalmente deprecations e coroutines não awaited - verificar após correções
- **Test Performance:** 36.43s está bom (< 3s por teste em média)
- **Estrutura Nova:** Testes foram reorganizados com sucesso em subdiretórios

---

## ✅ Próximos Passos

1. Começar pela Fase 1: Corrigir async/await
2. Rodar testes novamente após cada fase
3. Documentar fixes realizados
4. Quando tudo estiver verde, registrar baseline em PLAN-08
