# PLAN-09.2: Real-Time Streaming Logs for Remote Exec Jobs

## 📋 Contexto

**Referência**: PLAN-09.1 implementou job system para remote-bash, mas com **limitação crítica**:
- ❌ Jobs não mostram logs em tempo real durante execução
- ❌ `execute_remote_command()` usa `conn.run()` que é **bloqueante**
- ❌ Logs aparecem apenas NO FINAL da execução

**Status atual**:
- ✅ PLAN-09.1 completo (job decision logic funcionando)
- ⚠️ Mas sem streaming de output

**Problema identificado**:
```python
# Atual (BLOQUEANTE - sem logs progressivos):
result = await conn.run(command)  # Aguarda até terminar
# Só então retorna stdout/stderr completos
```

**O que precisa ser**:
```python
# Desejado (STREAMING - logs linha por linha):
async with conn.create_process(command) as proc:
    while True:
        line = await proc.stdout.readline()
        logger.info(f"[stdout] {line}")  # ← Capturado por JobLogManager!
```

---

## 🎯 Objetivo

Implementar **streaming real-time de logs** para remote exec jobs:
- ✅ Logs aparecem **linha por linha** durante execução
- ✅ JobLogManager captura automaticamente (já existe!)
- ✅ User monitora progresso com `get-job-status`
- ✅ Suporta comandos de até 300s
- ✅ SSH mantido aberto durante execução

---

## 🔍 Descobertas da Investigação

### ✅ JobLogManager já existe e é robusto!

```python
# src/job_log_manager.py
class JobLogManager:
    MONITORED_MODULES = [
        'src.orchestrator',  # ← Já monitora!
        'src.server_setup',
        'src.ansible_executor',
        ...
    ]

    # Features:
    # - Auto-capture via Python logging handlers
    # - Grava em arquivo incrementalmente
    # - Mantém últimos 100 logs em memória
    # - Thread-safe
```

**Implicação**: Se usarmos `logger.info()` no orchestrator, **logs são capturados automaticamente**! 🎉

### ✅ asyncssh suporta streaming com create_process()

```python
# Método atual (bloqueante):
result = await conn.run(cmd)  # Retorna só no fim

# Método streaming (linha por linha):
async with conn.create_process(cmd) as proc:
    while True:
        line = await proc.stdout.readline()
        if not line: break
        logger.info(f"[stdout] {line.decode()}")  # ← Auto-capturado!
```

### ✅ Job system já persiste logs incrementalmente

```python
# JobLogManager já faz:
file_handler = RotatingFileHandler(f"{job_id}.log")
# Cada logger.info() é gravado imediatamente no arquivo!
```

---

## 📊 Escopo Definitivo

### 1. Criar novo método streaming no orchestrator

**Arquivo**: `src/orchestrator/core.py`

```python
async def execute_remote_command_streaming(
    self,
    server_name: str,
    command: str,
    timeout: int = 30,
    working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute remote command with real-time stdout/stderr streaming

    Logs cada linha de output via logger.info() para captura automática
    pelo JobLogManager. Ideal para jobs de longa duração.

    Returns:
        {
            "stdout": str,  # Output completo
            "stderr": str,  # Errors completos
            "exit_code": int,
            "success": bool
        }
    """
    # Validações (mesmas do execute_remote_command)
    # ...

    logger.info(f"🔌 Connecting to {server_name} ({server_ip}) via SSH...")

    async with asyncssh.connect(...) as conn:
        logger.info(f"▶️  Executing: {command}")

        # Streaming com create_process
        async with conn.create_process(full_command) as process:
            stdout_lines = []
            stderr_lines = []

            async def stream_stdout():
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='replace').rstrip()
                    stdout_lines.append(decoded)
                    logger.info(f"📤 {decoded}")  # ← JobLogManager captura!

            async def stream_stderr():
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='replace').rstrip()
                    stderr_lines.append(decoded)
                    logger.warning(f"⚠️  {decoded}")  # ← Também capturado!

            # Roda ambos em paralelo com timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(stream_stdout(), stream_stderr()),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"⏱️  Command timed out after {timeout}s")
                process.kill()
                raise

            exit_code = process.returncode
            success = exit_code == 0

            logger.info(f"{'✅' if success else '❌'} Command finished: exit_code={exit_code}")

            return {
                "stdout": "\n".join(stdout_lines),
                "stderr": "\n".join(stderr_lines),
                "exit_code": exit_code,
                "success": success
            }
```

**Tamanho estimado**: ~80 linhas (similar ao método atual)

### 2. Atualizar remote_exec executor para usar streaming

**Arquivo**: `src/job_executors/remote_exec_executor.py`

```python
async def execute_remote_exec(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """Execute remote command with real-time log streaming"""

    server_name = job.params["server_name"]
    command = job.params["command"]

    # Step 1: Preparação
    job.advance_step(1, 2, f"Connecting to {server_name} via SSH")

    try:
        # Usa método STREAMING ao invés do bloqueante
        result = await orchestrator.execute_remote_command_streaming(
            server_name=server_name,
            command=command,
            timeout=job.params.get("timeout", 30),
            working_dir=job.params.get("working_dir")
        )

        # Logs já foram capturados automaticamente durante streaming!
        # JobLogManager já salvou tudo no arquivo .log

        # Step 2: Finalização
        success = result["success"]
        exit_code = result["exit_code"]

        if success:
            job.advance_step(2, 2, f"Command completed: exit_code={exit_code}")
        else:
            job.advance_step(2, 2, f"Command failed: exit_code={exit_code}")

        return result

    except Exception as e:
        logger.error(f"Remote exec failed: {e}", exc_info=True)
        job.update_progress(100, f"Failed: {str(e)}")
        raise
```

**Mudanças**:
- ✅ Apenas troca `execute_remote_command` → `execute_remote_command_streaming`
- ✅ Remove `job.add_log()` - JobLogManager cuida disso!
- ✅ Mais simples e limpo

### 3. Manter execute_remote_command original (sync path)

**IMPORTANTE**: NÃO substituir o método original!
- ✅ `execute_remote_command()` → Sync path (200 OK)
- ✅ `execute_remote_command_streaming()` → Job path (202 Accepted)

**Por que?**
- Sync path precisa ser **rápido** (< 60s)
- Streaming adiciona overhead mínimo de logging
- Usuário sync não precisa de logs detalhados

---

## 🧪 Estratégia de Testes TDD

### Test 1: Unit test para streaming method (RED → GREEN)

**Arquivo**: `tests/unit/test_remote_exec_streaming.py`

```python
@pytest.mark.asyncio
async def test_execute_remote_command_streaming_logs_output():
    """Should log each line of stdout/stderr in real-time"""

    # Setup
    orchestrator = create_test_orchestrator()

    # Mock asyncssh connection
    with patch('asyncssh.connect') as mock_connect:
        mock_proc = AsyncMock()

        # Simula output linha por linha
        mock_proc.stdout.readline = AsyncMock(side_effect=[
            b"Line 1\n",
            b"Line 2\n",
            b"Line 3\n",
            b""  # EOF
        ])
        mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
        mock_proc.returncode = 0

        mock_conn = AsyncMock()
        mock_conn.create_process = AsyncMock(return_value=mock_proc)
        mock_connect.return_value.__aenter__.return_value = mock_conn

        # Capture logs
        with capture_logs('src.orchestrator') as logs:
            result = await orchestrator.execute_remote_command_streaming(
                server_name="test",
                command="echo test"
            )

        # Assert
        assert "📤 Line 1" in logs
        assert "📤 Line 2" in logs
        assert "📤 Line 3" in logs
        assert result["stdout"] == "Line 1\nLine 2\nLine 3"
```

### Test 2: Integration test com JobLogManager

```python
@pytest.mark.asyncio
async def test_job_executor_saves_logs_to_file():
    """Job executor should save streaming logs to file via JobLogManager"""

    job_manager = JobManager(tmp_path)
    job = await job_manager.create_job(
        job_type="remote_exec",
        params={
            "server_name": "test",
            "command": "for i in 1 2 3; do echo Step $i; done"
        }
    )

    # Execute job
    await job_executor.execute_job(job, orchestrator)

    # Read log file
    log_file = job_manager.log_manager.logs_dir / f"{job.job_id}.log"
    assert log_file.exists()

    content = log_file.read_text()
    assert "📤 Step 1" in content
    assert "📤 Step 2" in content
    assert "📤 Step 3" in content
```

### Test 3: E2E test com servidor real

```typescript
// mcp-server/tests/e2e/test_mcp_e2e_workflow.ts

test('remote-bash job shows real-time logs', async () => {
    // Execute long command via job
    const execResult = await client.request({
        method: 'tools/call',
        params: {
            name: 'remote-bash',
            arguments: {
                server_name: 'e2e-test',
                command: 'for i in {1..5}; do echo "Step $i"; sleep 1; done',
                timeout: 30,
                use_job: true
            }
        }
    });

    const jobId = extractJobId(execResult);

    // Poll job status multiple times
    for (let i = 0; i < 10; i++) {
        await sleep(1000);

        const status = await getJobStatus(jobId, {tail_logs: 20});

        // Should see incremental logs
        expect(status.logs.length).toBeGreaterThan(0);

        if (status.status === 'completed') break;
    }

    // Final check
    const final = await getJobStatus(jobId);
    expect(final.logs).toContainEqual(expect.objectContaining({
        message: expect.stringContaining('📤 Step 1')
    }));
});
```

---

## 📁 Estrutura de Arquivos

```
src/
├── orchestrator/
│   └── core.py  [MODIFICAR]
│       - Adicionar execute_remote_command_streaming()
│       - Manter execute_remote_command() original
│
├── job_executors/
│   └── remote_exec_executor.py  [MODIFICAR]
│       - Trocar para execute_remote_command_streaming()
│       - Simplificar logging (JobLogManager cuida)
│
tests/
├── unit/
│   ├── test_remote_exec_streaming.py  [NOVO]
│   └── test_job_executor.py  [ATUALIZAR]
│
├── integration/
│   └── test_remote_exec_with_logs.py  [NOVO]
│
└── e2e/
    └── (já existe test_mcp_e2e_workflow.ts)
```

---

## ✅ Checklist de Implementação

### Etapa 1: TDD - Criar testes (RED phase)
- [ ] Test: streaming method loga cada linha
- [ ] Test: JobLogManager captura logs automaticamente
- [ ] Test: Timeout funciona corretamente
- [ ] Test: Stderr é capturado separadamente
- [ ] Rodar testes → Devem FALHAR (RED)

### Etapa 2: Implementar streaming method (GREEN phase)
- [ ] Criar `execute_remote_command_streaming()` em orchestrator
- [ ] Usar `conn.create_process()` para streaming
- [ ] Usar `logger.info()` para cada linha
- [ ] Handle timeout com asyncio.wait_for()
- [ ] Rodar testes → Devem PASSAR (GREEN)

### Etapa 3: Atualizar executor
- [ ] Modificar `execute_remote_exec()` usar método streaming
- [ ] Remover `job.add_log()` manual
- [ ] Simplificar código
- [ ] Rodar testes unitários

### Etapa 4: Testar via terminal
- [ ] Comando rápido (sync): `curl` com timeout=30
- [ ] Comando longo (job): `curl` com use_job=true
- [ ] Monitorar job: `get-job-status` múltiplas vezes
- [ ] Validar logs aparecem incrementalmente
- [ ] Verificar arquivo .log no disco

### Etapa 5: Validar com E2E
- [ ] Atualizar test E2E para validar logs
- [ ] Rodar E2E completo: `npm run test:e2e`
- [ ] Validar todos cenários passam

---

## 📦 Dependências Novas

**Nenhuma!** ✅

Tudo já existe:
- ✅ asyncssh (já instalado)
- ✅ JobLogManager (já implementado)
- ✅ Job system (já funcional)

---

## 🎯 Critérios de Sucesso

### User Experience esperada:

```bash
# User executa comando longo:
remote-bash(
    server="prod",
    command="apt-get update && apt-get upgrade -y",
    timeout=180,
    use_job=true
)

# Resposta:
{job_id: "remote_exec-abc123"}

# User monitora (a cada 2s):
get-job-status(job_id="remote_exec-abc123", tail_logs=20)

# Output evolui em tempo real:
[19:10:01] 🔌 Connecting to prod (1.2.3.4) via SSH...
[19:10:02] ▶️  Executing: apt-get update && apt-get upgrade -y
[19:10:03] 📤 Hit:1 http://deb.debian.org/debian bookworm InRelease
[19:10:04] 📤 Get:2 http://security.debian.org bookworm-security InRelease
[19:10:05] 📤 Reading package lists...
[19:10:10] 📤 Building dependency tree...
...
[19:12:30] ✅ Command finished: exit_code=0
```

### Validações técnicas:

✅ **Logs aparecem linha por linha** durante execução
✅ **JobLogManager salva no arquivo** incrementalmente
✅ **get-job-status retorna logs recentes** de memória
✅ **Timeout funciona** (kill process após N segundos)
✅ **Stderr separado** de stdout
✅ **Exit code correto** ao final

---

## ⚠️ Considerações Importantes

### 1. Performance

**Streaming vs Bloqueante**:
- Streaming: +5-10ms overhead por linha (mínimo)
- Bloqueante: 0ms overhead (retorna tudo no fim)

**Decisão**: Aceitável para job path (já é longo)

### 2. Limite de output

**Problema**: Comando pode gerar 100MB de output

**Solução atual**: Truncar stdout/stderr em 10KB
```python
# Manter limite em 10KB para evitar memory issues
if len(stdout_lines) > 1000:  # ~10KB
    stdout_lines = stdout_lines[:1000]
    logger.warning("Output truncated: exceeded 10KB limit")
```

### 3. Encoding

**Problema**: Output pode ter encoding variado

**Solução**: `decode('utf-8', errors='replace')`
- Replace caracteres inválidos com �
- Nunca falha

### 4. Backward compatibility

✅ **Sync path não afetado** - continua usando método original
✅ **Jobs migram automaticamente** - só trocar método
✅ **API não muda** - mesmos endpoints

---

## 🚀 Próximos Passos (Pós-09.2)

Após implementar streaming:
1. **PLAN-10**: Add job cancellation (kill SSH process)
2. **PLAN-11**: WebSocket support para live logs (sem polling)
3. **PLAN-12**: Log filtering (por level, regex)

---

## 📊 Status

🔵 **READY TO START** - Plano aprovado, aguardando implementação

---

*Plan Version: 1.0.0*
*Created: 2025-10-21*
*Based on: PLAN-09.1 + Investigation findings*
