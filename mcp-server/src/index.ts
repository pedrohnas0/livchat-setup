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
  "Gerencia configurações não-sensíveis (region padrão, timezone, etc). Para tokens/passwords use manage-secrets.",
  ManageConfigInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.manageConfig.execute(input as any) }] })
);

server.tool(
  "manage-secrets",
  "Gerencia credenciais criptografadas (tokens, passwords, SSH keys). Configure hetzner_token aqui antes de criar servidores.",
  ManageSecretsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.manageSecrets.execute(input as any) }] })
);

server.tool(
  "get-provider-info",
  "Obtém informações do provider (regions, server-types, preços). Use antes de create-server para ver opções disponíveis.",
  GetProviderInfoInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.getProviderInfo.execute(input as any) }] })
);

server.tool(
  "create-server",
  "Cria servidor VPS. Ex: name='manager-server', server_type='ccx23', region='ash'. Retorna job_id.",
  CreateServerInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.createServer.execute(input as any) }] })
);

server.tool(
  "list-servers",
  "Lista servidores. Use server_name para detalhes (IP, apps, DNS) ou include_details=true para info completa de todos.",
  ListServersInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listServers.execute(input as any) }] })
);

server.tool(
  "configure-server-dns",
  "Configura DNS do servidor (zone_name + subdomain). Apps usarão automaticamente em deploys. Configure Cloudflare em manage-secrets antes.",
  ConfigureServerDNSInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.configureServerDns.execute(input as any) }] })
);

server.tool(
  "setup-server",
  "Configura servidor: sistema, Docker, Swarm, Traefik e Portainer. Use configure-server-dns antes para SSL automático. Retorna job_id.",
  SetupServerInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.setupServer.execute(input as any) }] })
);

server.tool(
  "delete-server",
  "Deleta servidor e todos os dados permanentemente. Requer confirm=true do usuário. Retorna job_id.",
  DeleteServerInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.deleteServer.execute(input as any) }] })
);

server.tool(
  "list-apps",
  "Lista apps disponíveis (Postgres, Redis, N8N, Chatwoot). Use app_name para ver dependências e requisitos. Filtre por category.",
  ListAppsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listApps.execute(input as any) }] })
);

server.tool(
  "deploy-app",
  "Instala app com dependências automaticamente (ex: N8N instala Postgres + Redis). Usa DNS do servidor se configurado. Retorna job_id.",
  DeployAppInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.deployApp.execute(input as any) }] })
);

server.tool(
  "undeploy-app",
  "Remove app e dados. Requer confirm=true do usuário. Retorna job_id.",
  UndeployAppInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.undeployApp.execute(input as any) }] })
);

server.tool(
  "list-deployed-apps",
  "Lista apps instaladas em um servidor com status e domínios.",
  ListDeployedAppsInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.listDeployedApps.execute(input as any) }] })
);

server.tool(
  "get-job-status",
  "Verifica status de job (pending/running/completed/failed). Retorna progresso e logs.",
  GetJobStatusInputSchema.shape,
  async (input) => ({ content: [{ type: "text", text: await tools.getJobStatus.execute(input as any) }] })
);

server.tool(
  "list-jobs",
  "Lista histórico de jobs. Filtre por status se necessário.",
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
