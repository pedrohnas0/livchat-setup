# Plan-04: API REST + MCP Gateway (v2 - Job System)

## 📋 Contexto

Referência: **CLAUDE.md Phase 4** - MCP Gateway & API REST

**Status atual da codebase:**
- ✅ Orchestrator completo (1167 linhas) - Toda lógica de orquestração
- ✅ Storage Manager (616 linhas) - Config, State, Secrets
- ✅ Providers (Hetzner) + Integrations (Portainer, Cloudflare)
- ✅ App Registry + Deployer (1046 linhas)
- ✅ CLI funcional (381 linhas) - Interface completa via terminal
- ✅ Teste E2E validado - Workflow real testado em produção
- 🟡 **API REST** - Parcialmente implementada (Etapa 1 completa - 58 testes)
- ⚪ **MCP Server** - Não existe (mcp-server/)

---

## 🔄 **JÁ IMPLEMENTADO - PRECISA REFATORAR**

### **✅ Etapa 1 Completa (System Routes):**

**Arquivos implementados:**
1. ✅ `src/api/dependencies.py` - Orchestrator singleton (7 testes ✅)
2. ✅ `src/api/models/common.py` - ErrorResponse, SuccessResponse, MessageResponse (14 testes ✅)
3. ✅ `src/api/routes/system.py` - `/`, `/health`, `/api/init` (18 testes ✅)
4. ✅ `src/api/server.py` - FastAPI app com CORS (19 testes ✅)

**Status:** **58 testes passando em 1.25s** ✅

**⚠️ O que precisa ser refatorado:**
- ❌ **NADA!** - Sistema de rotas básicas está OK
- ✅ Routes de system (/, /health, /init) são **síncronas** - CORRETO!
- ✅ Não precisam de jobs (retornam em < 1s)

**✅ Pode continuar usando routes básicas como estão!**

---

## 🚨 **PROBLEMA IDENTIFICADO**

### **Operações longas vs HTTP Timeout:**

1. **`create_server()`** - 2-5 minutos
2. **`setup_server()`** - 5-10 minutos
3. **`deploy_app()`** - 2-5 minutos por app
4. **Deploy múltiplos apps** - 10-30 minutos

**Consequências:**
- ❌ HTTP timeout (30-120s)
- ❌ MCP/Claude trava esperando
- ❌ Sem feedback de progresso
- ❌ Impossível cancelar operação

---

## 💡 **SOLUÇÃO: Job Queue System**

### **Arquitetura Assíncrona:**

```
Cliente faz POST /api/servers
         ↓
API cria JOB e retorna IMEDIATAMENTE (< 1s)
Response: {"job_id": "job_abc123", "status": "queued"}
         ↓
Background worker processa job
         ↓
Cliente faz polling GET /api/jobs/job_abc123
Response: {"status": "running", "progress": 45%, "step": "Installing Docker"}
         ↓
Job completa
GET /api/jobs/job_abc123
Response: {"status": "completed", "result": {...}}
```

---

## 📊 **Arquitetura de Rotas REST - REFATORADA**

### **Total: 24 endpoints** (18 originais + 6 jobs)

```python
# ==========================================
# 1. SYSTEM / HEALTH (3 endpoints) - SEM MUDANÇAS ✅
# ==========================================
GET    /                           # Welcome + API info + version
GET    /health                     # Health check (liveness)
POST   /api/init                   # Initialize system (~/.livchat)


# ==========================================
# 2. CONFIGURATION (2 endpoints) - SEM MUDANÇAS ✅
# ==========================================
POST   /api/config/provider        # Configure cloud provider (Hetzner/DO)
                                   # Body: { "name": "hetzner", "token": "xxx" }
                                   # Response: Síncrono (< 1s) ✅

POST   /api/config/cloudflare      # Configure Cloudflare DNS
                                   # Body: { "email": "x@y.com", "api_key": "zzz" }
                                   # Response: Síncrono (< 1s) ✅


# ==========================================
# 3. JOBS - NOVO! 🆕 (6 endpoints)
# ==========================================
GET    /api/jobs                   # List all jobs
                                   # Query: ?status=running|completed|failed
                                   # Response: {
                                   #   "jobs": [
                                   #     {
                                   #       "job_id": "job_20250110_abc",
                                   #       "type": "create_server",
                                   #       "status": "running",
                                   #       "progress": 45
                                   #     }
                                   #   ]
                                   # }

GET    /api/jobs/{job_id}          # Get job status + progress
                                   # Response: {
                                   #   "job_id": "job_20250110_abc",
                                   #   "type": "create_server",
                                   #   "status": "running",
                                   #   "progress": 45,
                                   #   "current_step": "Installing Docker",
                                   #   "steps_completed": ["Create VPS", "Setup SSH"],
                                   #   "steps_remaining": ["Install Docker", "Init Swarm"],
                                   #   "started_at": "2025-01-10T15:00:00Z",
                                   #   "estimated_completion": "2025-01-10T15:05:00Z",
                                   #   "logs": [...]
                                   # }

GET    /api/jobs/{job_id}/logs     # Get detailed job logs
                                   # Query: ?tail=100

DELETE /api/jobs/{job_id}          # Cancel job (if running)
                                   # Response: {"success": true, "message": "Job cancelled"}

POST   /api/jobs/{job_id}/retry    # Retry failed job
                                   # Response: {"job_id": "job_new_xyz", "status": "queued"}

DELETE /api/jobs                   # Cleanup old jobs
                                   # Query: ?older_than=7d&status=completed


# ==========================================
# 4. SERVERS - VPS Management (6 endpoints) - MODIFICADO! 🔄
# ==========================================
POST   /api/servers                # Create new server (ASYNC via JOB)
                                   # Body: {
                                   #   "name": "prod-01",
                                   #   "server_type": "cx21",
                                   #   "region": "nbg1",
                                   #   "image": "debian-12"
                                   # }
                                   # Response: {
                                   #   "job_id": "job_20250110_abc",
                                   #   "status": "queued",
                                   #   "message": "Server creation started",
                                   #   "check_status": "/api/jobs/job_20250110_abc"
                                   # } ✅ Retorna em < 1s!

GET    /api/servers                # List all servers (SYNC)
                                   # Response: {"servers": {...}}

GET    /api/servers/{name}         # Get server details (SYNC)

DELETE /api/servers/{name}         # Delete server (ASYNC via JOB)
                                   # Response: {"job_id": "...", "status": "queued"}

POST   /api/servers/{name}/setup   # FULL SETUP (ASYNC via JOB)
                                   # Body: {
                                   #   "ssl_email": "admin@example.com",
                                   #   "zone_name": "livchat.ai",
                                   #   "subdomain": "lab"
                                   # }
                                   # Response: {"job_id": "...", "status": "queued"}
                                   # ⏱️ Job demora ~5-10 min

POST   /api/servers/{name}/exec    # Execute SSH command (SYNC - timeout curto)
                                   # Body: {
                                   #   "command": "docker ps -a",
                                   #   "timeout": 30  # max 300s
                                   # }
                                   # Response: Síncrono (< timeout) ✅


# ==========================================
# 5. APPLICATIONS (4 endpoints) - MODIFICADO! 🔄
# ==========================================
GET    /api/apps                   # List app catalog (SYNC)

POST   /api/servers/{name}/apps    # Deploy app (ASYNC via JOB)
                                   # Body: {
                                   #   "app_name": "n8n",
                                   #   "config": {...}
                                   # }
                                   # Response: {"job_id": "...", "status": "queued"}
                                   # ⏱️ Job demora ~2-5 min por app

GET    /api/servers/{name}/apps    # List apps deployed (SYNC)

DELETE /api/servers/{name}/apps/{app_name}  # Delete app (ASYNC via JOB)
                                             # Response: {"job_id": "...", "status": "queued"}


# ==========================================
# 6. PROVIDER INFO (3 endpoints) - SEM MUDANÇAS ✅
# ==========================================
GET    /api/providers/server-types  # List available server types (SYNC)
GET    /api/providers/locations     # List available regions (SYNC)
GET    /api/providers/images        # List available OS images (SYNC)
```

---

## 🔧 **Job Status Model**

```python
class JobStatus(str, Enum):
    QUEUED = "queued"        # Job criado, esperando processar
    RUNNING = "running"      # Job em execução
    COMPLETED = "completed"  # Job finalizado com sucesso
    FAILED = "failed"        # Job falhou
    CANCELLED = "cancelled"  # Job cancelado pelo usuário

class JobResponse(BaseModel):
    job_id: str
    type: str  # create_server, setup_server, deploy_app, etc
    status: JobStatus
    progress: int = 0  # 0-100%
    current_step: Optional[str] = None
    steps_completed: List[str] = []
    steps_remaining: List[str] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    result: Optional[Dict[str, Any]] = None  # Quando completed
    error: Optional[str] = None  # Quando failed
    logs: List[Dict[str, str]] = []  # [{timestamp, level, message}, ...]
```

---

## 🏗️ **Nova Arquitetura - JobManager**

### **1. Novo módulo: `src/job_manager.py`**

```python
"""
Job Manager for long-running operations

Manages asynchronous jobs with progress tracking and cancellation
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job:
    """Represents a long-running job"""

    def __init__(self, job_id: str, job_type: str, params: Dict[str, Any]):
        self.job_id = job_id
        self.type = job_type
        self.params = params
        self.status = JobStatus.QUEUED
        self.progress = 0
        self.current_step = None
        self.steps_completed = []
        self.steps_remaining = []
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.logs = []
        self._task: Optional[asyncio.Task] = None

    def log(self, level: str, message: str):
        """Add log entry"""
        self.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message
        })
        logger.log(getattr(logging, level.upper()), f"[{self.job_id}] {message}")

    def update_progress(self, progress: int, step: str):
        """Update job progress"""
        self.progress = min(100, max(0, progress))
        self.current_step = step
        self.log("info", f"Progress: {progress}% - {step}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "job_id": self.job_id,
            "type": self.type,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "steps_completed": self.steps_completed,
            "steps_remaining": self.steps_remaining,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "logs": self.logs
        }


class JobManager:
    """
    Manages long-running jobs

    - Creates jobs and returns immediately
    - Runs jobs in background asyncio tasks
    - Updates progress in real-time
    - Persists state to storage
    """

    def __init__(self, storage_manager, orchestrator):
        self.storage = storage_manager
        self.orchestrator = orchestrator
        self.jobs: Dict[str, Job] = {}
        self._load_jobs()

    def _load_jobs(self):
        """Load jobs from state"""
        try:
            jobs_data = self.storage.state._state.get("jobs", {})
            for job_id, job_dict in jobs_data.items():
                job = Job(job_id, job_dict["type"], job_dict.get("params", {}))
                # Restore job state (but not tasks)
                job.status = JobStatus(job_dict["status"])
                job.progress = job_dict.get("progress", 0)
                job.logs = job_dict.get("logs", [])
                job.result = job_dict.get("result")
                job.error = job_dict.get("error")
                self.jobs[job_id] = job
        except Exception as e:
            logger.warning(f"Failed to load jobs: {e}")

    def _save_job(self, job: Job):
        """Save job to state"""
        if "jobs" not in self.storage.state._state:
            self.storage.state._state["jobs"] = {}

        self.storage.state._state["jobs"][job.job_id] = job.to_dict()
        self.storage.state.save()

    def create_job(self, job_type: str, params: Dict[str, Any]) -> str:
        """
        Create new job and return job_id immediately

        Args:
            job_type: Type of job (create_server, setup_server, deploy_app, etc)
            params: Job parameters

        Returns:
            job_id: Unique job identifier
        """
        job_id = f"job_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        job = Job(job_id, job_type, params)
        job.log("info", f"Job created: {job_type}")

        self.jobs[job_id] = job
        self._save_job(job)

        logger.info(f"Created job {job_id} ({job_type})")
        return job_id

    async def run_job(self, job_id: str):
        """
        Execute job in background

        This method runs in asyncio task
        """
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow().isoformat()
            job.log("info", "Job started")
            self._save_job(job)

            # Route to appropriate handler
            if job.type == "create_server":
                result = await self._run_create_server(job)
            elif job.type == "setup_server":
                result = await self._run_setup_server(job)
            elif job.type == "deploy_app":
                result = await self._run_deploy_app(job)
            elif job.type == "delete_server":
                result = await self._run_delete_server(job)
            elif job.type == "delete_app":
                result = await self._run_delete_app(job)
            else:
                raise ValueError(f"Unknown job type: {job.type}")

            # Job completed successfully
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.result = result
            job.completed_at = datetime.utcnow().isoformat()
            job.log("info", "Job completed successfully")

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.log("warning", "Job cancelled by user")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.log("error", f"Job failed: {e}")

        finally:
            self._save_job(job)

    async def _run_create_server(self, job: Job) -> Dict[str, Any]:
        """Execute create_server job"""
        params = job.params

        job.update_progress(10, "Creating VPS on cloud provider")

        # Run sync orchestrator method in thread
        server = await asyncio.to_thread(
            self.orchestrator.create_server,
            params["name"],
            params["server_type"],
            params["region"],
            params.get("image", "debian-12")
        )

        job.update_progress(100, "Server created successfully")
        return server

    async def _run_setup_server(self, job: Job) -> Dict[str, Any]:
        """Execute setup_server job with progress tracking"""
        params = job.params
        server_name = params["name"]

        # Define steps
        job.steps_remaining = [
            "Update system packages",
            "Install Docker",
            "Initialize Swarm",
            "Deploy Traefik",
            "Deploy Portainer",
            "Configure DNS"
        ]

        job.update_progress(10, "Starting server setup")

        # Wrap orchestrator to track progress
        # (Idealmente o orchestrator deveria ter callbacks de progresso)
        result = await asyncio.to_thread(
            self.orchestrator.setup_server,
            server_name,
            params.get("config", {})
        )

        # Update completed steps
        job.steps_completed = job.steps_remaining
        job.steps_remaining = []
        job.update_progress(100, "Server setup completed")

        return result

    async def _run_deploy_app(self, job: Job) -> Dict[str, Any]:
        """Execute deploy_app job"""
        params = job.params

        job.update_progress(10, f"Starting deployment of {params['app_name']}")

        result = await self.orchestrator.deploy_app(
            params["server_name"],
            params["app_name"],
            params.get("config", {})
        )

        job.update_progress(100, "App deployed successfully")
        return result

    async def _run_delete_server(self, job: Job) -> Dict[str, Any]:
        """Execute delete_server job"""
        server_name = job.params["name"]

        job.update_progress(50, "Deleting server from cloud")

        success = await asyncio.to_thread(
            self.orchestrator.delete_server,
            server_name
        )

        job.update_progress(100, "Server deleted")
        return {"success": success, "server_name": server_name}

    async def _run_delete_app(self, job: Job) -> Dict[str, Any]:
        """Execute delete_app job"""
        params = job.params

        job.update_progress(50, f"Deleting {params['app_name']}")

        result = await self.orchestrator.delete_app(
            params["server_name"],
            params["app_name"]
        )

        job.update_progress(100, "App deleted")
        return result

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        return job.to_dict()

    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status"""
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status.value == status]

        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.job_id, reverse=True)

        return [j.to_dict() for j in jobs]

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel running job"""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status != JobStatus.RUNNING:
            return False  # Can only cancel running jobs

        if job._task and not job._task.done():
            job._task.cancel()
            job.log("warning", "Cancellation requested")
            return True

        return False

    def cleanup_old_jobs(self, older_than_days: int = 7, status: Optional[str] = None):
        """Remove old completed/failed jobs"""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)

        to_delete = []
        for job_id, job in self.jobs.items():
            # Only cleanup completed/failed/cancelled
            if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                continue

            if status and job.status.value != status:
                continue

            # Check if old enough
            if job.completed_at:
                completed_time = datetime.fromisoformat(job.completed_at)
                if completed_time < cutoff:
                    to_delete.append(job_id)

        for job_id in to_delete:
            del self.jobs[job_id]
            if "jobs" in self.storage.state._state and job_id in self.storage.state._state["jobs"]:
                del self.storage.state._state["jobs"][job_id]

        if to_delete:
            self.storage.state.save()
            logger.info(f"Cleaned up {len(to_delete)} old jobs")

        return len(to_delete)
```

---

## 📁 **Estrutura de Arquivos Atualizada**

```
src/
├── __init__.py
├── orchestrator.py           # Existing
├── storage.py                # Existing
├── job_manager.py           # 🆕 NEW - Job queue system
├── api/
│   ├── __init__.py
│   ├── server.py            # ✅ Already implemented
│   ├── dependencies.py      # ✅ Already implemented + add get_job_manager()
│   ├── models/
│   │   ├── __init__.py
│   │   ├── common.py        # ✅ Already implemented
│   │   ├── job.py           # 🆕 NEW - JobResponse, JobCreate, etc
│   │   ├── server.py        # 🆕 TODO
│   │   ├── app.py           # 🆕 TODO
│   │   └── config.py        # 🆕 TODO
│   └── routes/
│       ├── __init__.py
│       ├── system.py        # ✅ Already implemented
│       ├── jobs.py          # 🆕 NEW - Job management endpoints
│       ├── config.py        # 🆕 TODO - Provider & Cloudflare config
│       ├── servers.py       # 🆕 TODO - Server management (with jobs)
│       ├── apps.py          # 🆕 TODO - App deployment (with jobs)
│       └── providers.py     # 🆕 TODO - Provider info

tests/unit/api/
├── test_dependencies.py      # ✅ Already implemented (7 tests)
├── test_models_common.py     # ✅ Already implemented (14 tests)
├── test_routes_system.py     # ✅ Already implemented (18 tests)
├── test_server.py            # ✅ Already implemented (19 tests)
├── test_job_manager.py       # 🆕 TODO - JobManager tests
├── test_models_job.py        # 🆕 TODO
├── test_routes_jobs.py       # 🆕 TODO
├── test_routes_config.py     # 🆕 TODO
├── test_routes_servers.py    # 🆕 TODO
├── test_routes_apps.py       # 🆕 TODO
└── test_routes_providers.py  # 🆕 TODO
```

---

## 🔧 **MCP Tools - Ajustados para Jobs**

```typescript
const tools = [
    // System & Config (3 tools) - SEM MUDANÇAS
    "inicializar-sistema",              // POST /api/init
    "configurar-provider",              // POST /api/config/provider
    "configurar-cloudflare",            // POST /api/config/cloudflare

    // Jobs (3 tools) - NOVO! 🆕
    "verificar-job",                    // GET /api/jobs/{job_id}
    "listar-jobs",                      // GET /api/jobs
    "aguardar-job-completo",            // Polling automático até completar

    // Servers (6 tools) - MODIFICADO para jobs
    "criar-servidor",                   // POST /api/servers → retorna job_id
    "listar-servidores",                // GET /api/servers (sync)
    "detalhes-servidor",                // GET /api/servers/{name} (sync)
    "configurar-servidor-completo",     // POST /api/servers/{name}/setup → job_id
    "executar-comando-ssh",             // POST /api/servers/{name}/exec (sync)
    "destruir-servidor",                // DELETE /api/servers/{name} → job_id

    // Apps (4 tools) - MODIFICADO para jobs
    "listar-apps-disponiveis",          // GET /api/apps (sync)
    "instalar-app",                     // POST /api/servers/{name}/apps → job_id
    "listar-apps-instaladas",           // GET /api/servers/{name}/apps (sync)
    "desinstalar-app",                  // DELETE /api/servers/{name}/apps/{app} → job_id
];

// Total: 16 tools
```

### **Exemplo de uso MCP com Jobs:**

```typescript
// Tool: criar-servidor
async function criarServidor(name: string, type: string, region: string) {
    // 1. Inicia job
    const response = await apiClient.post("/api/servers", {
        name, server_type: type, region
    });

    const jobId = response.job_id;

    // 2. Retorna job_id para usuário
    return {
        content: [{
            type: "text",
            text: `✅ Servidor ${name} em criação!\n` +
                  `📋 Job ID: ${jobId}\n` +
                  `⏳ Use 'verificar-job ${jobId}' para acompanhar o progresso.`
        }]
    };
}

// Tool: aguardar-job-completo
async function aguardarJobCompleto(jobId: string, maxWait: number = 600) {
    const startTime = Date.now();

    while (true) {
        // Check status
        const job = await apiClient.get(`/api/jobs/${jobId}`);

        if (job.status === "completed") {
            return {
                content: [{
                    type: "text",
                    text: `✅ Job ${jobId} completado!\n` +
                          `📊 Resultado: ${JSON.stringify(job.result, null, 2)}`
                }]
            };
        }

        if (job.status === "failed") {
            return {
                content: [{
                    type: "text",
                    text: `❌ Job ${jobId} falhou!\n` +
                          `💥 Erro: ${job.error}`
                }]
            };
        }

        // Check timeout
        if (Date.now() - startTime > maxWait * 1000) {
            return {
                content: [{
                    type: "text",
                    text: `⏱️ Timeout! Job ${jobId} ainda em execução.\n` +
                          `📊 Progresso: ${job.progress}% - ${job.current_step}`
                }]
            };
        }

        // Wait before next check (5 seconds)
        await new Promise(resolve => setTimeout(resolve, 5000));
    }
}
```

---

## ✅ **Checklist de Implementação - ATUALIZADO**

### **Etapa 1: API Foundation** ✅ **COMPLETA**
- [x] Task 1.1: Criar estrutura src/api/
- [x] Task 1.2: Implementar get_orchestrator() singleton
- [x] Task 1.3: Criar FastAPI app com middleware + CORS
- [x] Task 1.4: Implementar routes/system.py
- [x] Task 1.5: Testes unitários (58 testes passando) ✅

### **Etapa 2: Job Manager** 🆕
- [ ] Task 2.1: Escrever testes para JobManager (TDD)
- [ ] Task 2.2: Implementar src/job_manager.py
- [ ] Task 2.3: Adicionar get_job_manager() em dependencies.py
- [ ] Task 2.4: Testes passando

### **Etapa 3: Job Models & Routes**
- [ ] Task 3.1: Escrever testes para models/job.py
- [ ] Task 3.2: Criar models/job.py (JobResponse, JobCreate, etc)
- [ ] Task 3.3: Escrever testes para routes/jobs.py
- [ ] Task 3.4: Implementar routes/jobs.py (6 endpoints)
- [ ] Task 3.5: Testes passando

### **Etapa 4: Server Models & Routes (com Jobs)**
- [ ] Task 4.1: Escrever testes para models/server.py
- [ ] Task 4.2: Criar models/server.py
- [ ] Task 4.3: Escrever testes para routes/servers.py
- [ ] Task 4.4: Implementar routes/servers.py (usando jobs)
- [ ] Task 4.5: Testes passando

### **Etapa 5: Configuration Routes**
- [ ] Task 5.1: Escrever testes para models/config.py
- [ ] Task 5.2: Criar models/config.py
- [ ] Task 5.3: Escrever testes para routes/config.py
- [ ] Task 5.4: Implementar routes/config.py
- [ ] Task 5.5: Testes passando

### **Etapa 6: Application Routes (com Jobs)**
- [ ] Task 6.1: Escrever testes para models/app.py
- [ ] Task 6.2: Criar models/app.py
- [ ] Task 6.3: Escrever testes para routes/apps.py
- [ ] Task 6.4: Implementar routes/apps.py (usando jobs)
- [ ] Task 6.5: Testes passando

### **Etapa 7: Provider Routes**
- [ ] Task 7.1: Escrever testes para routes/providers.py
- [ ] Task 7.2: Implementar routes/providers.py
- [ ] Task 7.3: Testes passando

### **Etapa 8: Integration Tests**
- [ ] Task 8.1: Test job workflow (create → poll → complete)
- [ ] Task 8.2: Test job cancellation
- [ ] Task 8.3: Test multiple jobs in parallel
- [ ] Task 8.4: Test job persistence (restart API, jobs reload)

### **Etapa 9: MCP Server TypeScript**
- [ ] Task 9.1: Criar estrutura mcp-server/
- [ ] Task 9.2: Implementar api-client.ts
- [ ] Task 9.3: Implementar tools com polling (aguardar-job-completo)
- [ ] Task 9.4: Build + test
- [ ] Task 9.5: Publicar NPM

### **Etapa 10: E2E + Documentation**
- [ ] Task 10.1: E2E tests com real infrastructure
- [ ] Task 10.2: OpenAPI docs
- [ ] Task 10.3: README com exemplos
- [ ] Task 10.4: MCP integration guide

---

## 📊 **Métricas Atualizadas**

- **Endpoints**: 24 rotas REST (18 originais + 6 jobs)
- **MCP Tools**: 16 tools (12 originais + 4 jobs)
- **Arquivos novos**: ~30 files (15 API + 1 JobManager + 10 MCP + 4 tests)
- **LOC estimado**: ~3500 linhas
  - JobManager: ~500 linhas
  - API: ~2000 linhas
  - MCP: ~1000 linhas
- **Cobertura**: 85%+
- **Já implementado**: 58 testes ✅ (Etapa 1)

---

## 🎯 **Critérios de Sucesso Atualizados**

### API REST
1. ✅ 24 endpoints implementados e funcionando
2. ✅ JobManager funcionando com background tasks
3. ✅ Polling funciona corretamente
4. ✅ Jobs são persistidos e recuperados após restart
5. ✅ Cancelamento de jobs funciona
6. ✅ Cobertura > 85%
7. ✅ Operações longas não causam timeout

### MCP Server
1. ✅ 16 tools expostas
2. ✅ Claude consegue criar servidor e aguardar sem travar
3. ✅ Polling automático funciona
4. ✅ Feedback de progresso visível
5. ✅ Publicado em NPM

---

## 📋 **Próximos Passos**

Agora vou implementar seguindo TDD:

**Etapa 2: JobManager**
1. Escrever testes para JobManager
2. Implementar JobManager
3. Integrar com API

Quer que eu continue?

---

**Version**: 2.0.0 (Job System)
**Created**: 2025-01-10
**Updated**: 2025-01-10
**Author**: Claude Code + Pedro
**Reference**: CLAUDE.md Phase 4 + Job System Architecture
