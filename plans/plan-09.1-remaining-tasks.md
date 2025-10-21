# PLAN-09.1: Remaining Tasks (Job Integration & Cleanup)

## 📋 Contexto

**Parent Plan**: PLAN-09 (State Management & Remote Execution Tools)
**Status Atual**: 85% completo - faltam 3 divergências críticas
**Implementado**:
- ✅ `manage-state` tool (100%)
- ✅ `remote-bash` tool (sync apenas - 70%)
- ✅ Security command validator (100%)
- ✅ Backend APIs e testes (100%)

**DIVERGÊNCIAS identificadas**:
1. ❌ `update-server-dns` NÃO foi removida (deveria ser substituída por `manage-state`)
2. ❌ Job system integration NÃO implementado (comandos longos devem usar jobs)
3. ⚠️ `use_job` parameter ausente (schema incompleto)

---

## 🎯 Objetivo

Completar PLAN-09 implementando:
1. **Remover** `update-server-dns` tool obsoleta
2. **Adicionar** suporte a job system para comandos longos
3. **Implementar** `use_job` parameter

**Métricas de Sucesso**:
- Tools: 15 → 14 (remoção de update-server-dns)
- remote-bash: Sync (< 60s) + Async via jobs (≥ 60s)
- Testes: > 80% coverage mantido

---

## 📊 Escopo Definitivo

### Divergência #1: Remover `update-server-dns`

**Arquivos afetados**:
```
mcp-server/src/
├── index.ts              # MODIFY: Remover linhas 28-29, 74, 130-135
├── tools/
│   ├── servers.ts        # MODIFY: Remover UpdateServerDNSTool class
│   └── index.ts          # MODIFY: Remover export UpdateServerDNSTool
```

**Mudanças**:
```typescript
// index.ts - DELETAR linhas 28-29:
import {
  UpdateServerDNSTool,      // ← REMOVER
  UpdateServerDNSInputSchema, // ← REMOVER
  ...
}

// index.ts - DELETAR linha 74:
updateServerDns: new UpdateServerDNSTool(apiClient), // ← REMOVER

// index.ts - DELETAR linhas 130-135:
server.tool(
  "update-server-dns",   // ← REMOVER TODO BLOCO
  "...",
  UpdateServerDNSInputSchema.shape,
  async (input) => ({ content: [...] })
);

// tools/servers.ts - DELETAR classe completa UpdateServerDNSTool

// tools/index.ts - DELETAR:
export { UpdateServerDNSTool, UpdateServerDNSInputSchema } from './servers.js';
```

**Justificativa**: `manage-state` substituiu completamente a funcionalidade:
```typescript
// ANTES (obsoleto):
update_server_dns(server_name="prod", zone_name="example.com", subdomain="lab")

// DEPOIS (novo):
manage_state(action="set", path="servers.prod.dns_config.zone_name", value="example.com")
manage_state(action="set", path="servers.prod.dns_config.subdomain", value="lab")
```

---

### Divergência #2 & #3: Job System Integration

**Fluxo de Decisão** (PLAN-09 linhas 258-266):
```python
if request.use_job == True OR request.timeout > 60:
    # Async via job system
    job = await job_manager.create_job(job_type="remote_exec", params={...})
    return {"job_id": job.job_id}  # 202 Accepted
else:
    # Sync execution (current implementation)
    result = await orchestrator.execute_remote_command(...)
    return result  # 200 OK
```

**Arquivos afetados**:
```
mcp-server/src/tools/
└── remote-bash.ts         # MODIFY: Add use_job parameter

src/
├── api/
│   ├── models/
│   │   └── remote_exec.py  # MODIFY: Add use_job field
│   └── routes/
│       └── servers.py      # MODIFY: Add job decision logic
└── job_executors/
    ├── remote_exec_executor.py  # NEW: Remote exec job executor
    └── __init__.py              # MODIFY: Register executor
```

**Implementação**:

#### 1. Frontend (TypeScript)
```typescript
// mcp-server/src/tools/remote-bash.ts - MODIFY schema
export const RemoteBashInputSchema = z.object({
  server_name: z.string().describe('Name of the server to execute command on'),
  command: z.string().min(1).describe('Shell command to execute'),
  timeout: z.number().int().min(1).max(300).optional().default(30)
    .describe('Command timeout in seconds (default: 30, max: 300)'),
  working_dir: z.string().optional()
    .describe('Optional working directory'),
  use_job: z.boolean().optional().default(false)  // ← NEW
    .describe('Execute via job system for long-running commands (allows monitoring via get-job-status)'),
});
```

#### 2. Backend Models
```python
# src/api/models/remote_exec.py - MODIFY
class RemoteExecRequest(BaseModel):
    command: str = Field(...)
    timeout: int = Field(default=30, ge=1, le=300)
    working_dir: Optional[str] = Field(default=None)
    use_job: bool = Field(default=False)  # ← NEW
        .describe("Execute via job system (async) instead of sync")
```

#### 3. Backend Route
```python
# src/api/routes/servers.py - MODIFY execute_remote_command()
@router.post("/{name}/exec")
async def execute_remote_command(
    name: str,
    request: RemoteExecRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    job_manager: JobManager = Depends(get_job_manager)  # ← ADD dependency
):
    """
    Execute command on remote server

    Returns:
        - Sync (use_job=false && timeout <= 60): RemoteExecResponse (200 OK)
        - Async (use_job=true || timeout > 60): JobResponse (202 Accepted)
    """
    # Check server exists
    server_data = orchestrator.storage.state.get_server(name)
    if not server_data:
        raise HTTPException(404, f"Server {name} not found")

    # ===== NEW LOGIC: Job decision =====
    should_use_job = request.use_job or request.timeout > 60

    if should_use_job:
        # Async execution via job system
        job = await job_manager.create_job(
            job_type="remote_exec",
            params={
                "server_name": name,
                "command": request.command,
                "timeout": request.timeout,
                "working_dir": request.working_dir
            }
        )

        logger.info(f"Created remote_exec job {job.job_id} for {name}")

        return JSONResponse(
            status_code=202,  # Accepted
            content={
                "job_id": job.job_id,
                "message": f"Command execution started via job system",
                "server_name": name,
                "command": request.command[:50] + "..." if len(request.command) > 50 else request.command
            }
        )

    # ===== EXISTING LOGIC: Sync execution =====
    try:
        result = await orchestrator.execute_remote_command(
            server_name=name,
            command=request.command,
            timeout=request.timeout,
            working_dir=request.working_dir
        )

        # ... existing response logic ...
    except ValueError as e:
        # ... existing error handling ...
```

#### 4. Job Executor
```python
# src/job_executors/remote_exec_executor.py - NEW FILE
"""
Remote Execution Executor

Executes SSH commands on remote servers as async jobs.
Used for long-running commands (timeout > 60s) or when use_job=true.
"""

import logging
from typing import Any, Dict

from src.job_manager import Job
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def execute_remote_exec(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute remote SSH command job

    Args:
        job: Job instance with params (server_name, command, timeout, working_dir)
        orchestrator: Orchestrator instance

    Returns:
        Command execution result with stdout, stderr, exit_code
    """
    logger.info(f"Executing remote_exec job {job.job_id}")

    # Extract params
    params = job.params
    server_name = params.get("server_name")
    command = params.get("command")
    timeout = params.get("timeout", 30)
    working_dir = params.get("working_dir")

    # Step 1: Connecting to server
    job.advance_step(1, 2, f"Connecting to {server_name} via SSH")

    # Execute command
    result = await orchestrator.execute_remote_command(
        server_name=server_name,
        command=command,
        timeout=timeout,
        working_dir=working_dir
    )

    # Step 2: Command completed
    status_msg = "succeeded" if result["success"] else f"failed (exit {result['exit_code']})"
    job.advance_step(2, 2, f"Command {status_msg}")

    logger.info(f"Remote exec job {job.job_id} completed: exit_code={result['exit_code']}")

    return result
```

#### 5. Register Executor
```python
# src/job_executors/__init__.py - MODIFY
from .remote_exec_executor import execute_remote_exec  # ← ADD

EXECUTOR_REGISTRY: Dict[str, Callable[[Any, Any], Awaitable[Any]]] = {
    # ... existing executors ...
    "remote_exec": execute_remote_exec,  # ← ADD
}
```

---

## 🧪 Estratégia de Testes TDD

### Test #1: Remoção de update-server-dns

```bash
# Verificar que update-server-dns foi removida
cd mcp-server
npm run build
# Deve compilar sem erros

# Verificar que manage-state funciona para DNS
# (já validado em testes anteriores)
```

### Test #2: use_job parameter (Unit Test)

```python
# tests/unit/api/test_routes_servers.py - NEW TEST
@pytest.mark.asyncio
async def test_remote_exec_with_use_job_creates_job(client, mock_job_manager):
    """Should create job when use_job=true"""
    response = await client.post(
        "/api/servers/test-server/exec",
        json={
            "command": "docker ps",
            "timeout": 30,
            "use_job": True  # ← Force job creation
        }
    )

    assert response.status_code == 202  # Accepted
    assert "job_id" in response.json()
    assert mock_job_manager.create_job.called

    # Verify job params
    call_args = mock_job_manager.create_job.call_args
    assert call_args[1]["job_type"] == "remote_exec"
    assert call_args[1]["params"]["command"] == "docker ps"
```

### Test #3: Auto job creation for long timeout

```python
# tests/unit/api/test_routes_servers.py - NEW TEST
@pytest.mark.asyncio
async def test_remote_exec_auto_job_for_long_timeout(client, mock_job_manager):
    """Should auto-create job when timeout > 60s"""
    response = await client.post(
        "/api/servers/test-server/exec",
        json={
            "command": "apt-get update && apt-get upgrade -y",
            "timeout": 120,  # > 60s → auto job
            "use_job": False  # Even with false, should use job
        }
    )

    assert response.status_code == 202
    assert "job_id" in response.json()
```

### Test #4: Job Executor

```python
# tests/unit/job_executors/test_remote_exec_executor.py - NEW FILE
@pytest.mark.asyncio
async def test_execute_remote_exec_success():
    """Should execute command and return result"""
    job = Mock()
    job.job_id = "test-job-123"
    job.params = {
        "server_name": "test-server",
        "command": "echo hello",
        "timeout": 30
    }
    job.advance_step = Mock()

    orchestrator = Mock()
    orchestrator.execute_remote_command = AsyncMock(return_value={
        "stdout": "hello\n",
        "stderr": "",
        "exit_code": 0,
        "success": True
    })

    from src.job_executors.remote_exec_executor import execute_remote_exec
    result = await execute_remote_exec(job, orchestrator)

    assert result["success"] is True
    assert "hello" in result["stdout"]
    assert job.advance_step.call_count == 2  # 2 steps
```

### Test #5: E2E Test Update

```typescript
// mcp-server/tests/e2e/test_mcp_e2e_workflow.ts - MODIFY
// Adicionar teste de remote-bash com use_job=true

console.log('\n💻 [NEW TOOL] Testing remote-bash with job system...');

// Test 1: Sync command (quick)
const syncResult = await remoteBashTool.execute({
  server_name: serverName,
  command: 'uname -a',
  timeout: 10,
  use_job: false
});
assert(syncResult.includes('Linux'), 'Sync command should work');

// Test 2: Async command via job
const asyncResult = await remoteBashTool.execute({
  server_name: serverName,
  command: 'docker stats --no-stream',
  timeout: 120,
  use_job: true  // ← Force job
});
assert(asyncResult.includes('job_id'), 'Should create job for async command');

// Extract job_id and monitor
const jobIdMatch = asyncResult.match(/job_id:\s*(\S+)/);
const jobId = jobIdMatch[1];

// Monitor job via get-job-status
let jobComplete = false;
for (let i = 0; i < 30; i++) {
  const status = await getJobStatusTool.execute({ job_id: jobId });
  if (status.includes('completed')) {
    jobComplete = true;
    break;
  }
  await sleep(2000);
}

assert(jobComplete, 'Job should complete successfully');
```

---

## ✅ Checklist de Implementação

### Etapa 1: Remover update-server-dns (TDD)
- [ ] **Task 1**: Criar teste que valida que update-server-dns não existe mais
- [ ] **Task 2**: Remover imports de UpdateServerDNSTool em index.ts
- [ ] **Task 3**: Remover instanciação em tools object (linha 74)
- [ ] **Task 4**: Remover registration server.tool() (linhas 130-135)
- [ ] **Task 5**: Deletar UpdateServerDNSTool class de servers.ts
- [ ] **Task 6**: Remover export de index.ts
- [ ] **Task 7**: Build TypeScript: `npm run build` (deve passar)
- [ ] **Task 8**: Validar que manage-state cobre todos os casos de uso

### Etapa 2: Add use_job Parameter (TDD)
- [ ] **Task 1**: RED - Criar teste que falha (test_remote_exec_with_use_job_creates_job)
- [ ] **Task 2**: GREEN - Adicionar use_job ao RemoteBashInputSchema (TypeScript)
- [ ] **Task 3**: GREEN - Adicionar use_job ao RemoteExecRequest (Python)
- [ ] **Task 4**: GREEN - Build e validar schema
- [ ] **Task 5**: Testes devem passar

### Etapa 3: Job System Integration (TDD)
- [ ] **Task 1**: RED - Criar teste para auto-job quando timeout > 60s
- [ ] **Task 2**: GREEN - Adicionar JobManager dependency ao endpoint
- [ ] **Task 3**: GREEN - Implementar job decision logic (if use_job or timeout > 60)
- [ ] **Task 4**: GREEN - Retornar 202 Accepted com job_id
- [ ] **Task 5**: Testes devem passar

### Etapa 4: Remote Exec Job Executor (TDD)
- [ ] **Task 1**: RED - Criar teste unitário para execute_remote_exec()
- [ ] **Task 2**: GREEN - Criar remote_exec_executor.py
- [ ] **Task 3**: GREEN - Implementar execute_remote_exec() com 2 steps
- [ ] **Task 4**: GREEN - Registrar em EXECUTOR_REGISTRY
- [ ] **Task 5**: Testes devem passar

### Etapa 5: Integration Testing
- [ ] **Task 1**: Testar via curl: comando sync (< 60s)
- [ ] **Task 2**: Testar via curl: comando async (use_job=true)
- [ ] **Task 3**: Testar via curl: comando auto-async (timeout=120)
- [ ] **Task 4**: Monitorar job via get-job-status

### Etapa 6: E2E Testing
- [ ] **Task 1**: Atualizar E2E test com remote-bash job tests
- [ ] **Task 2**: Rodar E2E completo: `npm run test:e2e`
- [ ] **Task 3**: Validar todos os 4 testes remote-bash passam

---

## 📦 Dependências

**Nenhuma dependência nova!**
- asyncssh já instalado ✅
- Job system já implementado ✅
- Tudo está pronto para integração

---

## 🎯 Critérios de Sucesso

### Funcionais
- [ ] `update-server-dns` tool removida completamente
- [ ] `remote-bash` com `use_job=false && timeout <= 60` → execução síncrona (200 OK)
- [ ] `remote-bash` com `use_job=true` → cria job (202 Accepted)
- [ ] `remote-bash` com `timeout > 60` → cria job automaticamente (202 Accepted)
- [ ] Job executor `remote_exec` registrado e funcional
- [ ] Jobs podem ser monitorados via `get-job-status`

### Não-Funcionais
- [ ] Total de tools: 15 → 14 (conforme PLAN-09)
- [ ] Build TypeScript sem erros
- [ ] Testes unitários > 80% coverage
- [ ] E2E test passa completamente
- [ ] Zero regressões em features existentes

---

## 📊 Métricas

### Performance Targets
- **Sync commands (< 60s)**: Resposta < 5s total
- **Async commands (≥ 60s)**: Job creation < 100ms
- **Job monitoring**: get-job-status < 50ms

### Testing
- **New unit tests**: 4 testes (2 para use_job, 1 para auto-job, 1 para executor)
- **Modified E2E test**: +3 cenários remote-bash
- **Coverage**: Manter > 80%

---

## ⚠️ Considerações Importantes

### 1. Backward Compatibility

**BREAKING CHANGE**: `update-server-dns` será REMOVIDA

**Migration Path**:
```typescript
// Users precisam migrar de:
update_server_dns(server_name="prod", zone_name="example.com")

// Para:
manage_state(action="set", path="servers.prod.dns_config.zone_name", value="example.com")
```

**Communication**: Adicionar em CHANGELOG.md e documentação.

### 2. Job System Behavior

**Decision Matrix**:
```
┌─────────────┬──────────────┬────────────┐
│   use_job   │   timeout    │   Result   │
├─────────────┼──────────────┼────────────┤
│    false    │    ≤ 60s     │   SYNC     │
│    false    │    > 60s     │   JOB      │
│    true     │   qualquer   │   JOB      │
└─────────────┴──────────────┴────────────┘
```

**Rationale**: Comandos > 60s são long-running e devem usar job system para não bloquear.

### 3. E2E Test Strategy

**Approach**: Usar servidor já criado (e2e-mcp-test) para evitar custo adicional.

**Test scenarios**:
1. Sync: `uname -a` (< 5s)
2. Async with use_job: `docker stats` (force job)
3. Auto-async: `sleep 70` (auto job due timeout)
4. Job monitoring: Acompanhar job até completion

---

## 🚀 Próximos Passos (Pós-PLAN-09.1)

Após completar PLAN-09.1:
1. ✅ **Bump version**: 0.2.6 → 0.3.0
2. ✅ **Update CHANGELOG.md** com breaking changes
3. ✅ **Publicar NPM package**
4. ✅ **Git tag**: `v0.3.0`
5. 🎯 **PLAN-10**: Próxima feature (TBD)

---

## 📊 Status

**Status**: 🔵 READY TO START
**Dependencies**: Nenhuma - implementação anterior completa
**Estimated Effort**: 4-6 horas
**Version Target**: v0.3.0

---

**Document Version**: 1.0.0
**Created**: 2025-10-21
**Author**: Claude AI + Pedro
**Parent Plan**: PLAN-09 State Management & Remote Execution Tools
**Status**: 🔵 READY FOR IMPLEMENTATION
