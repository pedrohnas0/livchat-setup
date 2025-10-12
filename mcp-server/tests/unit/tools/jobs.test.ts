/**
 * Tests for job tools (2 tools)
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import {
  GetJobStatusTool,
  GetJobStatusInputSchema,
  ListJobsTool,
  ListJobsInputSchema,
} from '../../../src/tools/jobs.js';
import { APIClient } from '../../../src/api-client.js';

// Mock APIClient
function createMockClient(): APIClient {
  return new APIClient('http://localhost:8000');
}

describe('Job Tools', () => {
  let mockClient: APIClient;

  beforeEach(() => {
    mockClient = createMockClient();
  });

  // ========================================
  // Tool 1: get-job-status
  // ========================================
  describe('GetJobStatusTool', () => {
    let tool: GetJobStatusTool;

    beforeEach(() => {
      tool = new GetJobStatusTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate with job_id only', () => {
        const input = { job_id: 'job-123' };
        const result = GetJobStatusInputSchema.parse(input);
        expect(result.tail_logs).toBe(null);
      });

      it('should validate with tail_logs', () => {
        const input = { job_id: 'job-123', tail_logs: 50 };
        const result = GetJobStatusInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should allow tail_logs values: 0, 50, 100, null', () => {
        expect(GetJobStatusInputSchema.safeParse({ job_id: 'j1', tail_logs: 0 }).success).toBe(true);
        expect(GetJobStatusInputSchema.safeParse({ job_id: 'j1', tail_logs: 50 }).success).toBe(true);
        expect(GetJobStatusInputSchema.safeParse({ job_id: 'j1', tail_logs: 100 }).success).toBe(true);
        expect(GetJobStatusInputSchema.safeParse({ job_id: 'j1', tail_logs: null }).success).toBe(true);
      });

      it('should reject invalid tail_logs value', () => {
        const input = { job_id: 'job-123', tail_logs: 25 };
        const result = GetJobStatusInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should get pending job status', async () => {
        const mockJob = {
          job_id: 'job-123',
          status: 'pending',
          operation: 'create_server',
          server_name: 'test-server',
          created_at: '2024-01-10T10:00:00Z',
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJob);

        const result = await tool.execute({ job_id: 'job-123', tail_logs: null });

        expect(result).toContain('Status do Job');
        expect(result).toContain('job-123');
        expect(result).toContain('Pending');
        expect(result).toContain('create_server');
        expect(result).toContain('test-server');
        expect(result).toContain('aguardando execução');
      });

      it('should get running job status with progress', async () => {
        const mockJob = {
          job_id: 'job-456',
          status: 'running',
          operation: 'setup_server',
          server_name: 'test-server',
          progress: 45,
          step: 'Installing Docker',
          created_at: '2024-01-10T10:00:00Z',
          started_at: '2024-01-10T10:01:00Z',
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJob);

        const result = await tool.execute({ job_id: 'job-456', tail_logs: null });

        expect(result).toContain('job-456');
        expect(result).toContain('Running');
        expect(result).toContain('45%');
        expect(result).toContain('Installing Docker');
        expect(result).toContain('ainda está em execução');
      });

      it('should get completed job status with result', async () => {
        const mockJob = {
          job_id: 'job-789',
          status: 'completed',
          operation: 'create_server',
          server_name: 'test-server',
          progress: 100,
          created_at: '2024-01-10T10:00:00Z',
          started_at: '2024-01-10T10:01:00Z',
          completed_at: '2024-01-10T10:05:00Z',
          elapsed_time: 240,
          result: {
            server_id: 'srv-123',
            ip_address: '1.2.3.4',
          },
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJob);

        const result = await tool.execute({ job_id: 'job-789', tail_logs: null });

        expect(result).toContain('job-789');
        expect(result).toContain('Completed');
        expect(result).toContain('100%');
        expect(result).toContain('Resultado');
        expect(result).toContain('srv-123');
        expect(result).toContain('1.2.3.4');
        expect(result).toContain('concluído com sucesso');
      });

      it('should get failed job status with error', async () => {
        const mockJob = {
          job_id: 'job-error',
          status: 'failed',
          operation: 'create_server',
          server_name: 'test-server',
          progress: 30,
          created_at: '2024-01-10T10:00:00Z',
          started_at: '2024-01-10T10:01:00Z',
          error: 'Provider API returned 401: Invalid token',
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJob);

        const result = await tool.execute({ job_id: 'job-error', tail_logs: null });

        expect(result).toContain('job-error');
        expect(result).toContain('Failed');
        expect(result).toContain('Erro');
        expect(result).toContain('Invalid token');
        expect(result).toContain('falhou');
      });

      it('should include logs when tail_logs is set', async () => {
        const mockJob = {
          job_id: 'job-logs',
          status: 'running',
          operation: 'setup_server',
          progress: 60,
          logs: [
            '[2024-01-10 10:01:00] Starting setup',
            '[2024-01-10 10:02:00] Updating system',
            '[2024-01-10 10:03:00] Installing Docker',
          ],
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJob);

        const result = await tool.execute({ job_id: 'job-logs', tail_logs: 50 });

        expect(result).toContain('Logs');
        expect(result).toContain('Starting setup');
        expect(result).toContain('Updating system');
        expect(result).toContain('Installing Docker');
      });
    });
  });

  // ========================================
  // Tool 2: list-jobs
  // ========================================
  describe('ListJobsTool', () => {
    let tool: ListJobsTool;

    beforeEach(() => {
      tool = new ListJobsTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate with defaults', () => {
        const input = {};
        const result = ListJobsInputSchema.parse(input);
        expect(result.limit).toBe(100);
      });

      it('should validate with status filter', () => {
        const input = { status: 'completed' };
        const result = ListJobsInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should validate with custom limit', () => {
        const input = { limit: 50 };
        const result = ListJobsInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should reject limit > 1000', () => {
        const input = { limit: 1001 };
        const result = ListJobsInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });

      it('should reject limit < 1', () => {
        const input = { limit: 0 };
        const result = ListJobsInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });

      it('should reject invalid status', () => {
        const input = { status: 'invalid' };
        const result = ListJobsInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should list all jobs', async () => {
        const mockJobs = {
          jobs: [
            {
              job_id: 'job-1',
              status: 'completed',
              operation: 'create_server',
              server_name: 'server-01',
              created_at: '2024-01-10T10:00:00Z',
            },
            {
              job_id: 'job-2',
              status: 'running',
              operation: 'deploy_app',
              server_name: 'server-01',
              app_name: 'n8n',
              progress: 50,
              created_at: '2024-01-10T11:00:00Z',
            },
          ],
          total: 2,
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJobs);

        const result = await tool.execute({ limit: 100 });

        expect(result).toContain('Jobs Encontrados: 2');
        expect(result).toContain('job-1');
        expect(result).toContain('Completed');
        expect(result).toContain('job-2');
        expect(result).toContain('Running');
        expect(result).toContain('50%');
        expect(result).toContain('n8n');
      });

      it('should list jobs filtered by status', async () => {
        const mockJobs = {
          jobs: [
            {
              job_id: 'job-completed-1',
              status: 'completed',
              operation: 'create_server',
              created_at: '2024-01-10T10:00:00Z',
            },
          ],
          total: 1,
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJobs);

        const result = await tool.execute({ status: 'completed', limit: 100 });

        expect(result).toContain('Status: completed');
        expect(result).toContain('job-completed-1');
        expect(mockClient.get).toHaveBeenCalledWith('/jobs?limit=100&status=completed');
      });

      it('should show message when no jobs exist', async () => {
        mockClient.get = jest.fn().mockResolvedValue({ jobs: [], total: 0 });

        const result = await tool.execute({ limit: 100 });

        expect(result).toContain('Nenhum job encontrado');
      });

      it('should show message when no jobs match filter', async () => {
        mockClient.get = jest.fn().mockResolvedValue({ jobs: [], total: 0 });

        const result = await tool.execute({ status: 'failed', limit: 100 });

        expect(result).toContain('Nenhum job encontrado');
        expect(result).toContain('failed');
      });

      it('should show total when more jobs exist', async () => {
        const mockJobs = {
          jobs: Array(100).fill(null).map((_, i) => ({
            job_id: `job-${i}`,
            status: 'completed',
            created_at: '2024-01-10T10:00:00Z',
          })),
          total: 250,
        };

        mockClient.get = jest.fn().mockResolvedValue(mockJobs);

        const result = await tool.execute({ limit: 100 });

        expect(result).toContain('100 de 250 total');
      });
    });
  });
});
