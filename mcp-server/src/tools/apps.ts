/**
 * Tools: Application Management (4 tools)
 *
 * 1. list-apps
 * 2. deploy-app (async)
 * 3. undeploy-app (async)
 * 4. list-deployed-apps
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

// ========================================
// Schemas
// ========================================

/**
 * Schema for list-apps tool
 */
export const ListAppsInputSchema = z.object({
  app_name: z.string().optional()
    .describe('Nome da aplicação específica (opcional)'),
  category: z.enum(['databases', 'applications', 'infrastructure']).optional()
    .describe('Filtrar por categoria (opcional)'),
});

export type ListAppsInput = z.infer<typeof ListAppsInputSchema>;

/**
 * Schema for deploy-app tool
 */
export const DeployAppInputSchema = z.object({
  app_name: z.string()
    .describe('Nome da aplicação (ex: postgres, redis, n8n). Use list-apps para ver opções'),
  server_name: z.string()
    .describe('Nome do servidor. Use list-servers para ver servidores disponíveis'),
  environment: z.record(z.any()).optional()
    .describe('Variáveis de ambiente customizadas (opcional)'),
});

export type DeployAppInput = z.infer<typeof DeployAppInputSchema>;

/**
 * Schema for undeploy-app tool
 */
export const UndeployAppInputSchema = z.object({
  app_name: z.string()
    .describe('Nome da aplicação a remover'),
  server_name: z.string()
    .describe('Nome do servidor'),
  confirm: z.literal(true)
    .describe('Confirmação obrigatória: true apenas se usuário confirmou explicitamente'),
});

export type UndeployAppInput = z.infer<typeof UndeployAppInputSchema>;

/**
 * Schema for list-deployed-apps tool
 */
export const ListDeployedAppsInputSchema = z.object({
  server_name: z.string()
    .describe('Nome do servidor'),
});

export type ListDeployedAppsInput = z.infer<typeof ListDeployedAppsInputSchema>;

// ========================================
// Tool Handlers
// ========================================

/**
 * Tool: list-apps
 */
export class ListAppsTool {
  constructor(private client: APIClient) {}

  async execute(input: ListAppsInput): Promise<string> {
    try {
      // Get specific app details
      if (input.app_name) {
        const app = await this.client.get<any>(`/apps/${input.app_name}`);
        return this.formatAppDetails(app);
      }

      // List all apps (with optional category filter)
      let endpoint = '/apps';
      if (input.category) {
        endpoint += `?category=${input.category}`;
      }

      const apps = await this.client.get<{ apps: any[] }>(endpoint);

      if (!apps.apps || apps.apps.length === 0) {
        return '✅ Nenhuma aplicação encontrada no catálogo.';
      }

      let output = `✅ Aplicações Disponíveis: ${apps.apps.length}\n\n`;

      // Group by category
      const byCategory: Record<string, any[]> = {};
      for (const app of apps.apps) {
        const cat = app.category || 'other';
        if (!byCategory[cat]) {
          byCategory[cat] = [];
        }
        byCategory[cat].push(app);
      }

      // Format by category
      for (const [category, categoryApps] of Object.entries(byCategory)) {
        output += `📦 ${category.toUpperCase()}\n`;
        for (const app of categoryApps) {
          output += `   📱 ${app.name} - ${app.description || 'N/A'}\n`;
          if (app.version) {
            output += `      Version: ${app.version}\n`;
          }
        }
        output += '\n';
      }

      output += '💡 Use list-apps(app_name="nome") para detalhes completos.';

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  private formatAppDetails(app: any): string {
    let output = '✅ Detalhes da Aplicação\n\n';
    output += `📱 Nome: ${app.name}\n`;
    output += `📝 Descrição: ${app.description || 'N/A'}\n`;
    output += `🏷️  Categoria: ${app.category || 'N/A'}\n`;
    output += `📦 Versão: ${app.version || 'latest'}\n`;

    if (app.dependencies && app.dependencies.length > 0) {
      output += `\n🔗 Dependências (${app.dependencies.length}):\n`;
      for (const dep of app.dependencies) {
        if (typeof dep === 'string') {
          output += `   - ${dep}\n`;
        } else {
          output += `   - ${dep.name}`;
          if (dep.config) {
            output += ` (config: ${JSON.stringify(dep.config)})`;
          }
          output += '\n';
        }
      }
      output += '\n💡 Dependências serão instaladas automaticamente.\n';
    } else {
      output += '\n🔗 Dependências: Nenhuma\n';
    }

    if (app.requirements) {
      output += '\n📊 Requisitos:\n';
      if (app.requirements.min_ram_mb) {
        output += `   RAM: ${app.requirements.min_ram_mb} MB\n`;
      }
      if (app.requirements.min_cpu_cores) {
        output += `   CPU: ${app.requirements.min_cpu_cores} cores\n`;
      }
    }

    if (app.environment && Object.keys(app.environment).length > 0) {
      output += '\n🔧 Variáveis de Ambiente:\n';
      for (const [key, value] of Object.entries(app.environment)) {
        output += `   ${key}=${value}\n`;
      }
    }

    if (app.ports && app.ports.length > 0) {
      output += '\n🌐 Portas:\n';
      for (const port of app.ports) {
        output += `   - ${port}\n`;
      }
    }

    return output;
  }
}

/**
 * Tool: deploy-app (ASYNC)
 */
export class DeployAppTool {
  constructor(private client: APIClient) {}

  async execute(input: DeployAppInput): Promise<string> {
    try {
      const response = await this.client.post<{ job_id: string }>(
        `/apps/${input.app_name}/deploy`,
        {
          server_name: input.server_name,
          environment: input.environment || {},
        }
      );

      let output = '✅ Deploy da aplicação iniciado (operação assíncrona)\n\n';
      output += `🆔 Job ID: ${response.job_id}\n`;
      output += `📱 Aplicação: ${input.app_name}\n`;
      output += `📦 Servidor: ${input.server_name}\n\n`;
      output += '🔧 Etapas do deploy:\n';
      output += '   1️⃣  Verificação de requisitos\n';
      output += '   2️⃣  Instalação de dependências (se houver)\n';
      output += '   3️⃣  Configuração do ambiente\n';
      output += '   4️⃣  Deploy da aplicação\n';
      output += '   5️⃣  Health checks\n\n';
      output += '⏱️  Tempo estimado: 2-5 minutos\n\n';
      output += '💡 Use get-job-status para acompanhar o progresso:\n';
      output += `   get-job-status(job_id="${response.job_id}", tail_logs=50)`;

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}

/**
 * Tool: undeploy-app (ASYNC)
 */
export class UndeployAppTool {
  constructor(private client: APIClient) {}

  async execute(input: UndeployAppInput): Promise<string> {
    try {
      const response = await this.client.post<{ job_id: string }>(
        `/apps/${input.app_name}/undeploy`,
        {
          server_name: input.server_name,
        }
      );

      let output = '✅ Remoção da aplicação iniciada (operação assíncrona)\n\n';
      output += `🆔 Job ID: ${response.job_id}\n`;
      output += `📱 Aplicação: ${input.app_name}\n`;
      output += `📦 Servidor: ${input.server_name}\n\n`;
      output += '⚠️  ATENÇÃO: Esta operação removerá:\n';
      output += '   - Containers da aplicação\n';
      output += '   - Volumes de dados\n';
      output += '   - Configurações de rede\n';
      output += '   - Registros DNS (se configurados)\n\n';
      output += '⏱️  Tempo estimado: 1-2 minutos\n\n';
      output += '💡 Use get-job-status para acompanhar:\n';
      output += `   get-job-status(job_id="${response.job_id}")`;

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}

/**
 * Tool: list-deployed-apps
 */
export class ListDeployedAppsTool {
  constructor(private client: APIClient) {}

  async execute(input: ListDeployedAppsInput): Promise<string> {
    try {
      const apps = await this.client.get<{ apps: any[] }>(
        `/servers/${input.server_name}/apps`
      );

      if (!apps.apps || apps.apps.length === 0) {
        return `✅ Nenhuma aplicação instalada no servidor "${input.server_name}".\n\n💡 Use deploy-app para instalar aplicações.`;
      }

      let output = `✅ Aplicações Instaladas em "${input.server_name}": ${apps.apps.length}\n\n`;

      for (const app of apps.apps) {
        output += `📱 ${app.name}\n`;
        output += `   📊 Status: ${app.status || 'unknown'}\n`;

        if (app.domain) {
          output += `   🌐 Domínio: ${app.domain}\n`;
        }

        if (app.url) {
          output += `   🔗 URL: ${app.url}\n`;
        }

        if (app.installed_at) {
          output += `   🕐 Instalado em: ${app.installed_at}\n`;
        }

        if (app.version) {
          output += `   📦 Versão: ${app.version}\n`;
        }

        output += '\n';
      }

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }
}
