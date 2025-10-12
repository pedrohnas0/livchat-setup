# Plan-06: MCP Server Implementation

## 📋 Contexto

Referência: **CLAUDE.md Phase 4** - MCP Gateway

**Status atual da codebase:**
- ✅ API REST completa (27 endpoints, 172 testes passing)
- ✅ Job Executor funcionando (jobs executam em background)
- ✅ E2E workflow validado
- ⚪ **MCP Server** - Não existe (mcp-server/)

**Problemas identificados:**
1. ❌ **Endpoints para Vault não existem** - Apenas config.yaml tem API
2. ✅ **DNS configuration existe** - Mas precisa de endpoint para associar ao servidor

---

## 🎯 Objetivo

Implementar **MCP Server TypeScript** publicável em NPM com:
- **14 tools** otimizadas (config, secrets, providers, servers, apps, jobs)
- **Nomenclatura em inglês**, descrições em português
- **Tratamento de erros padronizado** com instruções claras para AI
- **Polling opcional** (wait-for-job não bloqueia por padrão)
- **Cobertura 100%** da API REST (27 endpoints)

---

## 📊 Escopo Definitivo

### **Novos Endpoints API** [A DESENVOLVER]

#### 1. Secrets Management (Vault)
```python
# src/api/routes/secrets.py - NOVO

GET    /api/secrets              # List secret keys (sem valores!)
GET    /api/secrets/{key}        # Get secret value
PUT    /api/secrets/{key}        # Set secret value
DELETE /api/secrets/{key}        # Remove secret
```

#### 2. Server DNS Configuration
```python
# src/api/routes/servers.py - ADICIONAR

POST   /api/servers/{name}/dns   # Associate zone/subdomain to server
GET    /api/servers/{name}/dns   # Get DNS config for server
```

---

### **MCP Tools Schema - 14 Tools**

#### **🔧 1. CONFIGURAÇÃO & SECRETS (2 tools)**

```typescript
// ========================================
// Tool 1: manage-config
// ========================================
{
  name: "manage-config",
  description: "Gerencia configurações não-sensíveis do sistema (YAML em ~/.livchat/config.yaml). Exemplos: region padrão, server_type, admin_email, timezone. Use operation='get' para obter ou operation='set' para definir. Suporta notação de ponto (ex: 'defaults.region'). ATENÇÃO: Para dados sensíveis (tokens, passwords), use 'manage-secrets'.",
  inputSchema: {
    type: "object",
    properties: {
      operation: {
        type: "string",
        enum: ["get", "set"],
        description: "Operação: 'get' para obter, 'set' para definir"
      },
      key: {
        type: "string",
        description: "Chave de configuração (notação de ponto, ex: 'defaults.timezone')"
      },
      value: {
        description: "Valor a definir (apenas para operation='set')"
      }
    },
    required: ["operation", "key"],
    if: {
      properties: { operation: { const: "set" } }
    },
    then: {
      required: ["value"]
    }
  }
}
// Endpoints: GET/PUT /api/config/{key}

// ========================================
// Tool 2: manage-secrets [NOVO - API A DESENVOLVER]
// ========================================
{
  name: "manage-secrets",
  description: "Gerencia credenciais sensíveis CRIPTOGRAFADAS no Ansible Vault (~/.livchat/credentials.vault). Use para: tokens de API (Hetzner, Cloudflare), passwords de apps, SSH keys. CRÍTICO: Esta é a ÚNICA forma de configurar providers - hetzner_token DEVE estar no vault para criar servidores. Operações: 'get' (retorna valor decriptado), 'set' (salva criptografado), 'list' (lista chaves sem valores), 'delete' (remove secret).",
  inputSchema: {
    type: "object",
    properties: {
      operation: {
        type: "string",
        enum: ["get", "set", "list", "delete"],
        description: "Operação no vault: 'list' (lista keys), 'get' (obtém valor), 'set' (define), 'delete' (remove)"
      },
      key: {
        type: "string",
        description: "Nome do secret (ex: 'hetzner_token', 'cloudflare_api_key'). Obrigatório para get/set/delete"
      },
      value: {
        type: "string",
        description: "Valor do secret (apenas para operation='set')"
      }
    },
    required: ["operation"],
    allOf: [
      {
        if: {
          properties: { operation: { enum: ["get", "delete"] } }
        },
        then: {
          required: ["key"]
        }
      },
      {
        if: {
          properties: { operation: { const: "set" } }
        },
        then: {
          required: ["key", "value"]
        }
      }
    ]
  }
}
// Endpoints: GET/PUT/DELETE /api/secrets/{key}, GET /api/secrets
```

---

#### **☁️ 2. PROVIDERS (1 tool)**

```typescript
// ========================================
// Tool 3: get-provider-info
// ========================================
{
  name: "get-provider-info",
  description: "Obtém informações de provedores de nuvem (Hetzner, etc). info_type: 'overview' (status/configuração), 'regions' (datacenters disponíveis), 'server-types' (CPU/RAM/preço), 'all' (tudo). IMPORTANTE: Provider DEVE estar configurado com token no vault antes de consultar regions/server-types. Use 'manage-secrets' com key='hetzner_token' primeiro.",
  inputSchema: {
    type: "object",
    properties: {
      provider: {
        type: "string",
        enum: ["hetzner"],
        description: "Nome do provedor de nuvem"
      },
      info_type: {
        type: "string",
        enum: ["overview", "regions", "server-types", "all"],
        default: "all",
        description: "'overview'=status, 'regions'=datacenters, 'server-types'=tamanhos, 'all'=tudo"
      }
    },
    required: ["provider"]
  }
}
// Endpoints:
// - overview: GET /api/providers/{provider}
// - regions: GET /api/providers/{provider}/regions
// - server-types: GET /api/providers/{provider}/server-types
// - all: chama os 3 acima
```

---

#### **🖥️ 3. SERVIDORES (5 tools - 3 async)**

```typescript
// ========================================
// Tool 4: create-server 🔄 ASYNC
// ========================================
{
  name: "create-server",
  description: "Cria novo servidor VPS no provedor de nuvem. **OPERAÇÃO ASSÍNCRONA** (~2-5 min) - retorna job_id para acompanhar via 'get-job-status'. PRÉ-REQUISITO: Provider configurado com token no vault ('manage-secrets' com key='hetzner_token'). VALIDAÇÃO: Antes de executar, use 'get-provider-info' para obter server_type e region válidos.",
  inputSchema: {
    type: "object",
    properties: {
      name: {
        type: "string",
        description: "Nome único do servidor (apenas lowercase, números e hífens, ex: 'prod-01')",
        pattern: "^[a-z0-9-]+$",
        minLength: 3,
        maxLength: 50
      },
      server_type: {
        type: "string",
        description: "Tipo do servidor (ex: 'cx11', 'cx21'). IMPORTANTE: Consulte valores válidos via 'get-provider-info' com info_type='server-types' ANTES de executar"
      },
      region: {
        type: "string",
        description: "Região/datacenter (ex: 'nbg1', 'fsn1'). IMPORTANTE: Consulte valores válidos via 'get-provider-info' com info_type='regions' ANTES de executar"
      },
      image: {
        type: "string",
        description: "Imagem do SO (padrão: 'debian-12')",
        default: "debian-12"
      }
    },
    required: ["name", "server_type", "region"]
  }
}
// Endpoint: POST /api/servers (202 Accepted)
// Erros:
// - "Provider not configured" → Instrução: Use 'manage-secrets' para definir 'hetzner_token'
// - "Invalid server_type" → Instrução: Use 'get-provider-info' para ver tipos válidos
// - "Invalid region" → Instrução: Use 'get-provider-info' para ver regiões válidas

// ========================================
// Tool 5: list-servers
// ========================================
{
  name: "list-servers",
  description: "Lista servidores gerenciados. Se server_name fornecido, retorna detalhes do servidor específico (IP, status, apps instaladas, DNS config). Use include_details=true para informações completas de todos os servidores.",
  inputSchema: {
    type: "object",
    properties: {
      server_name: {
        type: "string",
        description: "Nome do servidor específico (opcional)"
      },
      include_details: {
        type: "boolean",
        description: "Incluir detalhes completos (padrão: false)",
        default: false
      }
    },
    required: []
  }
}
// Endpoints: GET /api/servers ou GET /api/servers/{name}

// ========================================
// Tool 6: configure-server-dns [NOVO - API A DESENVOLVER]
// ========================================
{
  name: "configure-server-dns",
  description: "Associa configuração DNS a um servidor existente. Define o domínio principal (zone_name, ex: 'livchat.ai') e subdomain opcional (ex: 'lab', 'dev', 'ops') que serão usados por todas as aplicações instaladas neste servidor. PRÉ-REQUISITO: Cloudflare deve estar configurado ('manage-secrets' com 'cloudflare_email' e 'cloudflare_api_key'). Esta configuração é SALVA NO STATE do servidor e usada automaticamente em deploys futuros.",
  inputSchema: {
    type: "object",
    properties: {
      server_name: {
        type: "string",
        description: "Nome do servidor"
      },
      zone_name: {
        type: "string",
        description: "Domínio principal registrado no Cloudflare (ex: 'livchat.ai', 'example.com')"
      },
      subdomain: {
        type: "string",
        description: "Subdomain preferido para este servidor (opcional, ex: 'lab', 'dev', 'prod'). Apps usarão pattern: {app}.{subdomain}.{zone_name} (ex: n8n.lab.livchat.ai)"
      }
    },
    required: ["server_name", "zone_name"]
  }
}
// Endpoint: POST /api/servers/{name}/dns (NOVO - A DESENVOLVER)

// ========================================
// Tool 7: setup-server 🔄 ASYNC
// ========================================
{
  name: "setup-server",
  description: "Executa configuração completa do servidor: atualiza sistema, instala Docker, inicializa Swarm, deploy Traefik + Portainer. **OPERAÇÃO ASSÍNCRONA** (~5-10 min). PRÉ-REQUISITO: Servidor já criado via 'create-server' e job concluído. RECOMENDAÇÃO: Configure DNS antes do setup via 'configure-server-dns' para obter certificados SSL automaticamente.",
  inputSchema: {
    type: "object",
    properties: {
      server_name: {
        type: "string",
        description: "Nome do servidor a configurar"
      },
      ssl_email: {
        type: "string",
        format: "email",
        description: "Email para certificados SSL Let's Encrypt (opcional)",
        default: "admin@example.com"
      },
      network_name: {
        type: "string",
        description: "Nome da rede Docker Swarm overlay (padrão: 'livchat_network')",
        default: "livchat_network"
      },
      timezone: {
        type: "string",
        description: "Timezone do servidor (padrão: 'America/Sao_Paulo' - horário de São Paulo UTC-3)",
        default: "America/Sao_Paulo"
      }
    },
    required: ["server_name"]
  }
}
// Endpoint: POST /api/servers/{name}/setup (202 Accepted)

// ========================================
// Tool 8: delete-server 🔄 ASYNC
// ========================================
{
  name: "delete-server",
  description: "Deleta servidor do provedor de nuvem e remove do estado. **OPERAÇÃO IRREVERSÍVEL e ASSÍNCRONA** (~1-2 min). ATENÇÃO: Todos os dados e aplicações serão perdidos permanentemente. Requer confirmação explícita do usuário com confirm=true.",
  inputSchema: {
    type: "object",
    properties: {
      server_name: {
        type: "string",
        description: "Nome do servidor a deletar"
      },
      confirm: {
        type: "boolean",
        description: "Confirmação obrigatória: true apenas se usuário confirmou explicitamente a deleção após ser alertado sobre irreversibilidade",
        const: true
      }
    },
    required: ["server_name", "confirm"]
  }
}
// Endpoint: DELETE /api/servers/{name} (202 Accepted)
```

---

#### **📦 4. APLICAÇÕES (4 tools - 2 async)**

```typescript
// ========================================
// Tool 9: list-apps
// ========================================
{
  name: "list-apps",
  description: "Lista aplicações disponíveis no catálogo (PostgreSQL, Redis, N8N, Chatwoot, etc). Se app_name fornecido, retorna detalhes completos (dependências, requisitos, variáveis). Pode filtrar por category (databases, applications, infrastructure).",
  inputSchema: {
    type: "object",
    properties: {
      app_name: {
        type: "string",
        description: "Nome da aplicação específica (opcional)"
      },
      category: {
        type: "string",
        enum: ["databases", "applications", "infrastructure"],
        description: "Filtrar por categoria (opcional)"
      }
    },
    required: []
  }
}
// Endpoints: GET /api/apps ou GET /api/apps/{name}

// ========================================
// Tool 10: deploy-app 🔄 ASYNC
// ========================================
{
  name: "deploy-app",
  description: "Instala aplicação em um servidor. Resolve e instala dependências automaticamente (ex: N8N instala PostgreSQL e Redis primeiro). **OPERAÇÃO ASSÍNCRONA** (~2-5 min por app). PRÉ-REQUISITOS: 1) Servidor configurado via 'setup-server', 2) Para DNS automático, use 'configure-server-dns' antes. O sistema usará DNS config do servidor (zone + subdomain) automaticamente se configurado.",
  inputSchema: {
    type: "object",
    properties: {
      app_name: {
        type: "string",
        description: "Nome da aplicação (ex: 'postgres', 'redis', 'n8n'). Use 'list-apps' para ver opções"
      },
      server_name: {
        type: "string",
        description: "Nome do servidor. Use 'list-servers' para ver servidores disponíveis"
      },
      environment: {
        type: "object",
        description: "Variáveis de ambiente customizadas (opcional)",
        additionalProperties: true
      }
    },
    required: ["app_name", "server_name"]
  }
}
// Endpoint: POST /api/apps/{name}/deploy (202 Accepted)

// ========================================
// Tool 11: undeploy-app 🔄 ASYNC
// ========================================
{
  name: "undeploy-app",
  description: "Remove aplicação de um servidor. **OPERAÇÃO ASSÍNCRONA** (~1-2 min). ATENÇÃO: Dados da aplicação serão perdidos. Requer confirmação explícita do usuário com confirm=true.",
  inputSchema: {
    type: "object",
    properties: {
      app_name: {
        type: "string",
        description: "Nome da aplicação a remover"
      },
      server_name: {
        type: "string",
        description: "Nome do servidor"
      },
      confirm: {
        type: "boolean",
        description: "Confirmação obrigatória: true apenas se usuário confirmou explicitamente",
        const: true
      }
    },
    required: ["app_name", "server_name", "confirm"]
  }
}
// Endpoint: POST /api/apps/{name}/undeploy (202 Accepted)

// ========================================
// Tool 12: list-deployed-apps
// ========================================
{
  name: "list-deployed-apps",
  description: "Lista aplicações instaladas em um servidor específico com status, domínios e informações de deployment.",
  inputSchema: {
    type: "object",
    properties: {
      server_name: {
        type: "string",
        description: "Nome do servidor"
      }
    },
    required: ["server_name"]
  }
}
// Endpoint: GET /api/servers/{server_name}/apps
```

---

#### **⏱️ 5. JOBS (2 tools - 1 opcional)**

```typescript
// ========================================
// Tool 13: get-job-status
// ========================================
{
  name: "get-job-status",
  description: "Verifica status de um job: pending (aguardando), running (executando), completed (concluído), failed (falhou), cancelled. Retorna progresso (0-100%), step atual e logs recentes se solicitado.",
  inputSchema: {
    type: "object",
    properties: {
      job_id: {
        type: "string",
        description: "ID do job retornado por operações assíncronas"
      },
      tail_logs: {
        type: "number",
        description: "Qtd de linhas de log: 0=todas, 50, 100, null=sem logs (padrão: null para economizar tokens)",
        enum: [0, 50, 100, null],
        default: null
      }
    },
    required: ["job_id"]
  }
}
// Endpoint: GET /api/jobs/{job_id}

// ========================================
// Tool 14: list-jobs
// ========================================
{
  name: "list-jobs",
  description: "Lista jobs com filtros opcionais. Útil para ver histórico de operações.",
  inputSchema: {
    type: "object",
    properties: {
      status: {
        type: "string",
        enum: ["pending", "running", "completed", "failed", "cancelled"],
        description: "Filtrar por status (opcional)"
      },
      limit: {
        type: "number",
        description: "Máximo de jobs (padrão: 100, máx: 1000)",
        minimum: 1,
        maximum: 1000,
        default: 100
      }
    },
    required: []
  }
}
// Endpoint: GET /api/jobs
```

**NOTA sobre wait-for-job:**
❌ **REMOVIDA** - Polling bloqueia a AI. Melhor UX: usuário executa operação async e verifica depois com `get-job-status`.

---

## 🧪 Estratégia de Testes TDD

### 1. Unit Tests - API Client
**`tests/unit/mcp/test_api_client.ts`** (RED → GREEN)
```typescript
describe('APIClient', () => {
  test('should make GET request', async () => {
    const client = new APIClient('http://localhost:8000');
    const response = await client.get('/health');
    expect(response.status).toBe('ok');
  });

  test('should handle 404 errors with instructions', async () => {
    const client = new APIClient('http://localhost:8000');
    await expect(client.get('/api/servers/invalid'))
      .rejects.toMatchObject({
        code: 'SERVER_NOT_FOUND',
        instruction: expect.stringContaining('list-servers')
      });
  });
});
```

### 2. Unit Tests - Tools
**`tests/unit/mcp/test_tools.ts`** (RED → GREEN)
```typescript
describe('MCP Tools', () => {
  test('manage-secrets tool should set secret', async () => {
    const tool = getToolHandler('manage-secrets');
    const result = await tool({
      operation: 'set',
      key: 'hetzner_token',
      value: 'test_token_123'
    });

    expect(result.content[0].text).toContain('Secret salvo com sucesso');
  });

  test('create-server tool should return job_id', async () => {
    const tool = getToolHandler('create-server');
    const result = await tool({
      name: 'test-server',
      server_type: 'cx11',
      region: 'nbg1'
    });

    expect(result.content[0].text).toContain('job_id');
  });
});
```

### 3. Integration Tests
**`tests/integration/mcp/test_mcp_workflows.ts`**
```typescript
describe('MCP Workflows', () => {
  test('complete server creation workflow', async () => {
    // 1. Configure provider
    await executeTool('manage-secrets', {
      operation: 'set',
      key: 'hetzner_token',
      value: process.env.HETZNER_TOKEN
    });

    // 2. Create server
    const createResult = await executeTool('create-server', {
      name: 'test-e2e',
      server_type: 'cx11',
      region: 'nbg1'
    });

    const jobId = extractJobId(createResult);

    // 3. Check job status
    const jobResult = await executeTool('get-job-status', {
      job_id: jobId,
      tail_logs: 50
    });

    expect(jobResult).toMatchObject({
      status: 'completed',
      progress: 100
    });
  });
});
```

---

## 📁 Estrutura de Arquivos

```
mcp-server/                       # TypeScript MCP Server
├── src/
│   ├── index.ts                 # Entry point + MCP server setup
│   ├── api-client.ts            # HTTP client para API REST
│   ├── error-handler.ts         # Tratamento padronizado de erros
│   ├── tools/
│   │   ├── index.ts             # Tool registry
│   │   ├── config.ts            # manage-config tool
│   │   ├── secrets.ts           # manage-secrets tool [NOVO]
│   │   ├── providers.ts         # get-provider-info tool
│   │   ├── servers.ts           # 5 server tools (create, list, dns, setup, delete)
│   │   ├── apps.ts              # 4 app tools (list, deploy, undeploy, list-deployed)
│   │   └── jobs.ts              # 2 job tools (get-status, list)
│   └── types/
│       ├── api.ts               # API response types
│       ├── tools.ts             # Tool input/output types
│       └── errors.ts            # Error types
│
├── tests/
│   ├── unit/
│   │   ├── api-client.test.ts
│   │   └── tools.test.ts
│   ├── integration/
│   │   └── workflows.test.ts
│   └── fixtures/
│       └── mock-responses.ts
│
├── package.json                 # NPM config + dependencies
├── tsconfig.json                # TypeScript config
├── jest.config.js               # Test config
└── README.md                    # Usage documentation

src/api/                          # Python API - Novos endpoints
├── routes/
│   ├── secrets.py               # [NOVO] Vault management
│   └── servers.py               # [ADICIONAR] DNS endpoint
└── models/
    └── secrets.py               # [NOVO] Secret models
```

---

## ✅ Checklist de Implementação (TDD)

### Etapa 1: API - Secrets Endpoint
- [ ] **Task 1.1**: Escrever testes para `src/api/routes/secrets.py` (RED)
  - test_list_secret_keys
  - test_get_secret_value
  - test_set_secret
  - test_delete_secret
  - test_secret_not_found_error

- [ ] **Task 1.2**: Criar models `src/api/models/secrets.py`
  - SecretListResponse
  - SecretGetResponse
  - SecretSetRequest/Response
  - SecretDeleteResponse

- [ ] **Task 1.3**: Implementar `src/api/routes/secrets.py` (GREEN)
  - GET /api/secrets (list keys only)
  - GET /api/secrets/{key} (get value)
  - PUT /api/secrets/{key} (set value)
  - DELETE /api/secrets/{key} (remove)

- [ ] **Task 1.4**: Rodar testes unitários API
  - `pytest tests/unit/api/test_routes_secrets.py -v`

### Etapa 2: API - Server DNS Endpoint
- [ ] **Task 2.1**: Escrever testes para DNS endpoint (RED)
  - test_configure_server_dns
  - test_get_server_dns_config
  - test_dns_requires_cloudflare

- [ ] **Task 2.2**: Adicionar em `src/api/routes/servers.py`
  - POST /api/servers/{name}/dns
  - GET /api/servers/{name}/dns

- [ ] **Task 2.3**: Rodar testes
  - `pytest tests/unit/api/test_routes_servers.py -v`

### Etapa 3: MCP - Setup TypeScript Project
- [ ] **Task 3.1**: Criar estrutura mcp-server/
  - package.json com dependencies
  - tsconfig.json
  - jest.config.js

- [ ] **Task 3.2**: Instalar dependencies
  - `@modelcontextprotocol/sdk`
  - `zod` para validação
  - `jest` + `ts-jest` para testes
  - `@types/node`

- [ ] **Task 3.3**: Configurar build
  - Script build no package.json
  - Bin entry point

### Etapa 4: MCP - API Client
- [ ] **Task 4.1**: Escrever testes para APIClient (RED)
  - test_make_get_request
  - test_make_post_request
  - test_handle_404_errors
  - test_handle_500_errors
  - test_parse_error_instructions

- [ ] **Task 4.2**: Implementar `src/api-client.ts` (GREEN)
  - Class APIClient
  - Methods: get(), post(), put(), delete()
  - Error parsing with instructions

- [ ] **Task 4.3**: Rodar testes
  - `npm test -- api-client`

### Etapa 5: MCP - Error Handler
- [ ] **Task 5.1**: Escrever testes para ErrorHandler (RED)
  - test_parse_api_error
  - test_format_error_for_ai
  - test_extract_instructions

- [ ] **Task 5.2**: Implementar `src/error-handler.ts` (GREEN)
  - Interface MCPError
  - parseAPIError()
  - formatForAI()

- [ ] **Task 5.3**: Rodar testes
  - `npm test -- error-handler`

### Etapa 6: MCP - Tools Implementation (14 tools)
- [ ] **Task 6.1**: Implementar tools/config.ts
  - manage-config tool
  - Zod schema validation
  - Testes unitários

- [ ] **Task 6.2**: Implementar tools/secrets.ts [NOVO]
  - manage-secrets tool (4 operations: get, set, list, delete)
  - Zod schema validation
  - Testes unitários

- [ ] **Task 6.3**: Implementar tools/providers.ts
  - get-provider-info tool
  - info_type switch (overview, regions, server-types, all)
  - Testes unitários

- [ ] **Task 6.4**: Implementar tools/servers.ts
  - create-server (async)
  - list-servers
  - configure-server-dns [NOVO]
  - setup-server (async)
  - delete-server (async)
  - Testes unitários

- [ ] **Task 6.5**: Implementar tools/apps.ts
  - list-apps
  - deploy-app (async)
  - undeploy-app (async)
  - list-deployed-apps
  - Testes unitários

- [ ] **Task 6.6**: Implementar tools/jobs.ts
  - get-job-status
  - list-jobs
  - Testes unitários

- [ ] **Task 6.7**: Criar tool registry em tools/index.ts
  - Export all tools
  - Tool metadata

### Etapa 7: MCP - Server Setup
- [ ] **Task 7.1**: Implementar `src/index.ts`
  - McpServer initialization
  - Register all 14 tools
  - StdioServerTransport
  - Error handling

- [ ] **Task 7.2**: Testar server startup
  - `npm run build`
  - `node dist/index.js`
  - Verificar logs

### Etapa 8: Integration Tests
- [ ] **Task 8.1**: Test complete workflows
  - Workflow: Configure provider → Create server → Setup
  - Workflow: Deploy app with dependencies
  - Workflow: Job status tracking

- [ ] **Task 8.2**: Test error scenarios
  - Missing provider token
  - Invalid server type
  - Server not found
  - Job not found

- [ ] **Task 8.3**: Rodar integration tests
  - `npm test -- integration`

### Etapa 9: Documentation
- [ ] **Task 9.1**: Criar README.md completo
  - Installation
  - Configuration (API_URL, API_KEY)
  - Usage examples
  - Tool reference

- [ ] **Task 9.2**: Criar CHANGELOG.md
  - Version 1.0.0
  - Initial release

- [ ] **Task 9.3**: Criar package.json metadata
  - Description
  - Keywords
  - Repository
  - License (MIT)

### Etapa 10: NPM Package
- [ ] **Task 10.1**: Preparar para publicação
  - Versão 1.0.0
  - Build final
  - Test installation local

- [ ] **Task 10.2**: Publicar no NPM
  - `npm publish --access public`
  - Verificar em npmjs.com

- [ ] **Task 10.3**: Testar instalação
  - `npx @livchat/setup-mcp`
  - Verificar funcionamento

---

## 📦 Dependências Novas

### Python API
```txt
# Nenhuma - Usa bibliotecas existentes
```

### TypeScript MCP
```json
{
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "zod": "^3.22.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.3.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.0",
    "@types/jest": "^29.5.0"
  }
}
```

---

## 🎯 Critérios de Sucesso

### API Python
1. ✅ Endpoint /api/secrets/* funcionando (GET, PUT, DELETE)
2. ✅ Endpoint /api/servers/{name}/dns funcionando (POST, GET)
3. ✅ Testes unitários passando (100% cobertura novos endpoints)
4. ✅ Erros retornam com formato padronizado + instruções

### MCP TypeScript
1. ✅ 14 tools implementadas e funcionando
2. ✅ Nomenclatura: tools em inglês, descrições em PT-BR
3. ✅ Tratamento de erros com instruções claras
4. ✅ APIClient faz requests corretamente
5. ✅ Testes unitários passando (> 85% cobertura)
6. ✅ Integration tests passando
7. ✅ Pacote publicado no NPM como `@livchat/setup-mcp`
8. ✅ Claude consegue usar via MCP config

### Validação End-to-End
1. ✅ Configurar Hetzner token via manage-secrets
2. ✅ Listar server types via get-provider-info
3. ✅ Criar servidor via create-server
4. ✅ Verificar job via get-job-status
5. ✅ Configurar DNS via configure-server-dns
6. ✅ Setup completo via setup-server
7. ✅ Deploy app via deploy-app
8. ✅ Verificar app instalada via list-deployed-apps

---

## 📊 Métricas

### API
- **Novos Endpoints**: 6 (4 secrets + 2 DNS)
- **Total Endpoints**: 33 (27 existentes + 6 novos)
- **Cobertura Testes**: > 85%

### MCP
- **Total Tools**: 14
- **LOC Estimado**: ~2000 linhas TypeScript
- **Bundle Size**: < 100KB
- **Startup Time**: < 1s
- **Memory Usage**: < 50MB

---

## ⚠️ Considerações Importantes

### Segurança
1. **Vault**: Secrets são criptografados com Ansible Vault
2. **API Key**: Suporte opcional para autenticação
3. **Logs**: Nunca logar valores de secrets
4. **Transport**: MCP usa stdio (seguro para uso local)

### Performance
1. **Async Tools**: 5 tools retornam job_id imediatamente
2. **Polling**: Removido para não bloquear AI
3. **Caching**: APIClient pode cachear GET requests

### UX
1. **Erros**: Sempre incluem instruções sobre próxima ação
2. **Validação**: Zod valida inputs antes de chamar API
3. **Feedback**: Mensagens claras em português para usuário final
4. **Confirmação**: Operações destrutivas requerem confirm=true

---

## 🚀 Próximos Passos Após Plan-06

Com MCP funcionando, podemos:
1. **Phase 5**: Testes E2E completos com Claude
2. **Phase 6**: Documentation & Tutorial videos
3. **Phase 7**: DigitalOcean provider
4. **Phase 8**: Web Dashboard (opcional)

---

## 📊 Status

- 🔵 **READY TO START**: Plan detalhado e aprovado
- 📋 **Checklist**: 10 Etapas com 40+ tasks específicas
- 🧪 **TDD**: Testes escritos antes da implementação
- 🎯 **Critérios**: Objetivos mensuráveis definidos
- 📦 **Deliverable**: NPM package `@livchat/setup-mcp`

---

**Version**: 1.0.0
**Created**: 2025-01-11
**Author**: Claude Code + Pedro
**Reference**: CLAUDE.md Phase 4 - MCP Gateway
**Estimated Time**: ~12-16 horas (com TDD)
