# Sessão: Testes e Ajustes do MCP - 2025-10-13

## ✅ Fase 1: Publicação e Correções (Completo)

### Pacotes Publicados
- **PyPI:** `livchat-setup@0.1.0` - https://pypi.org/project/livchat-setup/
- **NPM:** `@pedrohnas/livchat-setup-mcp@0.1.1`

### Correções Implementadas

**1. setup.py - Módulos Faltando**
```python
# Adicionado py_modules para incluir módulos raiz
py_modules=[
    "orchestrator", "storage", "app_registry",
    "app_deployer", "job_manager", "ssh_manager", etc
]
```

**2. Error Handler - Mensagens Melhoradas**
```typescript
// mcp-server/src/error-handler.ts:122-128
suggestions: [
  'Install LivChat Setup: pip install livchat-setup',
  'Start API: source venv/bin/activate && uvicorn src.api.server:app --reload',
  'Check: curl $LIVCHAT_API_URL/health',
  'Verify LIVCHAT_API_URL (default: http://localhost:8000)',
]
```

**3. Validação de Servidores - Sempre com Provider**
```typescript
// mcp-server/src/tools/servers.ts:156-172
// list-servers agora valida TODOS os servidores com provider
// Remove automaticamente servidores deletados externamente
```

---

## 🚧 Fase 2: Testes Tool por Tool (Em Progresso)

### Status Atual
- [x] list-servers - Validado e corrigido
- [ ] create-server - **PRÓXIMO**
- [ ] get-provider-info
- [ ] configure-server-dns
- [ ] setup-server
- [ ] delete-server
- [ ] list-apps
- [ ] deploy-app
- [ ] undeploy-app
- [ ] list-deployed-apps
- [ ] get-job-status
- [ ] list-jobs
- [ ] manage-config
- [ ] manage-secrets

### Plano de Teste
1. **Executar cada tool via MCP**
2. **Identificar problemas de UX nos prompts**
3. **Ajustar mensagens e validações**
4. **Publicar versão patch (0.1.x) se necessário**
5. **Documentar comportamento esperado**

---

## 📝 Registro de Testes

### Tool: list-servers
**Status:** ✅ Aprovado
**Versão:** 0.1.1
**Melhorias:**
- Validação automática com provider
- Detecta servidores deletados externamente
- Mensagens claras quando lista vazia

### Tool: get-provider-info
**Status:** ✅ Aprovado (após correção)
**Versão:** API fix
**Problema Encontrado:**
- providers.py buscava token no config.yaml
- servers.py buscava corretamente no vault
**Correção:** Unificado para buscar `{provider}_token` no vault
**Teste:** Listou 19 tipos de servidores da Hetzner corretamente

### Tool: create-server
**Status:** ✅ Aprovado
**Versão:** 0.1.2
**Teste:** Criou manager-server (ccx23/ash) em 22s
**Melhorias Aplicadas:**
- Recomendações visuais destacadas (⭐ ash, ⭐ ccx23)
- Output minimalista e elegante
- Descrições de tools mais concisas

### Tool: delete-server
**Status:** ✅ Aprovado
**Versão:** 0.1.2
**Teste:** Deletou manager-server em ~1s
**Problema Identificado:** Logs mostram "[object Object]" (a corrigir)

---

## 🐛 Problemas Identificados na Sessão

### 1. Logs "[object Object]"
**Causa:** TypeScript imprime objetos `{timestamp, message}` como string
**Arquivo:** mcp-server/src/tools/jobs.ts:130-132
**Status:** 🔧 A corrigir na v0.1.3

### 2. Barra de Progresso Confusa
**Problema:** Jobs longos (~10min) ficam em 0% durante toda execução
**Causa Raiz:** Progresso só atualiza 0% → 100% sem valores intermediários
**Impacto:** AI e usuário pensam que o job travou

**Solução Proposta:** Sistema de etapas híbrido
- Mostrar "Etapa X/Y: Nome da etapa"
- Progresso = (etapas_completas / total) * 100 + incremento_temporal
- Pulo proporcional ao completar etapa
- Crescimento suave durante etapa (baseado em tempo)

**Exemplo:**
```
📍 Etapa 3/7: Installing Docker
📈 [████████░░░░░░░░░░░] 35%
⏱️  2m 15s
```

**Status:** 🚀 Implementação aprovada

---

## 🎨 Melhorias de UX Aplicadas (v0.1.2)

### Visual Minimalista
**Antes:**
```
═══════════════════════════════════════
📦 Informações Completas: HETZNER
═══════════════════════════════════════
🌍 ash ← RECOMENDADO
```

**Depois:**
```
📦 HETZNER - Informações Completas

⭐ Configuração Recomendada
  Location: ash (Ashburn, VA)

⭐ ash
```

### Descrições de Tools Concisas
Reduziu de ~50 palavras para ~15 palavras por tool:

**Antes:** "Cria novo servidor VPS no provedor de nuvem. **OPERAÇÃO ASSÍNCRONA** (~2-5 min)..."
**Depois:** "Cria servidor VPS. Use get-provider-info para ver opções. Retorna job_id."

### Storage Decision Matrix
Nova seção no CLAUDE.md documentando claramente:
- Vault: tokens, passwords, SSH keys
- Config: preferências, defaults
- State: IPs, status, apps instaladas

---

## 🔧 Comandos Úteis

### Publicar Nova Versão MCP
```bash
# 1. Editar version em package.json
# 2. Build e publicar
npm run build
npm publish --access public --otp=XXXXXX

# 3. Atualizar .mcp.json
"args": ["@pedrohnas/livchat-setup-mcp@0.1.X"]

# 4. Reconectar MCP no Claude Code
/mcp
```

### API Local
```bash
source venv/bin/activate
uvicorn src.api.server:app --reload --port 8000
```

---

## 📋 Próximos Passos

### Implementação Imediata (v0.1.3)
1. ✅ Corrigir logs "[object Object]"
2. ✅ Sistema de etapas para progresso híbrido
3. ✅ Adicionar campos ao Job model (total_steps, current_step_num, step_name)
4. ✅ Atualizar executors para reportar etapas
5. ✅ Atualizar MCP display para mostrar "Etapa X/Y"

### Testes Pendentes
- [ ] setup-server (com novo sistema de etapas)
- [ ] configure-server-dns
- [ ] list-apps
- [ ] deploy-app
- [ ] undeploy-app
- [ ] list-deployed-apps
- [ ] manage-config
- [ ] manage-secrets

---

## 🏗️ Fase 3: Refatoração Arquitetural - DNS e Infrastructure

### 📋 Análise do Estado Atual

#### Fluxo Atual de Setup
```python
# setup-server (full_setup):
1. Wait SSH
2. Test connectivity
3. Base setup (apt, timezone)
4. Docker install
5. Swarm init
6. **Traefik deploy** ← Deployado via Ansible no setup
# Portainer NÃO é deployado automaticamente
```

#### Storage Atual
- **config.yaml**: `admin_email`, `provider`, `region` (defaults genéricos)
- **state.json**: Servers (ip, status, apps), deployments, jobs, DNS (zone/subdomain se configurado)
- **secrets.vault**: Tokens, passwords, SSH keys

#### Problemas Identificados

**1. DNS é Opcional**
- `configure-server-dns` é tool separada
- Pode deployar apps sem DNS configurado
- Apps quebram sem Traefik + DNS properly configurado

**2. Traefik/Portainer no Setup**
- São tratados como "infraestrutura do setup"
- Mas são aplicações Docker que deveriam ser apps
- Mistura conceitos: setup do sistema vs deploy de apps

**3. Sem Validação de Dependências Base**
- Apps podem ser deployados sem Traefik/Portainer
- Falha silenciosa quando Portainer não está pronto
- `app_deployer.py:123` - tenta usar Portainer sem validar

**4. config.yaml é Redundante**
- Adiciona complexidade sem benefício claro
- Mesmas informações poderiam estar no state.json
- Apenas `admin_email` é realmente usado

**5. configure-server-dns Tool Redundante**
- DNS deveria ser configurado no setup (obrigatório)
- Tool separada adiciona passo desnecessário
- Mas precisa de tool para **ajustar** DNS depois

### 🎯 Solução Proposta

#### 1. Refatorar setup-server Tool

**Parâmetros NOVOS:**
```typescript
setup-server(
  server_name: string,
  zone_name: string,          // ← OBRIGATÓRIO
  subdomain?: string,          // ← Opcional (ex: 'lab', 'prod')
  ssl_email?: string,          // Default: admin@livchat.ai
  network_name?: string,       // Default: livchat_network
  timezone?: string            // Default: America/Sao_Paulo
)
```

**Descrição Atualizada:**
```
"Configura servidor: sistema, Docker, Swarm. DNS obrigatório.
Ex: zone_name='livchat.ai', subdomain='lab', ssl_email='team@livchat.ai'.
Retorna job_id."
```

**Validações ANTES de executar:**
```python
# 1. Validar cloudflare_api_key existe no vault
if not storage.secrets.get_secret("cloudflare_api_key"):
    raise ValueError("Cloudflare API key not configured. Use manage-secrets first.")

# 2. Validar cloudflare_email existe
if not storage.secrets.get_secret("cloudflare_email"):
    raise ValueError("Cloudflare email not configured. Use manage-secrets first.")
```

**Novo Fluxo:**
```python
# setup-server (refatorado):
1. Validate Cloudflare credentials exist
2. Wait SSH
3. Test connectivity
4. **Save DNS config to state.json** ← NOVO (zone + subdomain)
5. Base setup (apt, timezone)
6. Docker install
7. Swarm init
8. **FINALIZA** ← SEM Traefik/Portainer
```

**Mudança Crítica:**
- Traefik e Portainer **NÃO** são mais deployados no setup
- São deployados via `deploy-app` como qualquer outra app
- DNS é configurado NO setup (obrigatório)

#### 2. Criar "base-infrastructure" App Bundle

**Novo arquivo:** `apps/definitions/infrastructure/base-infrastructure.yaml`
```yaml
name: base-infrastructure
version: "1.0.0"
category: infrastructure
deploy_method: ansible  # Ainda usa Ansible, mas via deploy-app
description: "Traefik + Portainer (infrastructure bundle required by all apps)"

components:
  - traefik
  - portainer

dependencies: []  # Nenhuma dependência

# Flag especial - indica que TODOS os apps dependem deste bundle
required_by_all_apps: true

# Deploy via Ansible (não Portainer, pois Portainer não existe ainda!)
ansible:
  playbooks:
    - traefik-deploy.yml
    - portainer-deploy.yml
```

**Comportamento:**
- `deploy-app(server_name="setup-test", app_name="base-infrastructure")`
- Deploya Traefik PRIMEIRO, depois Portainer
- Usa Ansible (não Portainer API, pois Portainer não existe ainda)
- Salva em `state.json`: `applications: ["base-infrastructure"]`

#### 3. Validações em deploy-app

**ANTES de deployar QUALQUER app (exceto base-infrastructure):**
```python
async def deploy_app(server_name, app_name, config):
    # 1. Validar base-infrastructure está deployada
    server = storage.state.get_server(server_name)
    apps = server.get("applications", [])

    if app_name != "base-infrastructure":
        if "base-infrastructure" not in apps:
            return {
                "success": False,
                "error": "Base infrastructure not deployed. Deploy 'base-infrastructure' first.",
                "hint": "deploy-app(server_name='...', app_name='base-infrastructure')"
            }

    # 2. Validar DNS está configurado
    dns = server.get("dns", {})
    if not dns.get("zone"):
        return {
            "success": False,
            "error": "DNS not configured on server. Run setup-server with zone_name parameter.",
            "hint": "setup-server(server_name='...', zone_name='livchat.ai', ...)"
        }

    # Proceed with deployment...
```

#### 4. Remover configure-server-dns Tool

**Remover:**
- Tool `configure-server-dns` do MCP
- Endpoint `/servers/{name}/dns` da API (ou deprecar)

**Razão:**
- DNS é configurado no setup (obrigatório)
- Tool é redundante e adiciona passo desnecessário

#### 5. Criar update-server-dns Tool

**Nova tool para AJUSTAR DNS depois (se necessário):**
```typescript
update-server-dns(
  server_name: string,
  zone_name: string,
  subdomain?: string
)
```

**Descrição:**
```
"Atualiza configuração DNS do servidor.
Ex: zone_name='livchat.ai', subdomain='prod'.
Apps já deployadas mantêm DNS anterior."
```

**Implementação:**
```python
# Atualiza apenas no state.json
# NÃO re-deploya apps automaticamente
# Novas apps usarão novo DNS
```

#### 6. Simplificar Storage

**config.yaml → Minimizar ou Remover:**
```yaml
# Manter APENAS se necessário:
admin_email: "team@livchat.ai"
# Remover: provider, region, server_type (são inputs, não config)
```

**state.json → Centralizar Tudo:**
```json
{
  "servers": {
    "setup-test": {
      "id": "110741662",
      "name": "setup-test",
      "ip": "5.161.115.202",
      "status": "running",
      "dns": {
        "zone": "livchat.ai",
        "subdomain": "lab"
      },
      "applications": ["base-infrastructure", "postgres", "n8n"],
      "created_at": "2025-10-14T00:28:06"
    }
  },
  "jobs": [...],
  "deployments": [...]
}
```

**secrets.vault → Manter:**
- `cloudflare_email`
- `cloudflare_api_key`
- `hetzner_token`
- SSH keys
- App passwords

### 📝 Checklist de Implementação

#### Backend Python (src/)
- [ ] **orchestrator.py:701-727** - Refatorar `setup_server()` para:
  - Validar Cloudflare credentials antes
  - Aceitar `zone_name` (required) e `subdomain` (optional)
  - Salvar DNS config no state.json ANTES do setup
  - REMOVER deploy de Traefik (linha 711)
  - REMOVER qualquer menção a Portainer no setup

- [ ] **server_setup.py:669-745** - Refatorar `full_setup()`:
  - Remover `("traefik-deploy", ...)` da lista de steps (linha 711)
  - Setup termina após `swarm-init`
  - Adicionar step para salvar DNS config

- [ ] **app_deployer.py:33-66** - Adicionar validações em `deploy()`:
  - Validar `base-infrastructure` deployada (exceto se deployando ela própria)
  - Validar DNS configurado no servidor
  - Retornar erros claros com hints

- [ ] **app_registry.py** - Suporte para bundle apps:
  - `required_by_all_apps` flag
  - `components` list para bundles
  - Validação de bundles

#### API (src/api/)
- [ ] **routes/servers.py** - Atualizar endpoint `POST /servers/{name}/setup`:
  - Adicionar `zone_name` (required)
  - Adicionar `subdomain` (optional)
  - Validar Cloudflare credentials antes
  - Documentação atualizada

- [ ] **routes/servers.py** - Criar endpoint `PUT /servers/{name}/dns`:
  - Para `update-server-dns` tool
  - Atualiza apenas state.json
  - Não re-deploya apps

- [ ] **routes/servers.py** - Deprecar/remover `POST /servers/{name}/dns`:
  - Endpoint antigo de configure-server-dns
  - Pode manter com warning de deprecation

#### App Definitions (apps/definitions/)
- [ ] **infrastructure/base-infrastructure.yaml** - Criar bundle:
  - Components: traefik + portainer
  - Deploy method: ansible
  - `required_by_all_apps: true`

- [ ] **infrastructure/traefik.yaml** - Manter, mas:
  - Usado via base-infrastructure
  - Não deployado diretamente

- [ ] **infrastructure/portainer.yaml** - Manter, mas:
  - Usado via base-infrastructure
  - Não deployado diretamente

#### MCP Server (mcp-server/src/)
- [ ] **tools/servers.ts** - Refatorar `SetupServerTool`:
  - Adicionar `zone_name` (required) ao schema
  - Adicionar `subdomain` (optional) ao schema
  - Atualizar descrição com exemplos
  - Atualizar output para mencionar DNS configurado

- [ ] **tools/servers.ts** - Criar `UpdateServerDNSTool`:
  - Schema: `server_name`, `zone_name`, `subdomain?`
  - Descrição clara (ajustar DNS existente)
  - Output mostrando DNS atualizado

- [ ] **tools/servers.ts** - Remover `ConfigureServerDNSTool`:
  - Deletar classe completa
  - Remover do index.ts

- [ ] **index.ts** - Atualizar tool registrations:
  - Remover `configure-server-dns`
  - Adicionar `update-server-dns`
  - Atualizar descrição de `setup-server`

#### Testes
- [ ] **Unit tests** - Adicionar testes para:
  - Validação de Cloudflare credentials
  - Validação de base-infrastructure
  - Validação de DNS configurado
  - update-server-dns

- [ ] **E2E tests** - Atualizar workflow:
  - setup-server com DNS obrigatório
  - deploy-app base-infrastructure
  - deploy-app outras apps (com validações)

#### Documentação
- [ ] **CLAUDE.md** - Atualizar seção Architecture:
  - Setup flow (sem Traefik/Portainer)
  - DNS obrigatório no setup
  - base-infrastructure bundle concept
  - Storage simplificado

- [ ] **README.md** - Atualizar quick start:
  - setup-server com DNS desde início
  - deploy base-infrastructure como primeiro step
  - Fluxo correto completo

### 🎯 Ordem de Implementação

**Fase 3.1: Backend Core (Python)**
1. Refatorar `server_setup.py` (remover Traefik do setup)
2. Refatorar `orchestrator.py` (DNS obrigatório, validações)
3. Adicionar validações em `app_deployer.py`
4. Criar `base-infrastructure.yaml`

**Fase 3.2: API Layer**
5. Atualizar endpoint `/servers/{name}/setup`
6. Criar endpoint `/servers/{name}/dns` (PUT)
7. Deprecar endpoint antigo

**Fase 3.3: MCP Server**
8. Refatorar `setup-server` tool
9. Criar `update-server-dns` tool
10. Remover `configure-server-dns` tool
11. Publicar v0.2.0 (breaking change)

**Fase 3.4: Testes e Docs**
12. Atualizar testes
13. Atualizar CLAUDE.md
14. Atualizar README.md

### ⚠️ Breaking Changes (v0.2.0)

**MCP Tools:**
- ❌ **REMOVED:** `configure-server-dns` tool
- 🔄 **CHANGED:** `setup-server` - `zone_name` now **required**
- ✨ **NEW:** `update-server-dns` tool
- 🔄 **CHANGED:** `deploy-app` - validates base-infrastructure first

**API Endpoints:**
- 🔄 **CHANGED:** `POST /servers/{name}/setup` - `zone_name` required
- ✨ **NEW:** `PUT /servers/{name}/dns`
- ⚠️ **DEPRECATED:** `POST /servers/{name}/dns`

**Workflow Changes:**
```bash
# ANTES (v0.1.x):
1. create-server
2. setup-server (Traefik deployado automaticamente)
3. configure-server-dns (opcional)
4. deploy-app postgres

# DEPOIS (v0.2.0):
1. create-server
2. setup-server (zone_name OBRIGATÓRIO, sem Traefik)
3. deploy-app base-infrastructure (Traefik + Portainer)
4. deploy-app postgres
```

---

**Última Atualização:** 2025-10-14 03:30 UTC
