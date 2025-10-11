# Plan 04.6 - Observabilidade via Logging Handlers

## 📋 Contexto

**Referência**: CLAUDE.md - Development Practices, Testing Strategy
**Status Atual**: Plan-04.5 implementado (JobExecutor funcionando)

### Problema Identificado

Durante testes E2E via API (`test_api_e2e_workflow.py`), descobrimos **gap crítico de observabilidade**:

```python
# Teste E2E Direto (sem API) - O que vemos:
PLAY [Base Server Setup] *******************************************************
TASK [Gathering Facts] *********************************************************
ok: [e2e-api-test]
TASK [Update apt cache] ********************************************************
changed: [e2e-api-test]
...
✅ Vemos TUDO: cada task, stdout, stderr, erros específicos

# Teste E2E via API - O que vemos:
⏳ Monitoring Server setup (ID: setup_server-713eaecf)...
   [0s] 0% -
   [5s] 100% - Server setup completed
✅ Server setup completed in 5s

GET /api/jobs/setup_server-713eaecf:
{
  "logs": [
    {"message": "Job started"},
    {"message": "Progress: 10% - Starting setup..."},
    {"message": "Progress: 100% - Server setup completed"}
  ]
}
❌ Não vemos NADA do que realmente aconteceu!
```

**Impacto**:
- ❌ Impossível debugar via API
- ❌ Agente AI via MCP será cego
- ❌ Jobs falham mas não sabemos por quê
- ❌ Usuários não têm visibilidade

---

## 🎯 Objetivo

Implementar sistema de observabilidade **equivalente ao teste E2E direto**, permitindo:

1. Ver logs detalhados de Ansible playbooks via API
2. Filtrar logs por nível (DEBUG, INFO, WARNING, ERROR)
3. Acessar logs históricos (até 72h)
4. Obter últimas N linhas rapidamente
5. **ZERO mudanças invasivas no código existente**

---

## 🔬 Análise: Callback vs Logging Handlers

### ❌ Abordagem 1: Progress Callbacks (Rejeitada)

```python
# Requer modificar TODAS as classes
class ProgressReporter(Protocol):
    def report_progress(self, percent: int, message: str) -> None: ...
    def report_log(self, level: str, message: str) -> None: ...

class Orchestrator:
    def setup_server(self, callback: Optional[ProgressReporter] = None):
        if callback:
            callback.report_progress(10, "Starting...")
        # Adicionar callback em CADA passo

class ServerSetup:
    def full_setup(self, callback: Optional[ProgressReporter] = None):
        if callback:
            callback.report_progress(20, "Installing Docker...")
        # Adicionar callback em CADA step
```

**Problemas:**
- 🔴 **Invasivo**: Modifica 10+ métodos (orchestrator, server_setup, ansible_executor, etc)
- 🔴 **Código duplicado**: `if callback: callback.report()` everywhere
- 🔴 **Não captura logs existentes**: Temos 37+ `logger.info()` em server_setup.py que seriam ignorados
- 🔴 **Threading complexo**: Callbacks precisam ser thread-safe manualmente
- 🔴 **~400 LOC de mudanças** em múltiplos arquivos
- 🔴 **Manutenção difícil**: Cada nova feature precisa adicionar callbacks

### ✅ Abordagem 2: Logging Handlers (Recomendada)

```python
# ZERO mudanças no código existente!
# Python logging já está sendo usado:
logger.info("Starting setup for server...")  # Já existe!
logger.warning("SSH took 30s")                # Já existe!
logger.error("Task failed: ...")              # Já existe!

# Basta adicionar handlers para capturar:
class JobLogManager:
    def start_job_logging(self, job_id: str):
        # Criar handlers
        file_handler = RotatingFileHandler(f"~/.livchat/logs/{job_id}.log")
        memory_handler = RecentLogsHandler(max_records=100)

        # Anexar aos módulos relevantes
        for module in ['orchestrator', 'server_setup', 'ansible_executor']:
            logger = logging.getLogger(f'src.{module}')
            logger.addHandler(file_handler)
            logger.addHandler(memory_handler)
```

**Vantagens:**
- ✅ **NÃO invasivo**: Zero mudanças no código existente
- ✅ **Captura tudo**: Todos os 37+ logs já existentes são capturados
- ✅ **Thread-safe**: Python logging é thread-safe out of the box
- ✅ **Níveis automáticos**: DEBUG, INFO, WARNING, ERROR já funcionam
- ✅ **Formatação automática**: Timestamps, níveis, formatação inclusa
- ✅ **~250 LOC total**: Apenas novo JobLogManager + integração
- ✅ **Manutenção zero**: Novos logs são capturados automaticamente

**Por que funciona?**
```python
# Python logging usa hierarquia:
logger = logging.getLogger('src.orchestrator')
logger.info("Creating server...")

# Este log propaga para:
# 1. Handlers do logger 'src.orchestrator'
# 2. Handlers do logger 'src'
# 3. Handlers do root logger

# Podemos adicionar handlers dinamicamente em QUALQUER ponto da hierarquia!
```

---

## 📊 Escopo Definitivo

### 1. **JobLogManager** (Novo componente)

```python
# src/job_log_manager.py (~200 LOC)

from logging.handlers import RotatingFileHandler
from collections import deque
from pathlib import Path
from typing import Dict, List
import logging

class RecentLogsHandler(logging.Handler):
    """
    Handler que mantém últimas N mensagens em memória
    Para respostas rápidas da API sem I/O de arquivo
    """
    def __init__(self, max_records=100):
        super().__init__()
        self.max_records = max_records
        self.records = deque(maxlen=max_records)

    def emit(self, record):
        """Armazena log record em memória"""
        self.records.append({
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage()
        })

    def get_recent_logs(self, limit: int = None) -> List[Dict]:
        """Retorna logs recentes (mais novos primeiro)"""
        logs = list(self.records)
        logs.reverse()
        return logs[:limit] if limit else logs

    def clear(self):
        """Limpa todos os logs da memória"""
        self.records.clear()


class JobLogManager:
    """
    Gerencia captura de logs para jobs usando Python logging handlers

    Features:
    - Captura logs em arquivo (completo, rotacionado)
    - Mantém últimas 100 linhas em memória (API rápida)
    - Logs expiram em 72h automaticamente
    - Thread-safe (Python logging built-in)
    """

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir / "jobs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Track handlers ativos por job
        self.handlers: Dict[str, List[logging.Handler]] = {}
        self.memory_handlers: Dict[str, RecentLogsHandler] = {}

        # Módulos cujos logs queremos capturar
        self.monitored_modules = [
            'src.orchestrator',
            'src.server_setup',
            'src.ansible_executor',
            'src.app_deployer',
            'src.providers',
            'src.integrations'
        ]

    def start_job_logging(self, job_id: str) -> Path:
        """
        Inicia captura de logs para um job

        Returns:
            Path do arquivo de log criado
        """
        if job_id in self.handlers:
            # Já está capturando
            return self.logs_dir / f"{job_id}.log"

        log_file = self.logs_dir / f"{job_id}.log"

        # FileHandler com rotação (max 10MB, sem backup)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=0  # Sem backup, logs expiram
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # MemoryHandler para últimas 100 linhas
        memory_handler = RecentLogsHandler(max_records=100)
        memory_handler.setLevel(logging.DEBUG)

        # Adicionar handlers aos módulos monitorados
        handlers = [file_handler, memory_handler]
        for module_name in self.monitored_modules:
            logger = logging.getLogger(module_name)
            for handler in handlers:
                logger.addHandler(handler)

        # Salvar referências
        self.handlers[job_id] = handlers
        self.memory_handlers[job_id] = memory_handler

        logger.info(f"Started log capture for job {job_id} → {log_file}")

        return log_file

    def stop_job_logging(self, job_id: str):
        """
        Para captura de logs e remove handlers
        """
        if job_id not in self.handlers:
            return

        handlers = self.handlers[job_id]

        # Remover handlers dos loggers
        for module_name in self.monitored_modules:
            logger = logging.getLogger(module_name)
            for handler in handlers:
                logger.removeHandler(handler)

        # Fechar handlers
        for handler in handlers:
            handler.close()

        # Limpar referências
        del self.handlers[job_id]
        del self.memory_handlers[job_id]

        logger.info(f"Stopped log capture for job {job_id}")

    def get_recent_logs(self, job_id: str, limit: int = 50) -> List[Dict]:
        """
        Retorna logs recentes da memória (O(1), sem I/O)

        Args:
            job_id: Job identifier
            limit: Número máximo de logs (padrão: 50)

        Returns:
            Lista de dicts com timestamp, level, message
        """
        if job_id in self.memory_handlers:
            return self.memory_handlers[job_id].get_recent_logs(limit)
        return []

    def read_log_file(
        self,
        job_id: str,
        tail: int = 100,
        level_filter: Optional[str] = None
    ) -> List[str]:
        """
        Lê arquivo de log (últimas N linhas)

        Args:
            job_id: Job identifier
            tail: Número de linhas do fim (padrão: 100)
            level_filter: Filtrar por nível (DEBUG, INFO, WARNING, ERROR)

        Returns:
            Lista de linhas de log
        """
        log_file = self.logs_dir / f"{job_id}.log"

        if not log_file.exists():
            return []

        # Ler últimas N linhas eficientemente
        lines = self._tail_file(log_file, tail)

        # Filtrar por nível se especificado
        if level_filter:
            lines = [l for l in lines if level_filter in l]

        return lines

    def _tail_file(self, file_path: Path, n: int) -> List[str]:
        """Lê últimas N linhas de arquivo eficientemente"""
        with open(file_path, 'rb') as f:
            # Seek to end
            f.seek(0, 2)
            file_size = f.tell()

            # Read in chunks from end
            buffer_size = 8192
            lines = []
            buffer = b''

            while len(lines) < n and file_size > 0:
                read_size = min(buffer_size, file_size)
                file_size -= read_size
                f.seek(file_size)

                chunk = f.read(read_size)
                buffer = chunk + buffer

                # Split into lines
                lines = buffer.decode('utf-8', errors='ignore').splitlines()

            # Return last n lines
            return lines[-n:]

    def cleanup_old_logs(self, max_age_hours: int = 72) -> int:
        """
        Remove arquivos de log mais antigos que max_age_hours

        Args:
            max_age_hours: Idade máxima em horas (padrão: 72h)

        Returns:
            Número de arquivos removidos
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed = 0

        for log_file in self.logs_dir.glob("*.log"):
            # Check file modification time
            if log_file.stat().st_mtime < cutoff.timestamp():
                try:
                    log_file.unlink()
                    removed += 1
                except Exception as e:
                    logger.warning(f"Failed to delete old log {log_file}: {e}")

        if removed > 0:
            logger.info(f"Cleaned up {removed} old log files (>{max_age_hours}h)")

        return removed
```

---

### 2. **Integração com JobManager**

```python
# src/job_manager.py (modificar)

from src.job_log_manager import JobLogManager

class JobManager:
    def __init__(self, storage=None):
        self.storage = storage
        self.jobs: Dict[str, Job] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

        # Adicionar JobLogManager
        logs_dir = Path.home() / ".livchat" / "logs"
        self.log_manager = JobLogManager(logs_dir)

        if storage:
            self._load_from_storage()

    async def run_job(
        self,
        job_id: str,
        task_func: Callable[[Job], Awaitable[Any]]
    ):
        """Execute job with log capture"""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            # Iniciar captura de logs
            log_file = self.log_manager.start_job_logging(job_id)
            job.log_file = str(log_file)  # Adicionar ao job

            # Mark as started
            job.mark_started()
            self.save_to_storage()

            # Execute task (logs são capturados automaticamente!)
            result = await task_func(job)

            # Mark as completed
            job.mark_completed(result=result)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            job.mark_completed(error=error_msg)
            logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True)

        finally:
            # Parar captura de logs
            self.log_manager.stop_job_logging(job_id)
            self.save_to_storage()
```

---

### 3. **Modificar Job Model**

```python
# src/job_manager.py (Job class)

@dataclass
class Job:
    job_id: str
    job_type: str
    params: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    current_step: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[Dict[str, str]] = field(default_factory=list)  # Deprecated
    log_file: Optional[str] = None  # ← NOVO: Path para arquivo de log
```

---

### 4. **API Routes para Logs**

```python
# src/api/routes/jobs.py (adicionar)

@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    tail: int = Query(100, ge=1, le=10000, description="Last N lines"),
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARNING|ERROR)$"),
    job_manager: JobManager = Depends(get_job_manager)
):
    """
    Get detailed logs for a job

    Reads from log file on disk. Supports:
    - tail: Get last N lines (default: 100, max: 10000)
    - level: Filter by log level (DEBUG, INFO, WARNING, ERROR)

    Example:
        GET /api/jobs/setup-abc/logs?tail=500&level=ERROR

    Returns:
        - total_lines: Number of lines returned
        - logs: List of log lines
        - log_file: Path to full log file
    """
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    # Ler logs do arquivo
    logs = job_manager.log_manager.read_log_file(
        job_id,
        tail=tail,
        level_filter=level
    )

    return {
        "job_id": job_id,
        "total_lines": len(logs),
        "logs": logs,
        "log_file": job.log_file
    }


# Modificar GET /api/jobs/{job_id} existente
@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager)
):
    """Get job status with recent logs"""
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")

    response = _job_to_response(job)

    # Adicionar últimas 50 linhas de log da memória (rápido!)
    response["recent_logs"] = job_manager.log_manager.get_recent_logs(
        job_id,
        limit=50
    )

    return JobResponse(**response)
```

---

### 5. **Background Cleanup Task**

```python
# src/api/background.py (modificar lifespan)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan with background tasks"""
    logger.info("🚀 Starting LivChat Setup API...")

    # Initialize managers
    orchestrator = get_orchestrator()
    job_manager = get_job_manager()

    # Start job executor
    executor = JobExecutor(job_manager, orchestrator)
    await executor.start()
    logger.info("✅ JobExecutor started successfully")

    # Start cleanup task
    cleanup_task = asyncio.create_task(log_cleanup_loop(job_manager))
    logger.info("✅ Log cleanup task started")

    logger.info("✅ LivChat Setup API ready!")

    yield  # API runs here

    # Shutdown
    logger.info("🛑 Shutting down LivChat Setup API...")

    # Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Stop executor
    await executor.stop()
    logger.info("✅ LivChat Setup API shutdown complete")


async def log_cleanup_loop(job_manager: JobManager):
    """Background task para limpar logs antigos a cada hora"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hora

            # Limpar logs > 72h
            removed = job_manager.log_manager.cleanup_old_logs(max_age_hours=72)

            if removed > 0:
                logger.info(f"Cleaned up {removed} old log files")

        except asyncio.CancelledError:
            logger.info("Log cleanup task cancelled")
            break

        except Exception as e:
            logger.error(f"Error in log cleanup: {e}", exc_info=True)
```

---

## 🧪 Estratégia de Testes

### Unit Tests

```python
# tests/unit/test_job_log_manager.py

class TestJobLogManager:
    def test_start_stop_logging(self):
        """Should create and cleanup handlers"""
        manager = JobLogManager(Path("/tmp/test"))

        # Start
        log_file = manager.start_job_logging("test-123")
        assert log_file.exists()
        assert "test-123" in manager.handlers

        # Stop
        manager.stop_job_logging("test-123")
        assert "test-123" not in manager.handlers

    def test_recent_logs_memory(self):
        """Should capture recent logs in memory"""
        manager = JobLogManager(Path("/tmp/test"))
        manager.start_job_logging("test-123")

        # Generate logs
        logger = logging.getLogger("src.orchestrator")
        logger.info("Test message 1")
        logger.warning("Test message 2")

        # Retrieve
        logs = manager.get_recent_logs("test-123", limit=10)
        assert len(logs) == 2
        assert logs[0]["message"] == "Test message 2"  # Newest first

    def test_read_log_file(self):
        """Should read from file"""
        manager = JobLogManager(Path("/tmp/test"))
        manager.start_job_logging("test-456")

        logger = logging.getLogger("src.server_setup")
        for i in range(200):
            logger.info(f"Line {i}")

        # Read last 50
        lines = manager.read_log_file("test-456", tail=50)
        assert len(lines) == 50
        assert "Line 199" in lines[-1]

    def test_level_filtering(self):
        """Should filter by log level"""
        manager = JobLogManager(Path("/tmp/test"))
        manager.start_job_logging("test-789")

        logger = logging.getLogger("src.ansible_executor")
        logger.info("Info message")
        logger.error("Error message")
        logger.warning("Warning message")

        # Filter ERROR only
        lines = manager.read_log_file("test-789", tail=100, level_filter="ERROR")
        assert len(lines) == 1
        assert "Error message" in lines[0]

    def test_cleanup_old_logs(self):
        """Should remove logs older than threshold"""
        manager = JobLogManager(Path("/tmp/test"))

        # Create old file
        old_log = manager.logs_dir / "old-job.log"
        old_log.write_text("old")

        # Set mtime to 80 hours ago
        old_time = time.time() - (80 * 3600)
        os.utime(old_log, (old_time, old_time))

        # Cleanup
        removed = manager.cleanup_old_logs(max_age_hours=72)
        assert removed == 1
        assert not old_log.exists()
```

### Integration Tests

```python
# tests/integration/test_job_logging_integration.py

class TestJobLoggingIntegration:
    @pytest.mark.asyncio
    async def test_job_with_logging(self):
        """Test complete job execution with log capture"""
        storage = StorageManager(Path("/tmp/test"))
        job_manager = JobManager(storage)

        # Create and run job
        job = job_manager.create_job("test_job", {"test": True})

        async def mock_task(job):
            logger = logging.getLogger("src.orchestrator")
            logger.info("Task started")
            logger.info("Processing...")
            logger.info("Task completed")
            return {"success": True}

        await job_manager.run_job(job.job_id, mock_task)

        # Verify logs captured
        assert job.log_file is not None
        assert Path(job.log_file).exists()

        # Read logs
        logs = job_manager.log_manager.read_log_file(job.job_id)
        assert any("Task started" in line for line in logs)
        assert any("Task completed" in line for line in logs)

        # Recent logs in memory
        recent = job_manager.log_manager.get_recent_logs(job.job_id)
        assert len(recent) == 3
```

---

## 📁 Estrutura de Arquivos

```
src/
├── job_log_manager.py           # 🆕 NOVO - ~200 LOC
├── job_manager.py                # 🔄 MODIFICAR - +20 LOC
└── api/
    ├── background.py             # 🔄 MODIFICAR - +30 LOC
    └── routes/
        └── jobs.py               # 🔄 MODIFICAR - +60 LOC

tests/
├── unit/
│   └── test_job_log_manager.py  # 🆕 NOVO - ~150 LOC
└── integration/
    └── test_job_logging_integration.py  # 🆕 NOVO - ~100 LOC

~/.livchat/
└── logs/
    └── jobs/
        ├── setup_server-abc123.log
        ├── deploy_app-def456.log
        └── create_server-ghi789.log
```

---

## ✅ Checklist de Implementação

### Etapa 1: JobLogManager Core
- [ ] Task 1.1: Criar src/job_log_manager.py
- [ ] Task 1.2: Implementar RecentLogsHandler
- [ ] Task 1.3: Implementar JobLogManager.start_job_logging()
- [ ] Task 1.4: Implementar JobLogManager.stop_job_logging()
- [ ] Task 1.5: Implementar JobLogManager.get_recent_logs()
- [ ] Task 1.6: Implementar JobLogManager.read_log_file()
- [ ] Task 1.7: Implementar JobLogManager.cleanup_old_logs()

### Etapa 2: Integração com JobManager
- [ ] Task 2.1: Adicionar log_manager ao JobManager.__init__()
- [ ] Task 2.2: Modificar JobManager.run_job() para start/stop logging
- [ ] Task 2.3: Adicionar log_file field ao Job model
- [ ] Task 2.4: Atualizar Job.to_dict() e from_dict()

### Etapa 3: API Routes
- [ ] Task 3.1: Criar GET /api/jobs/{job_id}/logs endpoint
- [ ] Task 3.2: Modificar GET /api/jobs/{job_id} para incluir recent_logs
- [ ] Task 3.3: Adicionar validação de parâmetros (tail, level)
- [ ] Task 3.4: Testar endpoints via pytest

### Etapa 4: Background Cleanup
- [ ] Task 4.1: Criar log_cleanup_loop() em background.py
- [ ] Task 4.2: Integrar no lifespan context manager
- [ ] Task 4.3: Adicionar logging para cleanup events

### Etapa 5: Testes
- [ ] Task 5.1: Escrever tests/unit/test_job_log_manager.py
- [ ] Task 5.2: Escrever tests/integration/test_job_logging_integration.py
- [ ] Task 5.3: Rodar pytest e verificar cobertura > 85%
- [ ] Task 5.4: Testar manualmente com E2E test

### Etapa 6: Validação E2E
- [ ] Task 6.1: Rodar test_api_e2e_workflow.py
- [ ] Task 6.2: Verificar GET /api/jobs/{id} tem recent_logs
- [ ] Task 6.3: Verificar GET /api/jobs/{id}/logs retorna detalhes
- [ ] Task 6.4: Verificar logs expiram em 72h

---

## 📦 Dependências

Nenhuma! Tudo usa Python stdlib:
- `logging` (built-in)
- `logging.handlers` (built-in)
- `collections.deque` (built-in)
- `pathlib` (built-in)

---

## 🎯 Critérios de Sucesso

1. ✅ **Observabilidade equivalente**: Logs via API tão detalhados quanto teste direto
2. ✅ **Performance**: GET /api/jobs/{id} retorna em < 100ms (logs em memória)
3. ✅ **Escalabilidade**: Logs expiram automaticamente em 72h
4. ✅ **Filtragem**: Suporta filtrar por nível e tail
5. ✅ **Zero mudanças invasivas**: Código existente não modificado
6. ✅ **Testes passando**: > 85% cobertura

---

## 📊 Métricas

- **LOC Total**: ~250 linhas (vs ~400 com callbacks)
- **Arquivos novos**: 3 (job_log_manager.py + 2 testes)
- **Arquivos modificados**: 3 (job_manager.py, background.py, routes/jobs.py)
- **Tempo estimado**: 3-4 horas (com testes)
- **Invasividade**: ZERO (não toca orchestrator, server_setup, etc)

---

## ⚠️ Considerações Importantes

### Disk Space
- Logs podem crescer (10MB max por job)
- Cleanup automático a cada 72h
- Monitorar ~/.livchat/logs/ size

### Performance
- FileHandler é thread-safe mas pode ter I/O overhead
- MemoryHandler resolve isso para API responses
- RotatingFileHandler evita logs infinitos

### Backward Compatibility
- Job.logs (list) marcado como deprecated
- Mantido para compatibilidade com jobs antigos
- Novos jobs usam log_file + recent_logs

---

## 🚀 Próximos Passos Após Implementação

Com observabilidade resolvida, podemos:
1. ✅ **Plan 04.7**: Implementar MCP TypeScript Server (já tem logs!)
2. ✅ **Fix Executor Error Handling**: Agora vemos logs de falhas
3. ✅ **Production Deployment**: Sistema observável e debugável

---

**Plan Version**: 1.0
**Created**: 2025-10-11
**Status**: 🔵 READY TO START
**Estimated**: 3-4 horas
**Priority**: P0 (Bloqueador para MCP)
