# Plan 04.5 - Job Executor Implementation

## 📋 Contexto

### Status Atual
Após implementar o Plan-04-v2 (API + Routes), temos:
- ✅ API REST completa (172 testes passing)
- ✅ JobManager cria e persiste jobs
- ✅ Routes retornam job_id (202 Accepted)
- ❌ **Jobs NUNCA são executados** - ficam em `pending` para sempre

### Problema Identificado
Descoberto ao rodar E2E test via API (`test_api_e2e_workflow.py`):

```python
# Cliente faz POST /api/servers
response = client.post("/api/servers", json={...})
job_id = response.json()["job_id"]  # ✅ Job criado

# Cliente faz polling
while True:
    job = client.get(f"/api/jobs/{job_id}").json()
    if job["status"] == "completed": break
    time.sleep(5)

# ❌ Loop infinito - job nunca sai de "pending"
```

**Por quê?**
Não existe nenhum componente que:
1. Monitora jobs com status=pending
2. Executa a lógica (orchestrator.create_server, deploy_app, etc)
3. Atualiza o status do job

### Arquitetura Atual vs Desejada

**ATUAL (incompleto):**
```
API Route → JobManager.create_job() → jobs.json (pending)
                                           ↓
                                      ❌ NADA ACONTECE
```

**DESEJADA:**
```
API Route → JobManager.create_job() → jobs.json (pending)
                                           ↓
                     JobExecutor (background) → Pega job pending
                                           ↓
                           Executa Orchestrator.create_server()
                                           ↓
                              Atualiza job → completed
```

## 🎯 Objetivo

Implementar **Job Executor** para processar jobs de forma assíncrona, permitindo que:
- E2E tests via API funcionem completamente
- Sistema seja production-ready
- Jobs sejam executados mesmo se API reiniciar

## 📊 Escopo Definitivo

### Componentes a Implementar

#### 1. **Job Executor Core** (`src/job_executor.py`)
```python
class JobExecutor:
    """
    Processa jobs em background usando asyncio

    Responsibilities:
    - Monitor jobs.json para pending jobs
    - Executar job usando JobManager.run_job()
    - Atualizar progresso em tempo real
    - Retry em caso de falha
    - Logging detalhado
    """

    def __init__(self, job_manager, orchestrator):
        self.job_manager = job_manager
        self.orchestrator = orchestrator
        self.running = False
        self._task = None

    async def start(self):
        """Inicia loop de processamento"""
        self.running = True
        self._task = asyncio.create_task(self._process_loop())

    async def stop(self):
        """Para loop gracefully"""
        self.running = False
        if self._task:
            await self._task

    async def _process_loop(self):
        """Loop principal - processa jobs pending"""
        while self.running:
            try:
                await self._process_pending_jobs()
            except Exception as e:
                logger.error(f"Error in job executor: {e}")

            await asyncio.sleep(2)  # Check every 2s

    async def _process_pending_jobs(self):
        """Processa todos jobs pending"""
        pending = self.job_manager.list_jobs(status=JobStatus.PENDING)

        for job in pending:
            # Execute in background (don't block other jobs)
            asyncio.create_task(self._execute_job(job))

    async def _execute_job(self, job: Job):
        """Executa um job específico"""
        # Determina qual função executar baseado no job_type
        executor_func = self._get_executor_function(job.job_type)

        if not executor_func:
            job.mark_completed(error=f"Unknown job type: {job.job_type}")
            return

        # Usa JobManager.run_job() que já existe!
        await self.job_manager.run_job(job.job_id, executor_func)
```

#### 2. **Job Executor Functions** (`src/job_executors/`)
Funções específicas para cada tipo de job:

```python
# src/job_executors/server_executors.py
async def execute_create_server(job: Job, orchestrator: Orchestrator):
    """
    Executa criação de servidor

    Args:
        job: Job com params = {name, server_type, location, image}
        orchestrator: Orchestrator instance

    Returns:
        Dict com server info
    """
    params = job.params

    # Update progress
    job.update_progress(10, "Validating parameters...")

    # Create server via orchestrator
    job.update_progress(30, "Creating server on Hetzner...")
    server = orchestrator.create_server(
        name=params["name"],
        server_type=params["server_type"],
        region=params["location"],
        image=params.get("image", "debian-12")
    )

    job.update_progress(80, "Waiting for server to be ready...")
    # Wait for server to be accessible
    await asyncio.sleep(10)

    job.update_progress(100, "Server created successfully")

    return {
        "server_id": server.get("id"),
        "ip": server.get("ip"),
        "name": server.get("name")
    }


async def execute_setup_server(job: Job, orchestrator: Orchestrator):
    """Executa setup do servidor (Docker, Swarm, Traefik)"""
    params = job.params
    server_name = params["server_name"]

    job.update_progress(10, "Preparing server setup...")

    # Run setup via orchestrator
    job.update_progress(30, "Installing Docker...")
    result = orchestrator.setup_server(
        server_name,
        options=params.get("options", {})
    )

    job.update_progress(100, "Server setup completed")

    return result


async def execute_delete_server(job: Job, orchestrator: Orchestrator):
    """Executa deleção de servidor"""
    params = job.params
    server_name = params["server_name"]

    job.update_progress(30, "Deleting server from Hetzner...")
    orchestrator.delete_server(server_name)

    job.update_progress(100, "Server deleted")

    return {"deleted": True, "server_name": server_name}


# src/job_executors/app_executors.py
async def execute_deploy_app(job: Job, orchestrator: Orchestrator):
    """Executa deploy de aplicação"""
    params = job.params

    job.update_progress(10, "Preparing app deployment...")

    # Deploy via orchestrator
    job.update_progress(40, f"Deploying {params['app_name']}...")
    result = await orchestrator.deploy_app(
        server_name=params["server_name"],
        app_name=params["app_name"],
        config=params.get("environment", {})
    )

    job.update_progress(100, "App deployed successfully")

    return result


async def execute_undeploy_app(job: Job, orchestrator: Orchestrator):
    """Executa undeploy de aplicação"""
    params = job.params

    job.update_progress(30, f"Removing {params['app_name']}...")
    result = await orchestrator.undeploy_app(
        server_name=params["server_name"],
        app_name=params["app_name"]
    )

    job.update_progress(100, "App removed")

    return result
```

#### 3. **FastAPI Integration** (`src/api/background.py`)
Integração com lifecycle do FastAPI:

```python
# src/api/background.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

from src.job_executor import JobExecutor
from src.api.dependencies import get_job_manager, get_orchestrator

_executor: JobExecutor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan manager

    Starts/stops job executor with the API
    """
    global _executor

    # Startup
    job_manager = get_job_manager()
    orchestrator = get_orchestrator()

    _executor = JobExecutor(job_manager, orchestrator)
    await _executor.start()

    print("✅ Job Executor started")

    yield  # API runs here

    # Shutdown
    await _executor.stop()
    print("👋 Job Executor stopped")


def get_executor() -> JobExecutor:
    """Get executor instance (for testing)"""
    return _executor
```

**Modificar `src/api/server.py`:**
```python
from src.api.background import lifespan

app = FastAPI(
    title="LivChatSetup API",
    # ... existing config ...
    lifespan=lifespan  # ← ADD THIS
)
```

#### 4. **Executor Registry** (`src/job_executor.py`)
```python
# Mapeia job_type → executor function
EXECUTOR_REGISTRY = {
    "create_server": execute_create_server,
    "setup_server": execute_setup_server,
    "delete_server": execute_delete_server,
    "deploy_app": execute_deploy_app,
    "undeploy_app": execute_undeploy_app,
}

class JobExecutor:
    def _get_executor_function(self, job_type: str):
        """Get executor function for job type"""
        func = EXECUTOR_REGISTRY.get(job_type)

        if not func:
            logger.error(f"No executor for job type: {job_type}")
            return None

        # Wrap to inject orchestrator
        async def wrapper(job: Job):
            return await func(job, self.orchestrator)

        return wrapper
```

## 🧪 Estratégia de Testes TDD

### 1. Unit Tests - Job Executor

**`tests/unit/test_job_executor.py`** (RED → GREEN)
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.job_executor import JobExecutor
from src.job_manager import JobManager, Job, JobStatus

class TestJobExecutor:
    """Unit tests for JobExecutor"""

    @pytest.fixture
    def job_manager(self):
        manager = MagicMock(spec=JobManager)
        manager.list_jobs.return_value = []
        manager.run_job = AsyncMock()
        return manager

    @pytest.fixture
    def orchestrator(self):
        return MagicMock()

    @pytest.fixture
    def executor(self, job_manager, orchestrator):
        return JobExecutor(job_manager, orchestrator)

    @pytest.mark.asyncio
    async def test_start_initializes_executor(self, executor):
        """Should start background task"""
        await executor.start()
        assert executor.running is True
        assert executor._task is not None
        await executor.stop()

    @pytest.mark.asyncio
    async def test_stop_gracefully_stops_executor(self, executor):
        """Should stop background loop"""
        await executor.start()
        await executor.stop()
        assert executor.running is False

    @pytest.mark.asyncio
    async def test_processes_pending_jobs(self, executor, job_manager):
        """Should pick up pending jobs and execute them"""
        # Create pending job
        job = Job(
            job_id="test-123",
            job_type="create_server",
            params={"name": "test"}
        )
        job_manager.list_jobs.return_value = [job]

        # Start executor briefly
        await executor.start()
        await asyncio.sleep(0.5)  # Let it process
        await executor.stop()

        # Should have called run_job
        job_manager.run_job.assert_called()

    @pytest.mark.asyncio
    async def test_handles_unknown_job_type(self, executor, job_manager):
        """Should mark job as failed for unknown type"""
        job = Job(
            job_id="test-456",
            job_type="unknown_type",
            params={}
        )

        result = await executor._execute_job(job)

        assert job.status == JobStatus.FAILED
        assert "Unknown job type" in job.error
```

### 2. Unit Tests - Executor Functions

**`tests/unit/test_job_executors.py`** (RED → GREEN)
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.job_executors.server_executors import (
    execute_create_server,
    execute_setup_server,
    execute_delete_server
)
from src.job_manager import Job

class TestServerExecutors:
    """Test executor functions for server operations"""

    @pytest.mark.asyncio
    async def test_execute_create_server(self):
        """Should create server and update progress"""
        # Mock orchestrator
        orch = MagicMock()
        orch.create_server.return_value = {
            "id": "srv-123",
            "ip": "192.168.1.1",
            "name": "test-server"
        }

        # Create job
        job = Job(
            job_id="create-test",
            job_type="create_server",
            params={
                "name": "test-server",
                "server_type": "cx11",
                "location": "nbg1"
            }
        )

        # Execute
        result = await execute_create_server(job, orch)

        # Assertions
        assert result["server_id"] == "srv-123"
        assert result["ip"] == "192.168.1.1"
        assert job.progress == 100
        orch.create_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_setup_server(self):
        """Should setup server and update progress"""
        orch = MagicMock()
        orch.setup_server.return_value = {"success": True}

        job = Job(
            job_id="setup-test",
            job_type="setup_server",
            params={"server_name": "test-server"}
        )

        result = await execute_setup_server(job, orch)

        assert result["success"] is True
        assert job.progress == 100
```

### 3. Integration Tests

**`tests/integration/test_job_executor_integration.py`**
```python
import pytest
import asyncio
import tempfile
from pathlib import Path

from src.job_executor import JobExecutor
from src.job_manager import JobManager, JobStatus
from src.orchestrator import Orchestrator
from src.storage import StorageManager

class TestJobExecutorIntegration:
    """Integration tests with real components (mocked external APIs)"""

    @pytest.fixture
    def temp_storage(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        import shutil
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def system(self, temp_storage):
        """Setup complete system"""
        storage = StorageManager(config_dir=temp_storage)
        orchestrator = Orchestrator(config_dir=temp_storage)
        job_manager = JobManager(storage=storage)
        executor = JobExecutor(job_manager, orchestrator)

        return {
            "executor": executor,
            "job_manager": job_manager,
            "orchestrator": orchestrator
        }

    @pytest.mark.asyncio
    async def test_job_execution_end_to_end(self, system):
        """Test complete job lifecycle with executor"""
        executor = system["executor"]
        job_manager = system["job_manager"]

        # Create job
        job = job_manager.create_job(
            "create_server",
            {"name": "test", "server_type": "cx11", "location": "nbg1"}
        )

        assert job.status == JobStatus.PENDING

        # Start executor
        await executor.start()

        # Wait for job to complete
        for _ in range(20):  # Max 10 seconds
            job = job_manager.get_job(job.job_id)
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.5)

        await executor.stop()

        # Verify job completed
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100
        assert job.result is not None
```

### 4. E2E Tests (modificar existente)

**`tests/e2e/test_api_e2e_workflow.py`** - Já existe, vai passar!
```python
# Não precisa modificar - apenas rodar com executor ativo
# O executor será iniciado via lifespan do FastAPI
```

## 📁 Estrutura de Arquivos

```
src/
├── job_executor.py              # NEW - JobExecutor class
├── job_executors/               # NEW - Executor functions
│   ├── __init__.py
│   ├── server_executors.py     # create_server, setup_server, delete_server
│   └── app_executors.py         # deploy_app, undeploy_app
├── api/
│   ├── background.py            # NEW - FastAPI lifespan
│   └── server.py                # MODIFY - add lifespan
└── job_manager.py               # UNCHANGED - já tem run_job()

tests/
├── unit/
│   ├── test_job_executor.py    # NEW - Executor tests
│   └── test_job_executors.py   # NEW - Executor functions tests
├── integration/
│   └── test_job_executor_integration.py  # NEW
└── e2e/
    └── test_api_e2e_workflow.py # EXISTS - vai passar!
```

## ✅ Checklist de Implementação (TDD)

### Etapa 1: Job Executor Core
- [ ] **Task 1.1**: Criar `tests/unit/test_job_executor.py` (RED)
  - test_start_initializes_executor
  - test_stop_gracefully_stops_executor
  - test_processes_pending_jobs
  - test_handles_unknown_job_type
  - test_concurrent_job_processing

- [ ] **Task 1.2**: Criar `src/job_executor.py` (GREEN)
  - JobExecutor class
  - start() / stop() methods
  - _process_loop()
  - _process_pending_jobs()
  - _execute_job()
  - _get_executor_function()

- [ ] **Task 1.3**: Rodar testes unitários
  - `pytest tests/unit/test_job_executor.py -v`

### Etapa 2: Executor Functions
- [ ] **Task 2.1**: Criar `tests/unit/test_job_executors.py` (RED)
  - test_execute_create_server
  - test_execute_setup_server
  - test_execute_delete_server
  - test_execute_deploy_app
  - test_execute_undeploy_app
  - test_executor_handles_errors

- [ ] **Task 2.2**: Criar `src/job_executors/server_executors.py` (GREEN)
  - execute_create_server()
  - execute_setup_server()
  - execute_delete_server()

- [ ] **Task 2.3**: Criar `src/job_executors/app_executors.py` (GREEN)
  - execute_deploy_app()
  - execute_undeploy_app()

- [ ] **Task 2.4**: Rodar testes
  - `pytest tests/unit/test_job_executors.py -v`

### Etapa 3: FastAPI Integration
- [ ] **Task 3.1**: Criar `src/api/background.py`
  - lifespan() context manager
  - get_executor() function

- [ ] **Task 3.2**: Modificar `src/api/server.py`
  - Import lifespan
  - Add to FastAPI(lifespan=lifespan)

- [ ] **Task 3.3**: Testar startup/shutdown manualmente
  - `uvicorn src.api.server:app`
  - Verificar logs: "✅ Job Executor started"
  - Ctrl+C e verificar: "👋 Job Executor stopped"

### Etapa 4: Integration Tests
- [ ] **Task 4.1**: Criar `tests/integration/test_job_executor_integration.py`
  - test_job_execution_end_to_end
  - test_multiple_jobs_concurrent
  - test_job_persistence_across_restarts

- [ ] **Task 4.2**: Rodar integration tests
  - `pytest tests/integration/test_job_executor_integration.py -v`

### Etapa 5: E2E Test via API
- [ ] **Task 5.1**: Configurar environment variables
  - `export LIVCHAT_E2E_REAL=true`
  - `export HETZNER_TOKEN=...`

- [ ] **Task 5.2**: Rodar E2E test completo
  - `pytest tests/e2e/test_api_e2e_workflow.py -xvs`
  - Deve passar completamente agora!

- [ ] **Task 5.3**: Verificar cleanup
  - `export LIVCHAT_E2E_CLEANUP=true`
  - Rodar novamente e verificar servidor deletado

## 📦 Dependências Novas

Nenhuma! Tudo usa bibliotecas já instaladas:
- `asyncio` (Python stdlib)
- `FastAPI` (já temos)
- `pytest-asyncio` (já instalado)

## 🎯 Critérios de Sucesso

1. **Unit Tests**: 100% dos testes do executor passando
2. **Integration Tests**: Jobs sendo processados end-to-end
3. **E2E Test via API**: `test_api_e2e_workflow.py` passa completamente
4. **Job Lifecycle**: Jobs vão de pending → running → completed
5. **Progress Updates**: Progresso sendo atualizado em tempo real
6. **Error Handling**: Jobs falhos são marcados corretamente
7. **FastAPI Integration**: Executor inicia/para com a API

## 📊 Métricas

- **Latência de Job**: < 2s entre pending → running
- **Progress Updates**: A cada 10-30% de progresso
- **Concurrent Jobs**: Suporta 5+ jobs simultâneos
- **Error Rate**: < 1% de crashes do executor
- **Test Coverage**: > 85% para job_executor.py

## ⚠️ Considerações Importantes

### 🔄 Sincronização de Jobs
```python
# IMPORTANTE: Evitar race conditions
# JobManager.run_job() já é thread-safe por usar dicts
# Mas devemos garantir que apenas 1 executor processa cada job

async def _execute_job(self, job: Job):
    # Check if already running (outro executor pegou)
    current = self.job_manager.get_job(job.job_id)
    if current.status != JobStatus.PENDING:
        return  # Skip - já está sendo processado

    # Continue...
```

### 🚀 Performance
- Usar `asyncio.create_task()` para processar jobs em paralelo
- Não bloquear o loop principal
- Limitar concorrência se necessário (ex: max 10 jobs simultâneos)

### 🛑 Graceful Shutdown
```python
async def stop(self):
    """Para executor mas aguarda jobs em andamento"""
    self.running = False

    # Aguarda jobs running completarem (max 30s)
    timeout = 30
    start = time.time()

    while self.job_manager.list_jobs(status=JobStatus.RUNNING):
        if time.time() - start > timeout:
            logger.warning("Jobs still running after timeout")
            break
        await asyncio.sleep(1)

    if self._task:
        await self._task
```

### 📝 Logging
```python
# Logs estruturados para debugging
logger.info(f"[JobExecutor] Processing job {job.job_id} (type: {job.job_type})")
logger.info(f"[JobExecutor] Job {job.job_id} completed in {elapsed}s")
logger.error(f"[JobExecutor] Job {job.job_id} failed: {error}")
```

## 🚀 Próximos Passos Após Implementação

Com Job Executor funcionando, podemos:
1. ✅ E2E tests via API passando
2. ✅ Validar toda a arquitetura end-to-end
3. → **Etapa 9**: Implementar MCP TypeScript Server
4. → MCP vai consumir a API que já funciona completamente

## 📊 Status

- 🔵 **READY TO START**: Plan detalhado e pronto
- 📋 **Checklist**: Etapas 1-5 com tasks específicas
- 🧪 **TDD**: Testes definidos antes da implementação
- 🎯 **Critérios**: Objetivos mensuráveis definidos

---

*Plan Version: 1.0*
*Created: 2025-10-10*
*Estimated Time: ~4 horas (com TDD)*
