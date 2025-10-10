# Plan-04: API REST Minimalista + MCP Gateway

## 📋 Contexto

Referência: **CLAUDE.md Phase 4** - MCP Gateway & API REST

**Status atual da codebase:**
- ✅ Orchestrator completo (1167 linhas) - Toda lógica de orquestração
- ✅ Storage Manager (616 linhas) - Config, State, Secrets
- ✅ Providers (Hetzner) + Integrations (Portainer, Cloudflare)
- ✅ App Registry + Deployer (1046 linhas)
- ✅ CLI funcional (381 linhas) - Interface completa via terminal
- ✅ Teste E2E validado - Workflow real testado em produção
- ⚪ **API REST** - Praticamente vazia (src/api/)
- ⚪ **MCP Server** - Não existe (mcp-server/)

**Aprendizados da análise:**
1. CLI já usa Orchestrator perfeitamente (cli.py linha 126)
2. Workflow validado: create → setup → deploy apps (com DNS automático)
3. API deve ser "CLI over HTTP" - mesma lógica, interface diferente
4. Orchestrator tem métodos síncronos → usar `asyncio.to_thread()` na API

---

## 🎯 Objetivo

Criar **API REST minimalista** (FastAPI) e **MCP Server TypeScript** para expor funcionalidades core do LivChatSetup via HTTP, permitindo controle completo pelo Claude AI sem sobrecarregar com tools desnecessárias.

**Princípios de Design:**
- ✅ **Minimalista**: ~18 endpoints essenciais (não 60!)
- ✅ **Baseado em E2E real**: Apenas o que foi validado
- ✅ **Agrupamento inteligente**: 1 endpoint faz múltiplas coisas
- ✅ **DNS automático**: Integrado no deploy, não manual
- ✅ **MCP enxuto**: ~12 tools (não 20+)

---

## 📊 Arquitetura de Rotas REST - FINAL

### **Total: 18 endpoints essenciais**

```python
# ==========================================
# 1. SYSTEM / HEALTH (3 endpoints)
# ==========================================
GET    /                           # Welcome + API info + version
GET    /health                     # Health check (liveness)
POST   /api/init                   # Initialize system (~/.livchat)


# ==========================================
# 2. CONFIGURATION (2 endpoints)
# ==========================================
POST   /api/config/provider        # Configure cloud provider (Hetzner/DO)
                                   # Body: { "name": "hetzner", "token": "xxx" }

POST   /api/config/cloudflare      # Configure Cloudflare DNS
                                   # Body: { "email": "x@y.com", "api_key": "zzz" }


# ==========================================
# 3. SERVERS - VPS Management (6 endpoints)
# ==========================================
POST   /api/servers                # Create new server
                                   # Body: {
                                   #   "name": "prod-01",
                                   #   "server_type": "cx21",
                                   #   "region": "nbg1",
                                   #   "image": "debian-12"
                                   # }

GET    /api/servers                # List all servers
                                   # Response: {
                                   #   "servers": {
                                   #     "prod-01": { "ip": "1.2.3.4", ... }
                                   #   }
                                   # }

GET    /api/servers/{name}         # Get server details + apps installed

DELETE /api/servers/{name}         # Delete server from cloud + state

POST   /api/servers/{name}/setup   # FULL SETUP (Docker + Swarm + Traefik + Portainer)
                                   # Body: {
                                   #   "ssl_email": "admin@example.com",
                                   #   "zone_name": "livchat.ai",  # optional
                                   #   "subdomain": "lab"          # optional
                                   # }
                                   # Este endpoint FAZ TUDO! Demora ~5min
                                   # Configura DNS automático se zone_name fornecido

POST   /api/servers/{name}/exec    # 🆕 Execute SSH command (generic diagnostic)
                                   # Body: {
                                   #   "command": "docker ps -a",
                                   #   "description": "List all containers",
                                   #   "timeout": 30,  # seconds
                                   #   "working_dir": "/opt"  # optional
                                   # }
                                   # Response: {
                                   #   "success": true,
                                   #   "exit_code": 0,
                                   #   "stdout": "...",
                                   #   "stderr": "",
                                   #   "execution_time": 1.23
                                   # }


# ==========================================
# 4. APPLICATIONS (4 endpoints)
# ==========================================
GET    /api/apps                   # List app catalog with dependencies
                                   # Query: ?category=database|automation|monitoring
                                   # Response: [
                                   #   {
                                   #     "name": "n8n",
                                   #     "category": "automation",
                                   #     "dependencies": ["postgres", "redis"],
                                   #     "dns_prefix": "edt",
                                   #     "description": "..."
                                   #   }
                                   # ]

POST   /api/servers/{name}/apps    # Deploy app to server
                                   # Body: {
                                   #   "app_name": "n8n",
                                   #   "config": {
                                   #     "basic_auth_user": "admin",
                                   #     "basic_auth_password": "secret"
                                   #   }
                                   # }
                                   # ✨ DNS configurado AUTOMATICAMENTE
                                   # ✨ Dependências resolvidas AUTOMATICAMENTE
                                   # ✨ Passwords gerados se não fornecidos

GET    /api/servers/{name}/apps    # List apps deployed on server
                                   # Response: {
                                   #   "server": "prod-01",
                                   #   "apps": ["traefik", "portainer", "postgres", "n8n"]
                                   # }

DELETE /api/servers/{name}/apps/{app_name}  # Delete app from server


# ==========================================
# 5. PROVIDER INFO (3 endpoints)
# ==========================================
GET    /api/providers/server-types  # List available server types
                                     # Response: [
                                     #   {
                                     #     "name": "cx21",
                                     #     "cores": 2,
                                     #     "memory": 4.0,
                                     #     "disk": 40,
                                     #     "price_monthly": 5.83,
                                     #     "description": "2 vCPU, 4GB RAM"
                                     #   }
                                     # ]

GET    /api/providers/locations      # List available regions
                                      # Response: [
                                      #   {
                                      #     "name": "nbg1",
                                      #     "city": "Nuremberg",
                                      #     "country": "DE",
                                      #     "description": "Nuremberg DC Park 1"
                                      #   }
                                      # ]

GET    /api/providers/images         # List available OS images
                                      # Response: [
                                      #   {
                                      #     "name": "ubuntu-22.04",
                                      #     "description": "Ubuntu 22.04 LTS",
                                      #     "os_flavor": "ubuntu"
                                      #   }
                                      # ]
```

---

## 🔧 MCP Tools Mapping

**Total: ~12 tools para Claude AI**

```typescript
const tools = [
    // System & Config (3 tools)
    "inicializar-sistema",              // POST /api/init
    "configurar-provider",              // POST /api/config/provider
    "configurar-cloudflare",            // POST /api/config/cloudflare

    // Servers (5 tools)
    "criar-servidor",                   // POST /api/servers
    "listar-servidores",                // GET /api/servers
    "detalhes-servidor",                // GET /api/servers/{name}
    "configurar-servidor-completo",     // POST /api/servers/{name}/setup
    "executar-comando-ssh",             // POST /api/servers/{name}/exec
    "destruir-servidor",                // DELETE /api/servers/{name}

    // Apps (4 tools)
    "listar-apps-disponiveis",          // GET /api/apps
    "instalar-app",                     // POST /api/servers/{name}/apps
    "listar-apps-instaladas",           // GET /api/servers/{name}/apps
    "desinstalar-app",                  // DELETE /api/servers/{name}/apps/{app}
];
```

**Nota:** Provider info (server-types, locations, images) pode ser 1 tool que retorna tudo ou ser chamado sob demanda.

---

## 📁 Estrutura de Arquivos - API REST

```
src/api/
├── __init__.py                    # FastAPI app exports
├── server.py                      # FastAPI application + middleware + CORS
├── dependencies.py                # get_orchestrator() singleton
├── models/                        # Pydantic schemas (request/response)
│   ├── __init__.py
│   ├── server.py                 # ServerCreate, ServerResponse, ServerSetup, ExecCommand
│   ├── app.py                    # AppDeploy, AppResponse, AppInfo
│   └── config.py                 # ProviderConfig, CloudflareConfig, InitResponse
└── routes/                        # Route handlers (apenas 4 arquivos!)
    ├── __init__.py
    ├── system.py                 # /, /health, /api/init
    ├── servers.py                # /api/servers/*
    ├── apps.py                   # /api/apps + /api/servers/{name}/apps
    └── providers.py              # /api/providers/*

Total: ~15 arquivos
```

---

## 📁 Estrutura de Arquivos - MCP Server

```
mcp-server/                        # Projeto TypeScript separado
├── src/
│   ├── server.ts                 # Main MCP server (baseado em /livchat-mcp validado)
│   ├── api-client.ts             # HTTP client wrapper (chama LivChatSetup API)
│   ├── tools/                    # MCP tool implementations
│   │   ├── system.ts            # System + config tools
│   │   ├── servers.ts           # Server management tools
│   │   └── apps.ts              # App deployment tools
│   ├── types.ts                  # TypeScript types
│   └── schemas.ts                # Zod schemas for validation
├── package.json                   # NPM config (@pedrohnas/livchatsetup-mcp)
├── tsconfig.json                  # TypeScript config
└── README.md                      # Usage instructions

Total: ~10 arquivos
```

---

## 🧪 Estratégia de Testes TDD

### **Unit Tests** (tests/unit/api/)
```python
test_models_validation.py          # Pydantic model validation
test_routes_system.py               # /, /health, /init
test_routes_servers.py              # /api/servers/* (mocked orchestrator)
test_routes_apps.py                 # /api/apps/* (mocked orchestrator)
test_dependencies.py                # get_orchestrator() singleton
```

**Padrão de mock correto:**
```python
@pytest.fixture
def mock_orchestrator():
    orch = Orchestrator()
    # Mock métodos que fazem I/O
    orch.create_server = Mock(return_value={"name": "test", "ip": "1.2.3.4"})
    orch.setup_server = Mock(return_value={"success": True})
    return orch

# NÃO fazer @patch('httpx.AsyncClient') - isso é unit test, não deve fazer I/O!
```

### **Integration Tests** (tests/integration/api/)
```python
test_api_server_workflow.py        # Create → setup → deploy app (mocked providers)
test_api_config_flow.py             # Init → configure → list (local storage)
test_api_ssh_exec.py                # SSH exec with mocked subprocess
```

### **E2E Tests** (tests/e2e/api/)
```python
test_api_real_workflow.py           # Full HTTP workflow with real infrastructure
                                     # Controlled by: LIVCHAT_E2E_REAL=true
```

**Métricas:**
- Unit tests: < 3 segundos total
- Integration tests: < 10 segundos
- E2E tests: < 5 minutos (quando REAL=true)
- **Coverage goal: 85%+ para API**

---

## 🏗️ Implementação Detalhada

### **1. FastAPI Server Setup**

```python
# src/api/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from .routes import system, servers, apps, providers

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LivChatSetup API",
    description="Automated infrastructure orchestration for LivChat",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(system.router, tags=["System"])
app.include_router(servers.router, prefix="/api/servers", tags=["Servers"])
app.include_router(apps.router, prefix="/api", tags=["Applications"])
app.include_router(providers.router, prefix="/api/providers", tags=["Providers"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": str(exc)}
    )

@app.on_event("startup")
async def startup():
    logger.info("🚀 LivChatSetup API starting...")

@app.on_event("shutdown")
async def shutdown():
    logger.info("👋 LivChatSetup API shutting down...")
```

---

### **2. Dependency Injection**

```python
# src/api/dependencies.py
from typing import Optional
from ..orchestrator import Orchestrator

_orchestrator: Optional[Orchestrator] = None

def get_orchestrator() -> Orchestrator:
    """
    Get or create Orchestrator singleton

    Shared between all API requests and CLI
    """
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = Orchestrator()
        _orchestrator.init()

        # Try to load existing configuration
        try:
            _orchestrator.storage.config.load()
            _orchestrator.storage.state.load()
        except Exception:
            pass  # Not initialized yet, will be on /api/init

    return _orchestrator
```

---

### **3. Pydantic Models - Exemplos**

```python
# src/api/models/server.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ServerCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, example="prod-01")
    server_type: str = Field(..., example="cx21")
    region: str = Field(..., example="nbg1")
    image: str = Field(default="debian-12", example="ubuntu-22.04")

class ServerSetup(BaseModel):
    ssl_email: str = Field(..., example="admin@example.com")
    zone_name: Optional[str] = Field(None, example="livchat.ai")
    subdomain: Optional[str] = Field(None, example="lab")
    network_name: str = Field(default="livchat_network")
    timezone: str = Field(default="UTC")

class ExecCommand(BaseModel):
    command: str = Field(..., example="docker ps -a")
    description: Optional[str] = Field(None, example="List all containers")
    timeout: int = Field(default=30, ge=1, le=300)  # 1s to 5min
    working_dir: Optional[str] = Field(None, example="/opt")

class ExecResponse(BaseModel):
    success: bool
    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float  # seconds

class ServerResponse(BaseModel):
    name: str
    id: str
    ip: str
    status: str
    server_type: str
    region: str
    created_at: str
    ssh_key: str
    applications: List[str] = []
    dns: Optional[Dict[str, Any]] = None

# src/api/models/app.py
class AppDeploy(BaseModel):
    app_name: str = Field(..., example="n8n")
    config: Dict[str, Any] = Field(default_factory=dict, example={
        "basic_auth_user": "admin",
        "basic_auth_password": "secret123"
    })

class AppResponse(BaseModel):
    success: bool
    app_name: str
    stack_id: Optional[int] = None
    dns_configured: bool = False
    dns_url: Optional[str] = None
    message: Optional[str] = None

class AppInfo(BaseModel):
    name: str
    category: str
    description: str
    dependencies: List[str]
    dns_prefix: Optional[str]
    version: str
```

---

### **4. Route Handlers - Exemplo Completo**

```python
# src/api/routes/servers.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import asyncio
import subprocess
import logging

from ..dependencies import get_orchestrator
from ..models.server import (
    ServerCreate, ServerResponse, ServerSetup,
    ExecCommand, ExecResponse
)
from ...orchestrator import Orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    data: ServerCreate,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Create a new VPS server"""
    try:
        # Call orchestrator method in thread (it's sync)
        server = await asyncio.to_thread(
            orchestrator.create_server,
            data.name,
            data.server_type,
            data.region,
            data.image
        )
        return ServerResponse(**server)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create server: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_servers(orchestrator: Orchestrator = Depends(get_orchestrator)):
    """List all managed servers"""
    servers = await asyncio.to_thread(orchestrator.list_servers)
    return {"servers": servers}

@router.get("/{name}", response_model=ServerResponse)
async def get_server(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Get server details"""
    server = await asyncio.to_thread(orchestrator.get_server, name)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")
    return ServerResponse(**server)

@router.delete("/{name}")
async def delete_server(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Delete a server"""
    success = await asyncio.to_thread(orchestrator.delete_server, name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")
    return {"success": True, "message": f"Server {name} deleted"}

@router.post("/{name}/setup")
async def setup_server(
    name: str,
    config: ServerSetup,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Run FULL server setup (Docker + Swarm + Traefik + Portainer)

    This endpoint does EVERYTHING! Takes ~5 minutes.
    DNS is configured automatically if zone_name provided.
    """
    try:
        result = await asyncio.to_thread(
            orchestrator.setup_server,
            name,
            config.dict(exclude_none=True)
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Setup failed")
            )

        return result
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{name}/exec", response_model=ExecResponse)
async def exec_command(
    name: str,
    cmd: ExecCommand,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Execute SSH command on server (generic diagnostic tool)

    Security: Uses managed SSH key, executed as root.
    All commands are logged for audit.
    """
    # Get server
    server = await asyncio.to_thread(orchestrator.get_server, name)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")

    # Get SSH key path
    ssh_key_name = server.get("ssh_key", f"{name}_key")
    ssh_key_path = orchestrator.ssh_manager.get_private_key_path(ssh_key_name)

    if not ssh_key_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"SSH key not found for server {name}"
        )

    # Log command for audit
    logger.info(f"[AUDIT] Executing on {name}: {cmd.command}")

    # Build SSH command
    ssh_cmd = [
        "ssh",
        "-i", str(ssh_key_path),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"root@{server['ip']}"
    ]

    # Add working directory if specified
    if cmd.working_dir:
        ssh_cmd.append(f"cd {cmd.working_dir} && {cmd.command}")
    else:
        ssh_cmd.append(cmd.command)

    # Execute with timeout
    import time
    start_time = time.time()

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=cmd.timeout
        )

        execution_time = time.time() - start_time

        return ExecResponse(
            success=result.returncode == 0,
            command=cmd.command,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time=execution_time
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail=f"Command timed out after {cmd.timeout}s"
        )
    except Exception as e:
        logger.error(f"Exec failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### **5. MCP Server TypeScript**

```typescript
// mcp-server/src/server.ts
#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { APIClient } from "./api-client.js";
import { systemTools, serverTools, appTools } from "./tools/index.js";

// Configuration
const API_URL = process.env.LIVCHATSETUP_API_URL || "http://localhost:8000";

// Create API client
const apiClient = new APIClient(API_URL);

// Create MCP server
const server = new Server(
  {
    name: "livchatsetup-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Register all tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    ...systemTools,
    ...serverTools,
    ...appTools
  ],
}));

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    // Route to appropriate handler
    if (name.startsWith("inicializar-")) {
      return await handleSystemTool(name, args, apiClient);
    } else if (name.includes("servidor")) {
      return await handleServerTool(name, args, apiClient);
    } else if (name.includes("app")) {
      return await handleAppTool(name, args, apiClient);
    }

    return {
      content: [{
        type: "text",
        text: `❌ Unknown tool: ${name}`
      }]
    };
  } catch (error) {
    return {
      content: [{
        type: "text",
        text: `❌ Error: ${error.message}`
      }]
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("LivChatSetup MCP Server v1.0.0 running...");
}

main().catch(console.error);
```

```typescript
// mcp-server/src/api-client.ts
export class APIClient {
  constructor(private baseURL: string) {}

  async request(method: string, path: string, body?: any): Promise<any> {
    const url = `${this.baseURL}${path}`;

    try {
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${error}`);
      throw error;
    }
  }

  // Convenience methods
  async get(path: string) {
    return this.request("GET", path);
  }

  async post(path: string, body: any) {
    return this.request("POST", path, body);
  }

  async delete(path: string) {
    return this.request("DELETE", path);
  }
}
```

---

## ✅ Checklist de Implementação

### **Etapa 1: API Foundation**
- [ ] Task 1.1: Criar estrutura src/api/ (server.py, dependencies.py)
- [ ] Task 1.2: Implementar get_orchestrator() singleton
- [ ] Task 1.3: Criar FastAPI app com middleware + CORS
- [ ] Task 1.4: Implementar routes/system.py (/, /health, /api/init)
- [ ] Task 1.5: Testes unitários para system routes

### **Etapa 2: Pydantic Models**
- [ ] Task 2.1: Criar models/server.py (ServerCreate, ServerSetup, ExecCommand, etc)
- [ ] Task 2.2: Criar models/app.py (AppDeploy, AppResponse, AppInfo)
- [ ] Task 2.3: Criar models/config.py (ProviderConfig, CloudflareConfig)
- [ ] Task 2.4: Testes de validação Pydantic

### **Etapa 3: Server Management Routes**
- [ ] Task 3.1: Implementar POST /api/servers (create)
- [ ] Task 3.2: Implementar GET /api/servers (list)
- [ ] Task 3.3: Implementar GET /api/servers/{name} (details)
- [ ] Task 3.4: Implementar DELETE /api/servers/{name}
- [ ] Task 3.5: Implementar POST /api/servers/{name}/setup
- [ ] Task 3.6: Implementar POST /api/servers/{name}/exec (SSH generic)
- [ ] Task 3.7: Testes unitários para server routes

### **Etapa 4: Configuration Routes**
- [ ] Task 4.1: Implementar POST /api/config/provider
- [ ] Task 4.2: Implementar POST /api/config/cloudflare
- [ ] Task 4.3: Testes unitários

### **Etapa 5: Application Routes**
- [ ] Task 5.1: Implementar GET /api/apps (catalog)
- [ ] Task 5.2: Implementar POST /api/servers/{name}/apps (deploy)
- [ ] Task 5.3: Implementar GET /api/servers/{name}/apps (list)
- [ ] Task 5.4: Implementar DELETE /api/servers/{name}/apps/{app}
- [ ] Task 5.5: Testes unitários para app routes

### **Etapa 6: Provider Info Routes**
- [ ] Task 6.1: Implementar GET /api/providers/server-types
- [ ] Task 6.2: Implementar GET /api/providers/locations
- [ ] Task 6.3: Implementar GET /api/providers/images
- [ ] Task 6.4: Testes unitários

### **Etapa 7: Integration Tests**
- [ ] Task 7.1: Test workflow: init → configure → create server
- [ ] Task 7.2: Test workflow: create → setup → deploy app
- [ ] Task 7.3: Test SSH exec with mocked subprocess
- [ ] Task 7.4: Test error handling (404, 500, timeouts)

### **Etapa 8: MCP Server TypeScript**
- [ ] Task 8.1: Criar estrutura mcp-server/ (package.json, tsconfig.json)
- [ ] Task 8.2: Implementar api-client.ts (HTTP wrapper)
- [ ] Task 8.3: Implementar tools/system.ts (init, configure)
- [ ] Task 8.4: Implementar tools/servers.ts (create, setup, exec, etc)
- [ ] Task 8.5: Implementar tools/apps.ts (deploy, list, delete)
- [ ] Task 8.6: Implementar server.ts (main MCP entry point)
- [ ] Task 8.7: Build + test locally
- [ ] Task 8.8: Publicar em NPM (@pedrohnas/livchatsetup-mcp)

### **Etapa 9: E2E Testing**
- [ ] Task 9.1: Test E2E via HTTP (real infrastructure if LIVCHAT_E2E_REAL=true)
- [ ] Task 9.2: Test MCP → API integration
- [ ] Task 9.3: Test Claude executing full workflow via MCP

### **Etapa 10: Documentation & Polish**
- [ ] Task 10.1: OpenAPI/Swagger docs (auto-generated)
- [ ] Task 10.2: README.md com exemplos curl
- [ ] Task 10.3: MCP README com instruções de uso no Claude Desktop
- [ ] Task 10.4: CLI command: `livchat-setup api start`
- [ ] Task 10.5: Docker image para API (opcional)

---

## 📦 Dependências

```toml
# pyproject.toml - additions
[project.dependencies]
# Existing deps...
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
```

```json
// mcp-server/package.json
{
  "name": "@pedrohnas/livchatsetup-mcp",
  "version": "1.0.0",
  "description": "MCP Server for LivChatSetup - Infrastructure orchestration via Claude AI",
  "main": "dist/server.js",
  "bin": {
    "livchatsetup-mcp": "./dist/server.js"
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.7.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@types/node": "^20.17.9",
    "typescript": "^5.7.2"
  }
}
```

---

## 🎮 Usage Examples

### **Via curl**
```bash
# 1. Initialize
curl -X POST http://localhost:8000/api/init

# 2. Configure provider
curl -X POST http://localhost:8000/api/config/provider \
  -H "Content-Type: application/json" \
  -d '{"name": "hetzner", "token": "xxx"}'

# 3. Create server
curl -X POST http://localhost:8000/api/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-01",
    "server_type": "cx21",
    "region": "nbg1"
  }'

# 4. Setup server (full)
curl -X POST http://localhost:8000/api/servers/prod-01/setup \
  -H "Content-Type: application/json" \
  -d '{
    "ssl_email": "admin@example.com",
    "zone_name": "livchat.ai",
    "subdomain": "lab"
  }'

# 5. Deploy N8N
curl -X POST http://localhost:8000/api/servers/prod-01/apps \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "n8n",
    "config": {
      "basic_auth_user": "admin",
      "basic_auth_password": "secret"
    }
  }'

# 6. Execute SSH command
curl -X POST http://localhost:8000/api/servers/prod-01/exec \
  -H "Content-Type: application/json" \
  -d '{
    "command": "docker ps",
    "timeout": 30
  }'
```

### **Via MCP (Claude Desktop)**
```json
// Claude Desktop config: ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "livchatsetup": {
      "command": "npx",
      "args": ["@pedrohnas/livchatsetup-mcp"],
      "env": {
        "LIVCHATSETUP_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Then in Claude:
```
User: "Create a server named prod-01 using cx21 in Nuremberg"

Claude: [Uses tool "criar-servidor"]
✅ Server prod-01 created at IP 1.2.3.4

User: "Set it up completely with SSL for admin@example.com"

Claude: [Uses tool "configurar-servidor-completo"]
✅ Server setup completed! Docker, Swarm, Traefik, and Portainer deployed.

User: "Install N8N with basic auth admin/secret123"

Claude: [Uses tool "instalar-app"]
✅ N8N deployed! Access at https://edt.lab.livchat.ai

User: "Show me all running containers"

Claude: [Uses tool "executar-comando-ssh" with "docker ps"]
Here are the containers:
- traefik
- portainer
- postgres
- redis
- n8n
```

---

## 🎯 Critérios de Sucesso

### API REST
1. ✅ 18 endpoints implementados e funcionando
2. ✅ Cobertura de testes > 85%
3. ✅ OpenAPI/Swagger docs completo
4. ✅ Validação Pydantic em todos os requests
5. ✅ Error handling padronizado (400, 404, 500, 408)
6. ✅ Orchestrator singleton funcionando
7. ✅ SSH exec genérico funcionando

### MCP Server
1. ✅ 12 tools expostas para Claude
2. ✅ API client HTTP funcional
3. ✅ Publicado em NPM com sucesso
4. ✅ Claude Desktop integration working
5. ✅ Claude consegue executar workflow completo (create → setup → deploy)

### Integration
1. ✅ CLI, API e MCP usam o MESMO Orchestrator
2. ✅ State persistido corretamente
3. ✅ Workflow E2E funciona via API e MCP

---

## 📊 Métricas

- **Endpoints**: 18 rotas REST
- **MCP Tools**: 12 tools
- **Arquivos novos**: ~25 files
- **LOC estimado**: ~2500 linhas
  - API: ~1500 linhas
  - MCP: ~1000 linhas
- **Cobertura**: 85%+
- **Tempo de implementação**: Etapas 1-10

---

## ⚠️ Considerações Importantes

### 1. **Async vs Sync**
```python
# Orchestrator methods são síncronos
# FastAPI routes são async

# Solução: asyncio.to_thread()
result = await asyncio.to_thread(orchestrator.create_server, ...)
```

### 2. **Singleton Pattern**
```python
# dependencies.py garante 1 instância do Orchestrator
# Compartilhado entre todas as requests
# CLI também pode usar o mesmo (se rodar no mesmo processo)
```

### 3. **SSH Exec Security**
- ✅ Usa SSH key gerenciada (não aceita custom keys)
- ✅ Timeout obrigatório (1s-300s)
- ✅ Log de auditoria para todas as execuções
- ⚠️ Executa como root (cuidado com comandos destrutivos!)
- ⚠️ Considerar whitelist de comandos em produção

### 4. **Error Handling**
```python
# ValueError → 400 Bad Request
# KeyError/NotFound → 404 Not Found
# TimeoutExpired → 408 Request Timeout
# RuntimeError → 500 Internal Server Error
```

### 5. **MCP + API Separation**
- MCP é projeto SEPARADO (TypeScript)
- Comunicação APENAS via HTTP (não imports Python)
- API deve rodar antes de usar MCP

---

## 🚀 Próximos Passos (Phase 5)

Após Phase 4 completa:
1. **Monitoring endpoints** (/api/metrics, /api/logs)
2. **WebSocket support** (real-time updates)
3. **Rollback operations**
4. **Deployment history tracking**
5. **Web Dashboard** (React/Vue)

---

## 📊 Status

- 🔵 **READY TO START**
- Aprovado pelo usuário: ✅
- Aguardando: Implementação

---

**Version**: 1.0.0
**Created**: 2025-01-10
**Author**: Claude Code + Pedro
**Reference**: CLAUDE.md Phase 4
