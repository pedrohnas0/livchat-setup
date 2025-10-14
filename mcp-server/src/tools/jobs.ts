/**
 * Tools: Job Management (2 tools)
 *
 * 1. get-job-status
 * 2. list-jobs
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

// ========================================
// Schemas
// ========================================

/**
 * Schema for get-job-status tool
 */
export const GetJobStatusInputSchema = z.object({
  job_id: z.string()
    .describe('ID do job retornado por operações assíncronas'),
  tail_logs: z.union([z.literal(0), z.literal(50), z.literal(100), z.null()])
    .default(null)
    .describe('Qtd de linhas de log: 0=todas, 50, 100, null=sem logs (padrão: null para economizar tokens)'),
});

export type GetJobStatusInput = z.infer<typeof GetJobStatusInputSchema>;

/**
 * Schema for list-jobs tool
 */
export const ListJobsInputSchema = z.object({
  status: z.enum(['pending', 'running', 'completed', 'failed', 'cancelled']).optional()
    .describe('Filtrar por status (opcional)'),
  limit: z.number()
    .min(1)
    .max(1000)
    .default(100)
    .describe('Máximo de jobs (padrão: 100, máx: 1000)'),
});

export type ListJobsInput = z.infer<typeof ListJobsInputSchema>;

// ========================================
// Tool Handlers
// ========================================

/**
 * Tool: get-job-status
 */
export class GetJobStatusTool {
  constructor(private client: APIClient) {}

  async execute(input: GetJobStatusInput): Promise<string> {
    try {
      let endpoint = `/jobs/${input.job_id}`;
      if (input.tail_logs !== null) {
        endpoint += `?tail_logs=${input.tail_logs}`;
      }

      const job = await this.client.get<any>(endpoint);

      return this.formatJobStatus(job);
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  private formatJobStatus(job: any): string {
    let output = '✅ Status do Job\n\n';
    output += `🆔 Job ID: ${job.job_id}\n`;
    output += `📊 Status: ${this.formatStatus(job.status)}\n`;

    // Show step information (Etapa X/Y) if available
    if (job.total_steps && job.total_steps > 0) {
      const stepNum = job.current_step_num || 0;
      const stepName = job.step_name || job.current_step || 'Em andamento';
      output += `📍 Etapa: ${stepNum}/${job.total_steps} - ${stepName}\n`;
    } else if (job.current_step || job.step) {
      // Fallback for jobs without step tracking
      output += `🔄 Etapa atual: ${job.current_step || job.step}\n`;
    }

    if (job.progress !== undefined) {
      const progressBar = this.createProgressBar(job.progress);
      output += `📈 Progresso: ${progressBar} ${job.progress}%\n`;
    }

    if (job.operation) {
      output += `🔧 Operação: ${job.operation}\n`;
    }

    if (job.server_name) {
      output += `📦 Servidor: ${job.server_name}\n`;
    }

    if (job.app_name) {
      output += `📱 Aplicação: ${job.app_name}\n`;
    }

    if (job.created_at) {
      output += `🕐 Criado em: ${job.created_at}\n`;
    }

    if (job.started_at) {
      output += `▶️  Iniciado em: ${job.started_at}\n`;
    }

    if (job.completed_at) {
      output += `✅ Concluído em: ${job.completed_at}\n`;
    }

    if (job.elapsed_time) {
      output += `⏱️  Tempo decorrido: ${job.elapsed_time}s\n`;
    }

    // Error information
    if (job.status === 'failed' && job.error) {
      output += `\n❌ Erro:\n${job.error}\n`;
    }

    // Result information
    if (job.status === 'completed' && job.result) {
      output += '\n🎉 Resultado:\n';
      if (typeof job.result === 'string') {
        output += `${job.result}\n`;
      } else {
        output += `${JSON.stringify(job.result, null, 2)}\n`;
      }
    }

    // Logs
    if (job.logs && job.logs.length > 0) {
      output += '\n📋 Logs:\n';
      output += '```\n';
      for (const log of job.logs) {
        if (typeof log === 'string') {
          output += `${log}\n`;
        } else if (log && typeof log === 'object') {
          // Handle {timestamp, message} format
          const timestamp = log.timestamp || '';
          const message = log.message || JSON.stringify(log);
          if (timestamp) {
            output += `[${timestamp}] ${message}\n`;
          } else {
            output += `${message}\n`;
          }
        }
      }
      output += '```\n';
    }

    // Status-specific suggestions
    if (job.status === 'running') {
      output += '\n💡 O job ainda está em execução. Use get-job-status novamente para verificar o progresso.';
    } else if (job.status === 'pending') {
      output += '\n💡 O job está aguardando execução. Aguarde alguns momentos e verifique novamente.';
    } else if (job.status === 'failed') {
      output += '\n💡 O job falhou. Verifique os logs acima para detalhes do erro.';
    } else if (job.status === 'completed') {
      output += '\n🎉 Job concluído com sucesso!';
    }

    return output;
  }

  private formatStatus(status: string): string {
    const statusEmojis: Record<string, string> = {
      pending: '⏳ Pending',
      running: '▶️  Running',
      completed: '✅ Completed',
      failed: '❌ Failed',
      cancelled: '🚫 Cancelled',
    };
    return statusEmojis[status] || status;
  }

  private createProgressBar(progress: number): string {
    const width = 20;
    const filled = Math.floor((progress / 100) * width);
    const empty = width - filled;
    return '[' + '█'.repeat(filled) + '░'.repeat(empty) + ']';
  }
}

/**
 * Tool: list-jobs
 */
export class ListJobsTool {
  constructor(private client: APIClient) {}

  async execute(input: ListJobsInput): Promise<string> {
    try {
      let endpoint = `/jobs?limit=${input.limit}`;
      if (input.status) {
        endpoint += `&status=${input.status}`;
      }

      const jobs = await this.client.get<{ jobs: any[]; total: number }>(endpoint);

      if (!jobs.jobs || jobs.jobs.length === 0) {
        let message = '✅ Nenhum job encontrado';
        if (input.status) {
          message += ` com status "${input.status}"`;
        }
        return message + '.';
      }

      let output = '✅ Jobs Encontrados';
      if (input.status) {
        output += ` (Status: ${input.status})`;
      }
      output += `: ${jobs.jobs.length}`;
      if (jobs.total && jobs.total > jobs.jobs.length) {
        output += ` de ${jobs.total} total`;
      }
      output += '\n\n';

      for (const job of jobs.jobs) {
        output += `🆔 ${job.job_id}\n`;
        output += `   📊 Status: ${this.formatStatus(job.status)}`;

        if (job.progress !== undefined && job.status === 'running') {
          output += ` (${job.progress}%)`;
        }

        output += '\n';

        if (job.operation) {
          output += `   🔧 ${job.operation}`;
        }

        if (job.server_name) {
          output += ` → ${job.server_name}`;
        }

        if (job.app_name) {
          output += ` (${job.app_name})`;
        }

        if (job.operation || job.server_name || job.app_name) {
          output += '\n';
        }

        if (job.created_at) {
          output += `   🕐 ${job.created_at}\n`;
        }

        output += '\n';
      }

      output += '💡 Use get-job-status(job_id="xxx") para detalhes completos de um job.';

      return output;
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  private formatStatus(status: string): string {
    const statusEmojis: Record<string, string> = {
      pending: '⏳ Pending',
      running: '▶️  Running',
      completed: '✅ Completed',
      failed: '❌ Failed',
      cancelled: '🚫 Cancelled',
    };
    return statusEmojis[status] || status;
  }
}
