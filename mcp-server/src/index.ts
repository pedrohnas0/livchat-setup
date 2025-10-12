#!/usr/bin/env node
/**
 * LivChatSetup MCP Server
 *
 * Infrastructure orchestration via AI using Model Context Protocol
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { APIClient } from "./api-client.js";
import {
  // Config & Secrets
  ManageConfigTool,
  ManageConfigInputSchema,
  ManageSecretsTool,
  ManageSecretsInputSchema,
  // Providers
  GetProviderInfoTool,
  GetProviderInfoInputSchema,
  // Servers
  CreateServerTool,
  CreateServerInputSchema,
  ListServersTool,
  ListServersInputSchema,
  ConfigureServerDNSTool,
  ConfigureServerDNSInputSchema,
  SetupServerTool,
  SetupServerInputSchema,
  DeleteServerTool,
  DeleteServerInputSchema,
  // Apps
  ListAppsTool,
  ListAppsInputSchema,
  DeployAppTool,
  DeployAppInputSchema,
  UndeployAppTool,
  UndeployAppInputSchema,
  ListDeployedAppsTool,
  ListDeployedAppsInputSchema,
  // Jobs
  GetJobStatusTool,
  GetJobStatusInputSchema,
  ListJobsTool,
  ListJobsInputSchema,
} from "./tools/index.js";

// Configuration from environment
const API_URL = process.env.LIVCHAT_API_URL || "http://localhost:8000";
const API_KEY = process.env.LIVCHAT_API_KEY;

// Create API client
const apiClient = new APIClient(API_URL, API_KEY);

// Create MCP server instance
const server = new McpServer({
  name: "livchat-setup",
  version: "1.0.0",
});

// Initialize all tool handlers
const tools = {
  // Config & Secrets (2 tools)
  manageConfig: new ManageConfigTool(apiClient),
  manageSecrets: new ManageSecretsTool(apiClient),
  // Providers (1 tool)
  getProviderInfo: new GetProviderInfoTool(apiClient),
  // Servers (5 tools)
  createServer: new CreateServerTool(apiClient),
  listServers: new ListServersTool(apiClient),
  configureServerDns: new ConfigureServerDNSTool(apiClient),
  setupServer: new SetupServerTool(apiClient),
  deleteServer: new DeleteServerTool(apiClient),
  // Apps (4 tools)
  listApps: new ListAppsTool(apiClient),
  deployApp: new DeployAppTool(apiClient),
  undeployApp: new UndeployAppTool(apiClient),
  listDeployedApps: new ListDeployedAppsTool(apiClient),
  // Jobs (2 tools)
  getJobStatus: new GetJobStatusTool(apiClient),
  listJobs: new ListJobsTool(apiClient),
};

// Register all 14 tools with MCP server
server.tool(
  "manage-config",
  "Gerencia configurações não-sensíveis do sistema (YAML em ~/.livchat/config.yaml). Exemplos: region padrão, server_type, admin_email, timezone. Use action='get' para obter ou action='set' para definir. Suporta notação de ponto (ex: 'defaults.region'). ATENÇÃO: Para dados sensíveis (tokens, passwords), use 'manage-secrets'.",
  ManageConfigInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.manageConfig.execute(input as any) }] })
);

server.tool(
  "manage-secrets",
  "Gerencia credenciais sensíveis CRIPTOGRAFADAS no Ansible Vault (~/.livchat/credentials.vault). Use para: tokens de API (Hetzner, Cloudflare), passwords de apps, SSH keys. CRÍTICO: Esta é a ÚNICA forma de configurar providers - hetzner_token DEVE estar no vault para criar servidores. Operações: 'get' (retorna valor decriptado), 'set' (salva criptografado), 'list' (lista chaves sem valores), 'delete' (remove secret).",
  ManageSecretsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.manageSecrets.execute(input as any) }] })
);

server.tool(
  "get-provider-info",
  "Obtém informações de provedores de nuvem (Hetzner, etc). info_type: 'overview' (status/configuração), 'regions' (datacenters disponíveis), 'server-types' (CPU/RAM/preço), 'all' (tudo). IMPORTANTE: Provider DEVE estar configurado com token no vault antes de consultar regions/server-types. Use 'manage-secrets' com key='hetzner_token' primeiro.",
  GetProviderInfoInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.getProviderInfo.execute(input as any) }] })
);

server.tool(
  "create-server",
  "Cria novo servidor VPS no provedor de nuvem. **OPERAÇÃO ASSÍNCRONA** (~2-5 min) - retorna job_id para acompanhar via 'get-job-status'. PRÉ-REQUISITO: Provider configurado com token no vault ('manage-secrets' com key='hetzner_token'). VALIDAÇÃO: Antes de executar, use 'get-provider-info' para obter server_type e region válidos.",
  CreateServerInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.createServer.execute(input as any) }] })
);

server.tool(
  "list-servers",
  "Lista servidores gerenciados. Se server_name fornecido, retorna detalhes do servidor específico (IP, status, apps instaladas, DNS config). Use include_details=true para informações completas de todos os servidores.",
  ListServersInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listServers.execute(input as any) }] })
);

server.tool(
  "configure-server-dns",
  "Associa configuração DNS a um servidor existente. Define o domínio principal (zone_name, ex: 'livchat.ai') e subdomain opcional (ex: 'lab', 'dev', 'ops') que serão usados por todas as aplicações instaladas neste servidor. PRÉ-REQUISITO: Cloudflare deve estar configurado ('manage-secrets' com 'cloudflare_email' e 'cloudflare_api_key'). Esta configuração é SALVA NO STATE do servidor e usada automaticamente em deploys futuros.",
  ConfigureServerDNSInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.configureServerDns.execute(input as any) }] })
);

server.tool(
  "setup-server",
  "Executa configuração completa do servidor: atualiza sistema, instala Docker, inicializa Swarm, deploy Traefik + Portainer. **OPERAÇÃO ASSÍNCRONA** (~5-10 min). PRÉ-REQUISITO: Servidor já criado via 'create-server' e job concluído. RECOMENDAÇÃO: Configure DNS antes do setup via 'configure-server-dns' para obter certificados SSL automaticamente.",
  SetupServerInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.setupServer.execute(input as any) }] })
);

server.tool(
  "delete-server",
  "Deleta servidor do provedor de nuvem e remove do estado. **OPERAÇÃO IRREVERSÍVEL e ASSÍNCRONA** (~1-2 min). ATENÇÃO: Todos os dados e aplicações serão perdidos permanentemente. Requer confirmação explícita do usuário com confirm=true.",
  DeleteServerInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.deleteServer.execute(input as any) }] })
);

server.tool(
  "list-apps",
  "Lista aplicações disponíveis no catálogo (PostgreSQL, Redis, N8N, Chatwoot, etc). Se app_name fornecido, retorna detalhes completos (dependências, requisitos, variáveis). Pode filtrar por category (databases, applications, infrastructure).",
  ListAppsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listApps.execute(input as any) }] })
);

server.tool(
  "deploy-app",
  "Instala aplicação em um servidor. Resolve e instala dependências automaticamente (ex: N8N instala PostgreSQL e Redis primeiro). **OPERAÇÃO ASSÍNCRONA** (~2-5 min por app). PRÉ-REQUISITOS: 1) Servidor configurado via 'setup-server', 2) Para DNS automático, use 'configure-server-dns' antes. O sistema usará DNS config do servidor (zone + subdomain) automaticamente se configurado.",
  DeployAppInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.deployApp.execute(input as any) }] })
);

server.tool(
  "undeploy-app",
  "Remove aplicação de um servidor. **OPERAÇÃO ASSÍNCRONA** (~1-2 min). ATENÇÃO: Dados da aplicação serão perdidos. Requer confirmação explícita do usuário com confirm=true.",
  UndeployAppInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.undeployApp.execute(input as any) }] })
);

server.tool(
  "list-deployed-apps",
  "Lista aplicações instaladas em um servidor específico com status, domínios e informações de deployment.",
  ListDeployedAppsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listDeployedApps.execute(input as any) }] })
);

server.tool(
  "get-job-status",
  "Verifica status de um job: pending (aguardando), running (executando), completed (concluído), failed (falhou), cancelled. Retorna progresso (0-100%), step atual e logs recentes se solicitado.",
  GetJobStatusInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.getJobStatus.execute(input as any) }] })
);

server.tool(
  "list-jobs",
  "Lista jobs com filtros opcionais. Útil para ver histórico de operações.",
  ListJobsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listJobs.execute(input as any) }] })
);

/**
 * Main entry point
 * Connects the MCP server to stdio transport
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is reserved for MCP protocol)
  console.error("LivChatSetup MCP Server v1.0.0");
  console.error(`API URL: ${API_URL}`);
  console.error(`API Key: ${API_KEY ? "***" + API_KEY.slice(-4) : "not set"}`);
  console.error("Server ready on stdio");
}

// Start server with error handling
main().catch((error) => {
  console.error("Fatal error starting server:", error);
  process.exit(1);
});
