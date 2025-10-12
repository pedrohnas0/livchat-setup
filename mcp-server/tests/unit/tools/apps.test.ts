/**
 * Tests for app tools (4 tools)
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import {
  ListAppsTool,
  ListAppsInputSchema,
  DeployAppTool,
  DeployAppInputSchema,
  UndeployAppTool,
  UndeployAppInputSchema,
  ListDeployedAppsTool,
  ListDeployedAppsInputSchema,
} from '../../../src/tools/apps.js';
import { APIClient } from '../../../src/api-client.js';

// Mock APIClient
function createMockClient(): APIClient {
  return new APIClient('http://localhost:8000');
}

describe('App Tools', () => {
  let mockClient: APIClient;

  beforeEach(() => {
    mockClient = createMockClient();
  });

  // ========================================
  // Tool 1: list-apps
  // ========================================
  describe('ListAppsTool', () => {
    let tool: ListAppsTool;

    beforeEach(() => {
      tool = new ListAppsTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate empty input', () => {
        const input = {};
        const result = ListAppsInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should validate with app_name', () => {
        const input = { app_name: 'n8n' };
        const result = ListAppsInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should validate with category filter', () => {
        const input = { category: 'databases' };
        const result = ListAppsInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should reject invalid category', () => {
        const input = { category: 'invalid' };
        const result = ListAppsInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should list all apps', async () => {
        const mockApps = {
          apps: [
            { name: 'postgres', description: 'PostgreSQL database', category: 'databases', version: '14' },
            { name: 'redis', description: 'Redis cache', category: 'databases', version: 'latest' },
            { name: 'n8n', description: 'Workflow automation', category: 'applications', version: 'latest' },
          ],
        };

        mockClient.get = jest.fn().mockResolvedValue(mockApps);

        const result = await tool.execute({});

        expect(result).toContain('Aplicações Disponíveis: 3');
        expect(result).toContain('postgres');
        expect(result).toContain('redis');
        expect(result).toContain('n8n');
        expect(result).toContain('DATABASES');
        expect(result).toContain('APPLICATIONS');
      });

      it('should show message when no apps exist', async () => {
        mockClient.get = jest.fn().mockResolvedValue({ apps: [] });

        const result = await tool.execute({});

        expect(result).toContain('Nenhuma aplicação encontrada');
      });

      it('should get specific app details', async () => {
        const mockApp = {
          name: 'n8n',
          description: 'Workflow automation platform',
          category: 'applications',
          version: 'latest',
          dependencies: ['postgres', 'redis'],
          requirements: {
            min_ram_mb: 1024,
            min_cpu_cores: 1,
          },
          environment: {
            N8N_HOST: 'n8n.example.com',
          },
          ports: ['5678:5678'],
        };

        mockClient.get = jest.fn().mockResolvedValue(mockApp);

        const result = await tool.execute({ app_name: 'n8n' });

        expect(result).toContain('Detalhes da Aplicação');
        expect(result).toContain('n8n');
        expect(result).toContain('Workflow automation');
        expect(result).toContain('postgres');
        expect(result).toContain('redis');
        expect(result).toContain('1024 MB');
        expect(result).toContain('N8N_HOST');
      });
    });
  });

  // ========================================
  // Tool 2: deploy-app
  // ========================================
  describe('DeployAppTool', () => {
    let tool: DeployAppTool;

    beforeEach(() => {
      tool = new DeployAppTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate correct input', () => {
        const input = {
          app_name: 'n8n',
          server_name: 'test-server',
        };
        const result = DeployAppInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should validate with environment variables', () => {
        const input = {
          app_name: 'n8n',
          server_name: 'test-server',
          environment: {
            N8N_HOST: 'n8n.custom.com',
            N8N_PORT: '5678',
          },
        };
        const result = DeployAppInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should require app_name and server_name', () => {
        const input = { app_name: 'n8n' };
        const result = DeployAppInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should deploy app and return job_id', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ job_id: 'job-123' });

        const result = await tool.execute({
          app_name: 'n8n',
          server_name: 'test-server',
        });

        expect(result).toContain('job-123');
        expect(result).toContain('n8n');
        expect(result).toContain('test-server');
        expect(result).toContain('dependências');
        expect(result).toContain('2-5 minutos');
        expect(mockClient.post).toHaveBeenCalledWith('/apps/n8n/deploy', {
          server_name: 'test-server',
          environment: {},
        });
      });

      it('should deploy app with custom environment', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ job_id: 'job-456' });

        const customEnv = { N8N_HOST: 'custom.com' };
        const result = await tool.execute({
          app_name: 'n8n',
          server_name: 'test-server',
          environment: customEnv,
        });

        expect(result).toContain('job-456');
        expect(mockClient.post).toHaveBeenCalledWith('/apps/n8n/deploy', {
          server_name: 'test-server',
          environment: customEnv,
        });
      });
    });
  });

  // ========================================
  // Tool 3: undeploy-app
  // ========================================
  describe('UndeployAppTool', () => {
    let tool: UndeployAppTool;

    beforeEach(() => {
      tool = new UndeployAppTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should require confirm=true', () => {
        const input = {
          app_name: 'n8n',
          server_name: 'test-server',
          confirm: true,
        };
        const result = UndeployAppInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should reject confirm=false', () => {
        const input = {
          app_name: 'n8n',
          server_name: 'test-server',
          confirm: false,
        };
        const result = UndeployAppInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });

      it('should reject missing confirm', () => {
        const input = {
          app_name: 'n8n',
          server_name: 'test-server',
        };
        const result = UndeployAppInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should undeploy app and return job_id', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ job_id: 'job-789' });

        const result = await tool.execute({
          app_name: 'n8n',
          server_name: 'test-server',
          confirm: true,
        });

        expect(result).toContain('job-789');
        expect(result).toContain('n8n');
        expect(result).toContain('test-server');
        expect(result).toContain('ATENÇÃO');
        expect(result).toContain('Containers');
        expect(result).toContain('Volumes');
      });
    });
  });

  // ========================================
  // Tool 4: list-deployed-apps
  // ========================================
  describe('ListDeployedAppsTool', () => {
    let tool: ListDeployedAppsTool;

    beforeEach(() => {
      tool = new ListDeployedAppsTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate with server_name', () => {
        const input = { server_name: 'test-server' };
        const result = ListDeployedAppsInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should require server_name', () => {
        const input = {};
        const result = ListDeployedAppsInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should list deployed apps', async () => {
        const mockApps = {
          apps: [
            {
              name: 'traefik',
              status: 'running',
              domain: 'traefik.example.com',
              url: 'https://traefik.example.com',
              installed_at: '2024-01-10T10:00:00Z',
              version: 'latest',
            },
            {
              name: 'portainer',
              status: 'running',
              domain: 'portainer.example.com',
              url: 'https://portainer.example.com',
              installed_at: '2024-01-10T10:05:00Z',
              version: 'latest',
            },
          ],
        };

        mockClient.get = jest.fn().mockResolvedValue(mockApps);

        const result = await tool.execute({ server_name: 'test-server' });

        expect(result).toContain('Aplicações Instaladas');
        expect(result).toContain('test-server');
        expect(result).toContain('traefik');
        expect(result).toContain('portainer');
        expect(result).toContain('running');
        expect(result).toContain('traefik.example.com');
      });

      it('should show message when no apps are deployed', async () => {
        mockClient.get = jest.fn().mockResolvedValue({ apps: [] });

        const result = await tool.execute({ server_name: 'test-server' });

        expect(result).toContain('Nenhuma aplicação instalada');
        expect(result).toContain('test-server');
        expect(result).toContain('deploy-app');
      });
    });
  });
});
