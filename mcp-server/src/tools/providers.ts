/**
 * Tool: Provider Management (1 tool)
 *
 * 1. get-provider-info
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

// ========================================
// Schema
// ========================================

/**
 * Schema for get-provider-info tool
 */
export const GetProviderInfoInputSchema = z.object({
  provider: z.enum(['hetzner'])
    .describe('Nome do provedor de nuvem'),
  info_type: z.enum(['overview', 'regions', 'server-types', 'all'])
    .default('all')
    .describe("'overview'=status, 'regions'=datacenters, 'server-types'=tamanhos, 'all'=tudo"),
});

export type GetProviderInfoInput = z.infer<typeof GetProviderInfoInputSchema>;

// ========================================
// Tool Handler
// ========================================

/**
 * Tool: get-provider-info
 */
export class GetProviderInfoTool {
  constructor(private client: APIClient) {}

  async execute(input: GetProviderInfoInput): Promise<string> {
    try {
      switch (input.info_type) {
        case 'overview':
          return await this.getOverview(input.provider);
        case 'regions':
          return await this.getRegions(input.provider);
        case 'server-types':
          return await this.getServerTypes(input.provider);
        case 'all':
          return await this.getAll(input.provider);
        default:
          return '❌ Tipo de informação inválido';
      }
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  /**
   * Get provider overview (status/configuration)
   */
  private async getOverview(provider: string): Promise<string> {
    const info = await this.client.get<any>(`/providers/${provider}`);

    let output = `✅ Overview do Provider: ${provider}\n\n`;
    output += `📊 Status: ${info.status || 'configured'}\n`;
    output += `🔑 Token configurado: ${info.token_configured ? 'Sim' : 'Não'}\n`;

    if (!info.token_configured) {
      output += '\n⚠️  Provider não configurado!\n';
      output += '💡 Use manage-secrets para definir o token:\n';
      output += `   manage-secrets(operation="set", key="${provider}_token", value="seu_token")`;
    }

    if (info.default_region) {
      output += `\n🌍 Região padrão: ${info.default_region}\n`;
    }

    if (info.default_server_type) {
      output += `🖥️  Tipo padrão: ${info.default_server_type}\n`;
    }

    return output;
  }

  /**
   * Get available regions/datacenters
   */
  private async getRegions(provider: string): Promise<string> {
    const regions = await this.client.get<{ regions: any[] }>(`/providers/${provider}/regions`);

    if (!regions.regions || regions.regions.length === 0) {
      return '✅ Nenhuma região disponível.';
    }

    let output = `✅ Regiões Disponíveis (${provider}): ${regions.regions.length}\n\n`;

    for (const region of regions.regions) {
      output += `🌍 ${region.name || region.id}\n`;

      if (region.description) {
        output += `   📝 ${region.description}\n`;
      }

      if (region.location) {
        output += `   📍 Localização: ${region.location}\n`;
      }

      if (region.city || region.country) {
        output += `   🏙️  ${region.city || ''} ${region.country || ''}\n`;
      }

      output += '\n';
    }

    return output;
  }

  /**
   * Get available server types (CPU/RAM/price)
   */
  private async getServerTypes(provider: string): Promise<string> {
    const types = await this.client.get<{ server_types: any[] }>(`/providers/${provider}/server-types`);

    if (!types.server_types || types.server_types.length === 0) {
      return '✅ Nenhum tipo de servidor disponível.';
    }

    let output = `✅ Tipos de Servidores Disponíveis (${provider}): ${types.server_types.length}\n\n`;

    for (const type of types.server_types) {
      output += `🖥️  ${type.name || type.id}\n`;

      if (type.description) {
        output += `   📝 ${type.description}\n`;
      }

      if (type.cores) {
        output += `   🔧 CPU: ${type.cores} cores\n`;
      }

      if (type.memory) {
        output += `   💾 RAM: ${type.memory} GB\n`;
      }

      if (type.disk) {
        output += `   💿 Disco: ${type.disk} GB\n`;
      }

      if (type.price) {
        output += `   💰 Preço: ${type.price} ${type.currency || 'EUR'}/mês\n`;
      }

      if (type.storage_type) {
        output += `   📦 Storage: ${type.storage_type}\n`;
      }

      output += '\n';
    }

    return output;
  }

  /**
   * Get all information (overview + regions + server-types)
   */
  private async getAll(provider: string): Promise<string> {
    const [overview, regions, serverTypes] = await Promise.all([
      this.getOverview(provider),
      this.getRegions(provider),
      this.getServerTypes(provider),
    ]);

    let output = '═══════════════════════════════════════\n';
    output += `📦 Informações Completas: ${provider.toUpperCase()}\n`;
    output += '═══════════════════════════════════════\n\n';
    output += overview + '\n\n';
    output += '───────────────────────────────────────\n\n';
    output += regions + '\n\n';
    output += '───────────────────────────────────────\n\n';
    output += serverTypes;

    return output;
  }
}
