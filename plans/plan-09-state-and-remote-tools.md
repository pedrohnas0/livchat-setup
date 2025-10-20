# PLAN-09: State Management & Remote Execution Tools

## 📋 Contexto

**Referência**: CLAUDE.md Seção 8.2 (MCP Tools), Seção 4.1 (Storage Manager)
**Status Atual**: v0.2.6 publicado, hybrid deployment implementado (PLAN-07 + PLAN-08 completos)
**Gap Identificado**:
1. `update-server-dns` é muito específico - deveria ser genérico para todo o `state.json`
2. Nenhuma tool para executar comandos SSH remotos nos servidores deployados

**Decisões Anteriores**:
- `config.yaml` foi DESCONTINUADO - tudo agora vai para `state.json` ou `credentials.vault`
- `manage-config` foi REMOVIDO quando config.yaml foi descontinuado
- DNS config agora vive em `state.json` em `servers[].dns_config`
- Settings (como admin_email) agora vivem em `state.json` em `settings`

---

## 🎯 Objetivo

Criar duas novas tools MCP para:

1. **`manage-state`**: Gerenciamento genérico de `state.json` com dot notation
2. **`remote-bash`**: Execução segura de comandos SSH em servidores deployados

**Métricas de Sucesso**:
- Remover `update-server-dns` (substituído por `manage-state`)
- Suportar acesso a qualquer campo do state.json via dot notation
- Executar comandos SSH com timeout configurável
- Integrar com job system para comandos longos

---

## 📊 Escopo Definitivo

### 1. Tool: `manage-state`

**Propósito**: Substituir `update-server-dns` com gerenciamento genérico do state.json

**Schema (Zod)**:
```typescript
export const ManageStateInputSchema = z.object({
  action: z.enum(['get', 'set', 'list', 'delete'])
    .describe('Ação: get (buscar valor), set (definir), list (listar chaves), delete (remover)'),

  path: z.string().optional()
    .describe('Caminho dot notation (ex: "servers.prod.dns_config.zone_name", "settings.admin_email")'),

  value: z.any().optional()
    .describe('Valor para action=set (pode ser string, number, object, array)'),
});
```

**Exemplos de Uso**:
```typescript
// Listar todos os servidores
manage_state(action="list", path="servers")
// Output: ["n8n-production", "lab-server"]

// Obter DNS config de um servidor
manage_state(action="get", path="servers.n8n-production.dns_config")
// Output: { "zone_name": "livchat.ai", "subdomain": "lab" }

// Atualizar zone_name
manage_state(action="set", path="servers.prod.dns_config.zone_name", value="newdomain.com")

// Adicionar nova configuração em settings
manage_state(action="set", path="settings.default_timezone", value="UTC")

// Deletar subdomain
manage_state(action="delete", path="servers.prod.dns_config.subdomain")
```

**Backend API Endpoint**:
```python
# Nova route: /api/state
@router.get("/api/state")
async def get_state(path: Optional[str] = None)
# Retorna: state completo ou valor específico via dot notation

@router.put("/api/state")
async def set_state(path: str, value: Any)
# Define valor em path específico

@router.delete("/api/state")
async def delete_state(path: str)
# Remove chave em path específico
```

**Implementação Python**:
```python
# storage.py - StateStore class
def get_by_path(self, path: str) -> Any:
    """
    Get value from state using dot notation

    Examples:
        get_by_path("servers.prod.ip") -> "1.2.3.4"
        get_by_path("servers") -> {...all servers...}
    """
    parts = path.split('.')
    current = self._state

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(f"Path not found: {path}")

    return current

def set_by_path(self, path: str, value: Any) -> None:
    """Set value in state using dot notation"""
    parts = path.split('.')
    current = self._state

    # Navigate to parent
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    # Set final value
    current[parts[-1]] = value
    self.save()

def delete_by_path(self, path: str) -> None:
    """Delete key from state using dot notation"""
    parts = path.split('.')
    current = self._state

    # Navigate to parent
    for part in parts[:-1]:
        current = current[part]

    # Delete final key
    del current[parts[-1]]
    self.save()

def list_keys_at_path(self, path: Optional[str] = None) -> List[str]:
    """List keys at specific path"""
    if path:
        current = self.get_by_path(path)
    else:
        current = self._state

    if isinstance(current, dict):
        return list(current.keys())
    else:
        return []
```

---

### 2. Tool: `remote-bash`

**Propósito**: Executar comandos SSH em servidores deployados de forma segura

**Decisões de Design**:

1. **Timeout Strategy** (baseado em pesquisa):
   - **Default**: 30 segundos (balanceado entre quick commands e safety)
   - **Quick commands**: 5-10s (ls, pwd, cat)
   - **Medium commands**: 30-60s (apt update, docker ps, systemctl status)
   - **Long commands**: Usar `use_job=true` para job system (120s+)

2. **Job Integration**:
   - Comandos com `timeout > 60s` OU `use_job=true` → job system
   - Comandos quick (< 60s) → execução síncrona
   - Job permite monitorar via `get-job-status`

3. **Security**:
   - Comando blacklist (rm -rf /, dd if=/dev/zero, etc)
   - Output truncation (max 10KB)
   - Não permitir input interativo
   - Rate limiting (max 10 commands/minute por servidor)

**Schema (Zod)**:
```typescript
export const RemoteBashInputSchema = z.object({
  server_name: z.string()
    .describe('Nome do servidor onde executar o comando'),

  command: z.string()
    .min(1)
    .max(1000)  // Previne comandos absurdamente longos
    .describe('Comando bash a executar (ex: "docker ps -a", "systemctl status traefik")'),

  timeout: z.number()
    .min(5)
    .max(300)  // 5 minutos max
    .default(30)
    .describe('Timeout em segundos (padrão: 30s, máx: 300s)'),

  use_job: z.boolean()
    .default(false)
    .describe('Executar via job system para comandos longos (permite monitoring via get-job-status)'),

  working_directory: z.string().optional()
    .describe('Diretório de trabalho (opcional, padrão: /root)'),
});
```

**Exemplos de Uso**:
```typescript
// Quick command (sync)
remote_bash(
  server_name="n8n-production",
  command="docker ps -a",
  timeout=10
)
// Output imediato: lista de containers

// Medium command (sync)
remote_bash(
  server_name="lab-server",
  command="systemctl status traefik",
  timeout=30
)

// Long command (async via job)
remote_bash(
  server_name="prod",
  command="docker system prune -af",
  timeout=120,
  use_job=true
)
// Output: job_id + instruções de get-job-status
```

**Backend API Endpoint**:
```python
# Nova route: /api/servers/{name}/exec
@router.post("/api/servers/{name}/exec")
async def execute_remote_command(
    name: str,
    request: RemoteCommandRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Execute SSH command on remote server

    Returns:
        - Sync (use_job=false): {"output": "...", "exit_code": 0}
        - Async (use_job=true): {"job_id": "xxx"}
    """
    # Validar servidor existe e está ready
    server = orchestrator.storage.state.get_server(name)
    if not server:
        raise HTTPException(404, f"Server {name} not found")

    # Security: blacklist check
    if is_dangerous_command(request.command):
        raise HTTPException(400, "Command rejected by security policy")

    # Se use_job=true OU timeout > 60s, usar job system
    if request.use_job or request.timeout > 60:
        job = await job_manager.create_job(
            job_type="remote_exec",
            params={
                "server_name": name,
                "command": request.command,
                "timeout": request.timeout
            }
        )
        return {"job_id": job.job_id}

    # Execução síncrona
    result = await orchestrator.execute_remote_command(
        server_name=name,
        command=request.command,
        timeout=request.timeout,
        working_dir=request.working_directory
    )

    return {
        "output": result.stdout,
        "error": result.stderr,
        "exit_code": result.exit_code
    }
```

**Implementação no Orchestrator**:
```python
# orchestrator/core.py
async def execute_remote_command(
    self,
    server_name: str,
    command: str,
    timeout: int = 30,
    working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute command on remote server via SSH

    Uses asyncssh for async execution with timeout
    """
    import asyncssh

    # Get server info
    server = self.storage.state.get_server(server_name)
    server_ip = server.get("ip")

    # Get SSH key
    ssh_key_path = self.ssh_manager.keys_dir / server_name
    if not ssh_key_path.exists():
        raise ValueError(f"SSH key not found for {server_name}")

    try:
        # Connect and run command
        async with asyncssh.connect(
            server_ip,
            username='root',
            client_keys=[str(ssh_key_path)],
            known_hosts=None  # Development - accept any host key
        ) as conn:

            # Build command with working directory
            full_command = command
            if working_dir:
                full_command = f"cd {working_dir} && {command}"

            # Run with timeout
            result = await asyncio.wait_for(
                conn.run(full_command, check=False),  # check=False para não raise em exit != 0
                timeout=timeout
            )

            # Truncate output if too large (max 10KB)
            stdout = result.stdout[:10240] if result.stdout else ""
            stderr = result.stderr[:10240] if result.stderr else ""

            if len(result.stdout) > 10240:
                stdout += "\n[OUTPUT TRUNCATED - exceeds 10KB]"

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.exit_status,
                "success": result.exit_status == 0
            }

    except asyncio.TimeoutError:
        raise TimeoutError(f"Command timed out after {timeout}s")
    except Exception as e:
        logger.error(f"SSH command failed: {e}", exc_info=True)
        raise
```

**Security Blacklist**:
```python
# security/command_validator.py
DANGEROUS_PATTERNS = [
    r'rm\s+-rf\s+/',          # rm -rf /
    r'dd\s+if=/dev/zero',     # disk wipe
    r'mkfs\.',                # format filesystem
    r':\(\)\{\s*:\|:&\s*\};:', # fork bomb
    r'wget.*\|\s*sh',         # download and execute
    r'curl.*\|\s*bash',       # download and execute
]

def is_dangerous_command(command: str) -> bool:
    """Check if command matches dangerous patterns"""
    import re
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False
```

---

## 🧪 Estratégia de Testes TDD

### Unit Tests

```python
# tests/unit/test_state_manager.py
def test_get_by_path():
    """Test dot notation path access"""
    state = StateStore(tmp_path)
    state._state = {
        "servers": {
            "prod": {
                "ip": "1.2.3.4",
                "dns_config": {"zone_name": "example.com"}
            }
        }
    }

    assert state.get_by_path("servers.prod.ip") == "1.2.3.4"
    assert state.get_by_path("servers.prod.dns_config.zone_name") == "example.com"

    with pytest.raises(KeyError):
        state.get_by_path("servers.nonexistent")

def test_set_by_path():
    """Test setting values via dot notation"""
    state = StateStore(tmp_path)
    state._state = {"servers": {}}

    state.set_by_path("servers.prod.ip", "1.2.3.4")
    assert state._state["servers"]["prod"]["ip"] == "1.2.3.4"

# tests/unit/test_remote_exec.py
@pytest.mark.asyncio
async def test_execute_remote_command_success(mock_ssh):
    """Test successful command execution"""
    orchestrator = Orchestrator()
    orchestrator.ssh_manager = mock_ssh

    # Mock asyncssh connection
    mock_result = MagicMock()
    mock_result.stdout = "container1\ncontainer2"
    mock_result.stderr = ""
    mock_result.exit_status = 0

    with patch('asyncssh.connect') as mock_connect:
        mock_connect.return_value.__aenter__.return_value.run.return_value = mock_result

        result = await orchestrator.execute_remote_command(
            server_name="test-server",
            command="docker ps",
            timeout=10
        )

        assert result["success"] is True
        assert "container1" in result["stdout"]
        assert result["exit_code"] == 0

@pytest.mark.asyncio
async def test_execute_remote_command_timeout():
    """Test command timeout"""
    orchestrator = Orchestrator()

    with patch('asyncssh.connect') as mock_connect:
        # Simulate long-running command
        async def long_run(*args, **kwargs):
            await asyncio.sleep(100)

        mock_connect.return_value.__aenter__.return_value.run = long_run

        with pytest.raises(TimeoutError):
            await orchestrator.execute_remote_command(
                server_name="test",
                command="sleep 100",
                timeout=1
            )

def test_dangerous_command_detection():
    """Test security blacklist"""
    assert is_dangerous_command("rm -rf /") is True
    assert is_dangerous_command("dd if=/dev/zero of=/dev/sda") is True
    assert is_dangerous_command("docker ps") is False
    assert is_dangerous_command("ls -la") is False
```

### Integration Tests

```python
# tests/integration/test_state_api.py
def test_state_get_endpoint(client):
    """Test GET /api/state endpoint"""
    response = client.get("/api/state?path=servers.prod.ip")
    assert response.status_code == 200
    assert "value" in response.json()

def test_state_set_endpoint(client):
    """Test PUT /api/state endpoint"""
    response = client.put(
        "/api/state",
        json={"path": "servers.prod.ip", "value": "1.2.3.4"}
    )
    assert response.status_code == 200

# tests/integration/test_remote_exec_api.py
def test_remote_exec_sync(client):
    """Test sync remote execution"""
    response = client.post(
        "/api/servers/test-server/exec",
        json={
            "command": "echo hello",
            "timeout": 10,
            "use_job": False
        }
    )
    assert response.status_code == 200
    assert "output" in response.json()

def test_remote_exec_async_job(client):
    """Test async execution via job"""
    response = client.post(
        "/api/servers/test-server/exec",
        json={
            "command": "sleep 30",
            "timeout": 60,
            "use_job": True
        }
    )
    assert response.status_code == 202
    assert "job_id" in response.json()
```

### E2E Tests

```python
# tests/e2e/test_remote_execution.py
@pytest.mark.e2e
async def test_real_remote_command():
    """Test real SSH command execution on deployed server"""
    if not os.getenv("LIVCHAT_E2E_REAL"):
        pytest.skip("E2E tests disabled")

    # Assumindo servidor já criado e setupado
    result = await orchestrator.execute_remote_command(
        server_name="e2e-test-server",
        command="docker ps -a",
        timeout=30
    )

    assert result["success"] is True
    assert result["exit_code"] == 0
```

---

## 📁 Estrutura de Arquivos

```
src/
├── storage.py                    # [MODIFY] Add dot notation methods
├── security/                     # [NEW]
│   ├── __init__.py
│   └── command_validator.py     # [NEW] Security blacklist
├── orchestrator/
│   └── core.py                   # [MODIFY] Add execute_remote_command()
├── api/
│   ├── models/
│   │   ├── state.py              # [NEW] State management models
│   │   └── remote_exec.py        # [NEW] Remote exec models
│   └── routes/
│       ├── state.py              # [NEW] State management endpoints
│       ├── servers.py            # [MODIFY] Add /exec endpoint
│       └── __init__.py           # [MODIFY] Register new routes

mcp-server/src/
├── tools/
│   ├── manage-state.ts           # [NEW] manage-state tool
│   ├── remote-bash.ts            # [NEW] remote-bash tool
│   └── index.ts                  # [MODIFY] Export new tools
└── index.ts                      # [MODIFY] Register new tools, REMOVE update-server-dns

tests/
├── unit/
│   ├── test_state_manager.py    # [NEW] Dot notation tests
│   ├── test_remote_exec.py      # [NEW] Remote command tests
│   └── security/
│       └── test_command_validator.py  # [NEW] Security tests
├── integration/
│   ├── test_state_api.py        # [NEW]
│   └── test_remote_exec_api.py  # [NEW]
└── e2e/
    └── test_remote_execution.py # [NEW]
```

---

## ✅ Checklist de Implementação

### Etapa 1: State Management Backend
- [ ] **Task 1**: Adicionar métodos dot notation em StateStore
  - `get_by_path(path: str)`
  - `set_by_path(path: str, value: Any)`
  - `delete_by_path(path: str)`
  - `list_keys_at_path(path: Optional[str])`
- [ ] **Task 2**: Criar models Pydantic em `api/models/state.py`
  - `StateGetRequest`
  - `StateSetRequest`
  - `StateDeleteRequest`
  - `StateResponse`
- [ ] **Task 3**: Criar routes em `api/routes/state.py`
  - `GET /api/state`
  - `PUT /api/state`
  - `DELETE /api/state`
- [ ] **Task 4**: Testes unitários para dot notation
- [ ] **Task 5**: Testes de integração para state API

### Etapa 2: Remote Execution Backend
- [ ] **Task 1**: Criar security blacklist em `security/command_validator.py`
  - Implementar `is_dangerous_command()`
  - Definir `DANGEROUS_PATTERNS`
- [ ] **Task 2**: Adicionar `execute_remote_command()` no Orchestrator
  - Integração com asyncssh
  - Timeout handling
  - Output truncation
- [ ] **Task 3**: Criar models em `api/models/remote_exec.py`
  - `RemoteCommandRequest`
  - `RemoteCommandResponse`
  - `RemoteCommandJobResponse`
- [ ] **Task 4**: Adicionar endpoint `/api/servers/{name}/exec` em routes/servers.py
  - Sync execution path
  - Async (job) execution path
  - Security validation
- [ ] **Task 5**: Testes unitários para remote exec
- [ ] **Task 6**: Testes de integração para exec API

### Etapa 3: MCP Tools
- [ ] **Task 1**: Criar `mcp-server/src/tools/manage-state.ts`
  - Schema com Zod
  - Tool handler class
  - Error formatting
  - AI-friendly output
- [ ] **Task 2**: Criar `mcp-server/src/tools/remote-bash.ts`
  - Schema com Zod
  - Tool handler class
  - Timeout support
  - Job integration
- [ ] **Task 3**: Registrar tools em `mcp-server/src/index.ts`
  - Adicionar manage-state
  - Adicionar remote-bash
  - **REMOVER update-server-dns**
- [ ] **Task 4**: Update exports em `tools/index.ts`

### Etapa 4: Job System Integration
- [ ] **Task 1**: Adicionar job executor para `remote_exec` type
- [ ] **Task 2**: Implementar log streaming para comandos SSH
- [ ] **Task 3**: Testes de integração com job system

### Etapa 5: Documentation & Testing
- [ ] **Task 1**: Atualizar CLAUDE.md com novas tools
- [ ] **Task 2**: E2E test para remote execution
- [ ] **Task 3**: Update README com exemplos
- [ ] **Task 4**: Verificar cobertura de testes (target: 80%+)

### Etapa 6: Deployment
- [ ] **Task 1**: Build do MCP server: `cd mcp-server && npm run build`
- [ ] **Task 2**: Bump version: 0.2.6 → 0.3.0
- [ ] **Task 3**: Publicar no NPM
- [ ] **Task 4**: Git tag: `v0.3.0`

---

## 📦 Dependências Novas

```json
// mcp-server/package.json - NENHUMA DEPENDÊNCIA NOVA
// Já temos: zod, @modelcontextprotocol/sdk

// No backend Python - NOVA:
{
  "asyncssh": "^2.14.0"  // Para execução SSH assíncrona
}
```

```bash
# Adicionar ao requirements.txt
pip install asyncssh==2.14.0
```

---

## 🎮 MCP Commands (Alterações)

**Tools Removidas**:
- ❌ `update-server-dns` - Substituída por `manage-state`

**Tools Novas**:
- ✅ `manage-state` - Gerenciamento genérico de state.json
- ✅ `remote-bash` - Execução SSH remota

**Total de Tools**: 13 → 14 tools
1. manage-secrets
2. get-provider-info
3. create-server
4. list-servers
5. ~~update-server-dns~~ → **manage-state** (NOVO)
6. setup-server
7. delete-server
8. list-apps
9. deploy-app
10. undeploy-app
11. list-deployed-apps
12. get-job-status
13. list-jobs
14. **remote-bash** (NOVO)

---

## 🎯 Critérios de Sucesso

### Funcionais
- [ ] `manage-state` consegue acessar qualquer campo do state.json via dot notation
- [ ] `manage-state` consegue criar/atualizar/deletar valores
- [ ] `remote-bash` executa comandos SSH com sucesso
- [ ] `remote-bash` respeita timeouts configurados
- [ ] Comandos perigosos são bloqueados pelo security validator
- [ ] Output é truncado em 10KB para prevenir overflow
- [ ] Comandos longos podem usar job system para monitoring

### Não-Funcionais
- [ ] Comandos quick (< 30s) retornam em < 2s
- [ ] Timeout detection funciona corretamente
- [ ] Cobertura de testes > 80% para componentes críticos
- [ ] Documentação completa com exemplos
- [ ] Zero regressões em E2E tests existentes

---

## 📊 Métricas

### Performance Targets
- **State access**: < 50ms para get_by_path()
- **Remote command (quick)**: < 3s total (1s SSH connect + 1s command + 1s cleanup)
- **Remote command (long)**: Job creation < 100ms, monitoring via get-job-status

### Security
- **Blacklist coverage**: 100% dos padrões perigosos conhecidos
- **False positives**: < 1% (comandos legítimos bloqueados)
- **Output truncation**: Hard limit 10KB

### Testing
- **Unit test coverage**: > 85%
- **Integration test coverage**: > 70%
- **E2E test**: 1 cenário completo de remote execution

---

## ⚠️ Considerações Importantes

### 1. Backward Compatibility
**BREAKING CHANGE**: `update-server-dns` será REMOVIDA

**Migration Path** para usuários:
```typescript
// ANTES (deprecated):
update_server_dns(
  server_name="prod",
  zone_name="example.com",
  subdomain="lab"
)

// DEPOIS (novo):
manage_state(
  action="set",
  path="servers.prod.dns_config.zone_name",
  value="example.com"
)

manage_state(
  action="set",
  path="servers.prod.dns_config.subdomain",
  value="lab"
)
```

### 2. Security Considerations

**asyncssh known_hosts**:
- Development: `known_hosts=None` (aceita qualquer host)
- Production: Implementar verificação de host keys

**Command Injection Prevention**:
- NO shell expansion de variáveis
- NO command chaining via `;` ou `&&` no user input
- Blacklist é primeira linha de defesa, não única

**Rate Limiting**:
- Implementar em fase futura
- Inicial: confiar em timeout protection

### 3. Timeout Strategy Rationale

**Por que 30s default?**
- Pesquisa mostrou Airflow usa 10s (muito curto, causa falhas)
- 60s resolve problemas comuns
- 30s é balanceado: suficiente para apt update, não muito longo para travamentos
- Job system disponível para > 60s

**Por que max 300s (5min)?**
- Comandos > 5min devem usar job system
- Previne hanging connections
- Alinhado com best practices de SSH timeout

### 4. Job System Integration

**Quando usar jobs**:
- `use_job=true` explícito
- OU `timeout > 60s` automático

**Benefits**:
- Monitoring via get-job-status
- Não bloqueia MCP server
- Log streaming

### 5. Output Handling

**Por que truncar em 10KB?**
- Previne memory issues
- MCP tem limites de message size
- 10KB é suficiente para debug (~200 linhas de 50 chars)
- Comandos com output gigante devem redirecionar para arquivo

**Alternativa futura**: Streaming incremental via WebSocket

---

## 🚀 Próximos Passos (Pós-PLAN-09)

### Possíveis PLAN-10 Topics:
1. **Web Dashboard**: Interface gráfica para monitoring
2. **File Upload/Download**: Transferir files via SSH (scp/sftp)
3. **Log Streaming**: WebSocket para output em tempo real
4. **Advanced Security**: Host key verification, audit log
5. **Multi-Provider Expansion**: DigitalOcean, AWS Lightsail

---

## 📊 Status

**Status**: 🔵 READY TO START

**Next Action**: Começar Etapa 1 - State Management Backend

**Dependencies**: Nenhuma - PLAN-07 e PLAN-08 completos

**Estimated Effort**:
- Backend: 3 etapas (~6-8 horas)
- MCP Tools: 1 etapa (~2 horas)
- Testing: 2 etapas (~4 horas)
- Total: ~12-14 horas de desenvolvimento

**Version Target**: v0.3.0

---

**Document Version**: 1.0.0
**Created**: 2025-10-20
**Author**: Claude AI + Pedro (LivChat Team)
**Status**: 🔵 READY FOR APPROVAL
