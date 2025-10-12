/**
 * Tests for server tools (5 tools)
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import {
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
} from '../../../src/tools/servers.js';
import { APIClient } from '../../../src/api-client.js';

// Mock APIClient
function createMockClient(): APIClient {
  return new APIClient('http://localhost:8000');
}

describe('Server Tools', () => {
  let mockClient: APIClient;

  beforeEach(() => {
    mockClient = createMockClient();
  });

  // ========================================
  // Tool 1: create-server
  // ========================================
  describe('CreateServerTool', () => {
    let tool: CreateServerTool;

    beforeEach(() => {
      tool = new CreateServerTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate correct input', () => {
        const input = {
          name: 'test-server-01',
          server_type: 'cx11',
          region: 'nbg1',
        };
        const result = CreateServerInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should reject invalid server name (uppercase)', () => {
        const input = {
          name: 'Test-Server',
          server_type: 'cx11',
          region: 'nbg1',
        };
        const result = CreateServerInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });

      it('should reject server name too short', () => {
        const input = {
          name: 'ab',
          server_type: 'cx11',
          region: 'nbg1',
        };
        const result = CreateServerInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });

      it('should use default image', () => {
        const input = {
          name: 'test-server',
          server_type: 'cx11',
          region: 'nbg1',
        };
        const result = CreateServerInputSchema.parse(input);
        expect(result.image).toBe('debian-12');
      });
    });

    describe('execute', () => {
      it('should create server and return job_id', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ job_id: 'job-123' });

        const result = await tool.execute({
          name: 'test-server',
          server_type: 'cx11',
          region: 'nbg1',
          image: 'debian-12',
        });

        expect(result).toContain('job-123');
        expect(result).toContain('test-server');
        expect(result).toContain('cx11');
        expect(result).toContain('nbg1');
        expect(result).toContain('get-job-status');
        expect(mockClient.post).toHaveBeenCalledWith('/servers', {
          name: 'test-server',
          server_type: 'cx11',
          region: 'nbg1',
          image: 'debian-12',
        });
      });

      it('should handle errors gracefully', async () => {
        const mockError = new Error('Provider not configured');
        mockClient.post = jest.fn().mockRejectedValue(mockError);

        const result = await tool.execute({
          name: 'test-server',
          server_type: 'cx11',
          region: 'nbg1',
          image: 'debian-12',
        });

        expect(result).toContain('Error');
      });
    });
  });

  // ========================================
  // Tool 2: list-servers
  // ========================================
  describe('ListServersTool', () => {
    let tool: ListServersTool;

    beforeEach(() => {
      tool = new ListServersTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate empty input', () => {
        const input = {};
        const result = ListServersInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should validate with server_name', () => {
        const input = { server_name: 'test-server' };
        const result = ListServersInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should use default include_details=false', () => {
        const input = {};
        const result = ListServersInputSchema.parse(input);
        expect(result.include_details).toBe(false);
      });
    });

    describe('execute', () => {
      it('should list all servers', async () => {
        const mockServers = {
          servers: [
            { name: 'server-01', id: 'srv-1', ip_address: '1.2.3.4', status: 'running' },
            { name: 'server-02', id: 'srv-2', ip_address: '5.6.7.8', status: 'running' },
          ],
        };

        mockClient.get = jest.fn().mockResolvedValue(mockServers);

        const result = await tool.execute({ include_details: false });

        expect(result).toContain('server-01');
        expect(result).toContain('server-02');
        expect(result).toContain('1.2.3.4');
      });

      it('should show message when no servers exist', async () => {
        mockClient.get = jest.fn().mockResolvedValue({ servers: [] });

        const result = await tool.execute({ include_details: false });

        expect(result).toContain('Nenhum servidor encontrado');
        expect(result).toContain('create-server');
      });

      it('should get specific server details', async () => {
        const mockServer = {
          name: 'test-server',
          id: 'srv-123',
          ip_address: '1.2.3.4',
          status: 'running',
          server_type: 'cx11',
          region: 'nbg1',
          applications: ['traefik', 'portainer'],
        };

        mockClient.get = jest.fn().mockResolvedValue(mockServer);

        const result = await tool.execute({ server_name: 'test-server' });

        expect(result).toContain('Detalhes do Servidor');
        expect(result).toContain('test-server');
        expect(result).toContain('cx11');
        expect(result).toContain('traefik');
        expect(result).toContain('portainer');
      });
    });
  });

  // ========================================
  // Tool 3: configure-server-dns
  // ========================================
  describe('ConfigureServerDNSTool', () => {
    let tool: ConfigureServerDNSTool;

    beforeEach(() => {
      tool = new ConfigureServerDNSTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate with zone_name only', () => {
        const input = {
          server_name: 'test-server',
          zone_name: 'example.com',
        };
        const result = ConfigureServerDNSInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should validate with zone_name and subdomain', () => {
        const input = {
          server_name: 'test-server',
          zone_name: 'example.com',
          subdomain: 'lab',
        };
        const result = ConfigureServerDNSInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should require server_name and zone_name', () => {
        const input = { server_name: 'test' };
        const result = ConfigureServerDNSInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should configure DNS without subdomain', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ success: true });

        const result = await tool.execute({
          server_name: 'test-server',
          zone_name: 'example.com',
        });

        expect(result).toContain('Configuração DNS associada');
        expect(result).toContain('test-server');
        expect(result).toContain('example.com');
        expect(result).toContain('{app}.example.com');
      });

      it('should configure DNS with subdomain', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ success: true });

        const result = await tool.execute({
          server_name: 'test-server',
          zone_name: 'livchat.ai',
          subdomain: 'lab',
        });

        expect(result).toContain('Configuração DNS associada');
        expect(result).toContain('lab');
        expect(result).toContain('{app}.lab.livchat.ai');
        expect(result).toContain('n8n.lab.livchat.ai');
      });
    });
  });

  // ========================================
  // Tool 4: setup-server
  // ========================================
  describe('SetupServerTool', () => {
    let tool: SetupServerTool;

    beforeEach(() => {
      tool = new SetupServerTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should validate with defaults', () => {
        const input = { server_name: 'test-server' };
        const result = SetupServerInputSchema.parse(input);
        expect(result.ssl_email).toBe('admin@example.com');
        expect(result.network_name).toBe('livchat_network');
        expect(result.timezone).toBe('America/Sao_Paulo');
      });

      it('should allow custom values', () => {
        const input = {
          server_name: 'test-server',
          ssl_email: 'admin@livchat.ai',
          network_name: 'custom_network',
          timezone: 'UTC',
        };
        const result = SetupServerInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should reject invalid email', () => {
        const input = {
          server_name: 'test-server',
          ssl_email: 'not-an-email',
        };
        const result = SetupServerInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should setup server and return job_id', async () => {
        mockClient.post = jest.fn().mockResolvedValue({ job_id: 'job-456' });

        const result = await tool.execute({
          server_name: 'test-server',
          ssl_email: 'admin@example.com',
          network_name: 'livchat_network',
          timezone: 'America/Sao_Paulo',
        });

        expect(result).toContain('job-456');
        expect(result).toContain('test-server');
        expect(result).toContain('Traefik');
        expect(result).toContain('Portainer');
        expect(result).toContain('5-10 minutos');
      });
    });
  });

  // ========================================
  // Tool 5: delete-server
  // ========================================
  describe('DeleteServerTool', () => {
    let tool: DeleteServerTool;

    beforeEach(() => {
      tool = new DeleteServerTool(mockClient);
    });

    describe('Input Schema', () => {
      it('should require confirm=true', () => {
        const input = {
          server_name: 'test-server',
          confirm: true,
        };
        const result = DeleteServerInputSchema.safeParse(input);
        expect(result.success).toBe(true);
      });

      it('should reject confirm=false', () => {
        const input = {
          server_name: 'test-server',
          confirm: false,
        };
        const result = DeleteServerInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });

      it('should reject missing confirm', () => {
        const input = {
          server_name: 'test-server',
        };
        const result = DeleteServerInputSchema.safeParse(input);
        expect(result.success).toBe(false);
      });
    });

    describe('execute', () => {
      it('should delete server and return job_id', async () => {
        mockClient.delete = jest.fn().mockResolvedValue({ job_id: 'job-789' });

        const result = await tool.execute({
          server_name: 'test-server',
          confirm: true,
        });

        expect(result).toContain('job-789');
        expect(result).toContain('test-server');
        expect(result).toContain('IRREVERSÍVEL');
        expect(result).toContain('dados serão perdidos');
      });
    });
  });
});
