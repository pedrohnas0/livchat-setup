/**
 * Tools: Server Management (5 tools) - v0.2.0
 *
 * 1. create-server (async)
 * 2. list-servers
 * 3. update-server-dns (v0.2.0: replaces configure-server-dns)
 * 4. setup-server (async) - v0.2.0: DNS now required
 * 5. delete-server (async)
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

// ========================================
// Schemas
// ========================================

/**
 * Schema for create-server tool
 */
export const CreateServerInputSchema = z.object({
  name: z.string()
    .min(3)
    .max(50)
    .regex(/^[a-z0-9-]+$/)
    .describe('Nome único do servidor (apenas lowercase, números e hífens)'),
  server_type: z.string()
    .describe('Tipo do servidor (ex: cx11, cx21). Use get-provider-info para ver valores válidos'),
  region: z.string()
    .describe('Região/datacenter (ex: nbg1, fsn1). Use get-provider-info para ver regiões válidas'),
  image: z.string()
    .default('debian-12')
    .describe('Imagem do SO (padrão: debian-12)'),
});

export type CreateServerInput = z.infer<typeof CreateServerInputSchema>;

/**
 * Schema for list-servers tool
 */
export const ListServersInputSchema = z.object({
  server_name: z.string().optional()
    .describe('Nome do servidor específico (opcional)'),
  include_details: z.boolean()
    .default(false)
    .describe('Incluir detalhes completos (padrão: false)'),
});

export type ListServersInput = z.infer<typeof ListServersInputSchema>;

/**
 * Schema for update-server-dns tool (v0.2.0: replaces configure-server-dns)
 */
export const UpdateServerDNSInputSchema = z.object({
  server_name: z.string()
    .describe('Nome do servidor'),
  zone_name: z.string()
    .min(3)
    .describe('Domínio principal registrado no Cloudflare (ex: livchat.ai)'),
  subdomain: z.string().optional()
    .describe('Subdomain opcional (ex: lab, dev, prod). Apps usarão pattern: {app}.{subdomain}.{zone_name}'),
});

export type UpdateServerDNSInput = z.infer<typeof UpdateServerDNSInputSchema>;

/**
 * Schema for setup-server tool (v0.2.0: DNS now required)
 */
export const SetupServerInputSchema = z.object({
  server_name: z.string()
    .describe('Nome do servidor a configurar'),

  // v0.2.0: DNS configuration is now REQUIRED
  zone_name: z.string()
    .min(3)
    .describe('Domínio principal registrado no Cloudflare (OBRIGATÓRIO - ex: livchat.ai)'),
  subdomain: z.string().optional()
    .describe('Subdomain opcional (ex: lab, dev, prod). Apps usarão pattern: {app}.{subdomain}.{zone_name}'),

  ssl_email: z.string()
    .email()
    .default('admin@example.com')
    .describe('Email para certificados SSL Let\'s Encrypt'),
  network_name: z.string()
    .default('livchat_network')
    .describe('Nome da rede Docker Swarm overlay'),
  timezone: z.string()
    .default('America/Sao_Paulo')
    .describe('Timezone do servidor (padrão: America/Sao_Paulo - UTC-3)'),
});

export type SetupServerInput = z.infer<typeof SetupServerInputSchema>;

/**
 * Schema for delete-server tool
 */
export const DeleteServerInputSchema = z.object({
  server_name: z.string()
    .describe('Nome do servidor a deletar'),
  confirm: z.literal(true)
    .describe('Confirmação obrigatória: true apenas se usuário confirmou explicitamente a deleção'),
});

export type DeleteServerInput = z.infer<typeof DeleteServerInputSchema>;

// ========================================
// Tool Handlers
// ========================================

/**
 * Tool: create-server (ASYNC)
 */
export class CreateServerTool {
  constructor(private client: APIClient) {}

  async execute(input: CreateServerInput): Promise<string> {
    try {
      const response = await this.client.post<{ job_id: string }>('/servers', {
        name: input.name,
        server_type: input.server_type,
        region: input.region,
        image: input.image,
      });

      let output = '✅ Servidor sendo criado (operação assíncrona)\n\n';
      output += `🆔 Job ID: ${response.job_id}\n`;
      output += `📦 Servidor: ${input.name}\n`;
      output += `🖥️  Tipo: ${input.server_type}\n`;
      output += `🌍 Região: ${input.region}\n\n`;
      output += '💡 Use get-job-status para acompanhar o progresso:\n';
      output += `   get-job-status(job_id="${response.job_id}", tail_logs=50)`;

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}

/**
 * Tool: list-servers
 */
export class ListServersTool {
  constructor(private client: APIClient) {}

  async execute(input: ListServersInput): Promise<string> {
    try {
      // Get specific server details
      if (input.server_name) {
        // CRITICAL: verify_provider=true ensures server still exists in cloud provider
        // This prevents using stale state data for servers deleted externally
        const server = await this.client.get<any>(`/servers/${input.server_name}?verify_provider=true`);
        return this.formatServerDetails(server);
      }

      // List all servers (from state)
      const servers = await this.client.get<{ servers: any[] }>('/servers');

      if (!servers.servers || servers.servers.length === 0) {
        return '✅ Nenhum servidor encontrado.\n\n💡 Use create-server para criar seu primeiro servidor.';
      }

      // CRITICAL: Validate each server with provider to update state
      // This ensures we don't show servers that were deleted externally
      const validatedServers = [];
      for (const server of servers.servers) {
        try {
          // Verify each server exists in provider
          const validated = await this.client.get<any>(`/servers/${server.name}?verify_provider=true`);
          validatedServers.push(validated);
        } catch (error: any) {
          // Server was deleted externally - skip it
          if (error.status === 404) {
            continue;
          }
          // Other errors - include server with warning
          validatedServers.push({ ...server, status: `${server.status} (verification failed)` });
        }
      }

      if (validatedServers.length === 0) {
        return '✅ Nenhum servidor ativo encontrado.\n\n💡 Alguns servidores podem ter sido deletados externamente.';
      }

      let output = `✅ Servidores Encontrados: ${validatedServers.length}\n\n`;

      for (const server of validatedServers) {
        output += `📦 ${server.name}\n`;
        output += `   🆔 ID: ${server.id}\n`;
        output += `   🌐 IP: ${server.ip_address || 'N/A'}\n`;
        output += `   📊 Status: ${server.status}\n`;

        if (input.include_details && server.applications) {
          output += `   📱 Apps: ${server.applications.join(', ') || 'Nenhuma'}\n`;
        }

        output += '\n';
      }

      output += '💡 Use list-servers(server_name="nome") para detalhes completos.';

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  private formatServerDetails(server: any): string {
    let output = '✅ Detalhes do Servidor\n\n';
    output += `📦 Nome: ${server.name}\n`;
    output += `🆔 ID: ${server.id}\n`;
    output += `🌐 IP: ${server.ip_address || 'N/A'}\n`;
    output += `📊 Status: ${server.status}\n`;
    output += `🖥️  Tipo: ${server.server_type || 'N/A'}\n`;
    output += `🌍 Região: ${server.region || 'N/A'}\n`;

    if (server.dns_config) {
      output += `\n🌐 Configuração DNS:\n`;
      output += `   Zone: ${server.dns_config.zone_name}\n`;
      if (server.dns_config.subdomain) {
        output += `   Subdomain: ${server.dns_config.subdomain}\n`;
      }
    }

    if (server.applications && server.applications.length > 0) {
      output += `\n📱 Aplicações Instaladas (${server.applications.length}):\n`;
      for (const app of server.applications) {
        output += `   - ${app}\n`;
      }
    } else {
      output += '\n📱 Aplicações: Nenhuma instalada\n';
    }

    if (server.created_at) {
      output += `\n🕐 Criado em: ${server.created_at}\n`;
    }

    return output;
  }
}

/**
 * Tool: update-server-dns (v0.2.0: replaces configure-server-dns)
 */
export class UpdateServerDNSTool {
  constructor(private client: APIClient) {}

  async execute(input: UpdateServerDNSInput): Promise<string> {
    try {
      await this.client.put(`/servers/${input.server_name}/dns`, {
        zone_name: input.zone_name,
        subdomain: input.subdomain,
      });

      let output = '✅ Configuração DNS atualizada (v0.2.0)\n\n';
      output += `📦 Servidor: ${input.server_name}\n`;
      output += `🌐 Zone: ${input.zone_name}\n`;

      if (input.subdomain) {
        output += `🏷️  Subdomain: ${input.subdomain}\n`;
        output += `\n📝 Pattern de domínios: {app}.${input.subdomain}.${input.zone_name}\n`;
        output += `   Exemplo: n8n.${input.subdomain}.${input.zone_name}\n`;
      } else {
        output += `\n📝 Pattern de domínios: {app}.${input.zone_name}\n`;
        output += `   Exemplo: n8n.${input.zone_name}\n`;
      }

      output += '\n⚠️  Apps deployadas podem precisar ser redeployadas para usar os novos domínios.\n';
      output += '💡 Use list-deployed-apps para ver apps que podem precisar atualização.';

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}

/**
 * Tool: setup-server (ASYNC) - v0.2.0
 */
export class SetupServerTool {
  constructor(private client: APIClient) {}

  async execute(input: SetupServerInput): Promise<string> {
    try {
      const response = await this.client.post<{ job_id: string }>(
        `/servers/${input.server_name}/setup`,
        {
          zone_name: input.zone_name,        // v0.2.0: DNS required
          subdomain: input.subdomain,        // v0.2.0: Optional subdomain
          ssl_email: input.ssl_email,
          network_name: input.network_name,
          timezone: input.timezone,
        }
      );

      let output = '✅ Setup do servidor iniciado com DNS (operação assíncrona)\n\n';
      output += `🆔 Job ID: ${response.job_id}\n`;
      output += `📦 Servidor: ${input.server_name}\n`;
      output += `🌐 DNS Zone: ${input.zone_name}\n`;
      if (input.subdomain) {
        output += `🏷️  Subdomain: ${input.subdomain}\n`;
      }
      output += '\n🔧 Etapas do setup (v0.2.0):\n';
      output += '   1️⃣  Atualização do sistema e timezone\n';
      output += '   2️⃣  Instalação do Docker\n';
      output += '   3️⃣  Inicialização do Swarm + rede overlay\n';
      output += '   4️⃣  Configuração DNS salva no servidor\n\n';
      output += '⚠️  IMPORTANTE: Traefik e Portainer NÃO são mais instalados automaticamente!\n';
      output += '   Após o setup, você DEVE deployar a infrastructure:\n';
      output += `   deploy-app(app_name="infrastructure", server_name="${input.server_name}")\n\n`;
      output += '⏱️  Tempo estimado: 3-5 minutos\n\n';
      output += '💡 Use get-job-status para acompanhar o progresso:\n';
      output += `   get-job-status(job_id="${response.job_id}", tail_logs=50)`;

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}

/**
 * Tool: delete-server (ASYNC)
 */
export class DeleteServerTool {
  constructor(private client: APIClient) {}

  async execute(input: DeleteServerInput): Promise<string> {
    try {
      const response = await this.client.delete<{ job_id: string }>(
        `/servers/${input.server_name}`
      );

      let output = '✅ Servidor sendo deletado (operação assíncrona)\n\n';
      output += `🆔 Job ID: ${response.job_id}\n`;
      output += `📦 Servidor: ${input.server_name}\n\n`;
      output += '⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL\n';
      output += '   - Todos os dados serão perdidos permanentemente\n';
      output += '   - Todas as aplicações serão removidas\n';
      output += '   - O servidor será destruído no provedor de nuvem\n\n';
      output += '💡 Use get-job-status para acompanhar:\n';
      output += `   get-job-status(job_id="${response.job_id}")`;

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}
