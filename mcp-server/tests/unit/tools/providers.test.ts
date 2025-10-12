/**
 * Tests for provider tool
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import {
  GetProviderInfoTool,
  GetProviderInfoInputSchema,
} from '../../../src/tools/providers.js';
import { APIClient } from '../../../src/api-client.js';

// Mock APIClient
function createMockClient(): APIClient {
  return new APIClient('http://localhost:8000');
}

describe('GetProviderInfoTool', () => {
  let tool: GetProviderInfoTool;
  let mockClient: APIClient;

  beforeEach(() => {
    mockClient = createMockClient();
    tool = new GetProviderInfoTool(mockClient);
  });

  describe('Input Schema', () => {
    it('should validate with default info_type', () => {
      const input = { provider: 'hetzner' };
      const result = GetProviderInfoInputSchema.parse(input);
      expect(result.info_type).toBe('all');
    });

    it('should validate with specific info_type', () => {
      const input = { provider: 'hetzner', info_type: 'regions' };
      const result = GetProviderInfoInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should reject invalid provider', () => {
      const input = { provider: 'invalid' };
      const result = GetProviderInfoInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it('should reject invalid info_type', () => {
      const input = { provider: 'hetzner', info_type: 'invalid' };
      const result = GetProviderInfoInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('execute - overview', () => {
    it('should get provider overview when configured', async () => {
      const mockOverview = {
        status: 'configured',
        token_configured: true,
        default_region: 'nbg1',
        default_server_type: 'cx11',
      };

      mockClient.get = jest.fn().mockResolvedValue(mockOverview);

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'overview',
      });

      expect(result).toContain('Overview do Provider: hetzner');
      expect(result).toContain('Token configurado: Sim');
      expect(result).toContain('nbg1');
      expect(result).toContain('cx11');
    });

    it('should show warning when provider not configured', async () => {
      const mockOverview = {
        status: 'not_configured',
        token_configured: false,
      };

      mockClient.get = jest.fn().mockResolvedValue(mockOverview);

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'overview',
      });

      expect(result).toContain('Provider não configurado');
      expect(result).toContain('manage-secrets');
      expect(result).toContain('hetzner_token');
    });
  });

  describe('execute - regions', () => {
    it('should list available regions', async () => {
      const mockRegions = {
        regions: [
          { id: 'nbg1', name: 'Nuremberg 1', location: 'Germany', city: 'Nuremberg', country: 'DE' },
          { id: 'fsn1', name: 'Falkenstein 1', location: 'Germany', city: 'Falkenstein', country: 'DE' },
          { id: 'hel1', name: 'Helsinki 1', location: 'Finland', city: 'Helsinki', country: 'FI' },
        ],
      };

      mockClient.get = jest.fn().mockResolvedValue(mockRegions);

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'regions',
      });

      expect(result).toContain('Regiões Disponíveis');
      expect(result).toContain('nbg1');
      expect(result).toContain('Nuremberg');
      expect(result).toContain('fsn1');
      expect(result).toContain('hel1');
      expect(result).toContain('Finland');
    });

    it('should handle empty regions', async () => {
      mockClient.get = jest.fn().mockResolvedValue({ regions: [] });

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'regions',
      });

      expect(result).toContain('Nenhuma região disponível');
    });
  });

  describe('execute - server-types', () => {
    it('should list available server types', async () => {
      const mockTypes = {
        server_types: [
          {
            id: 'cx11',
            name: 'CX11',
            description: 'Entry level',
            cores: 1,
            memory: 2,
            disk: 20,
            price: 3.29,
            currency: 'EUR',
            storage_type: 'local',
          },
          {
            id: 'cx21',
            name: 'CX21',
            description: 'Small instance',
            cores: 2,
            memory: 4,
            disk: 40,
            price: 5.83,
            currency: 'EUR',
            storage_type: 'local',
          },
        ],
      };

      mockClient.get = jest.fn().mockResolvedValue(mockTypes);

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'server-types',
      });

      expect(result).toContain('Tipos de Servidores Disponíveis');
      expect(result).toContain('CX11');
      expect(result).toContain('1 cores');
      expect(result).toContain('2 GB');
      expect(result).toContain('3.29');
      expect(result).toContain('CX21');
      expect(result).toContain('4 GB');
    });

    it('should handle empty server types', async () => {
      mockClient.get = jest.fn().mockResolvedValue({ server_types: [] });

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'server-types',
      });

      expect(result).toContain('Nenhum tipo de servidor disponível');
    });
  });

  describe('execute - all', () => {
    it('should get all information', async () => {
      const mockOverview = {
        status: 'configured',
        token_configured: true,
        default_region: 'nbg1',
      };

      const mockRegions = {
        regions: [
          { id: 'nbg1', name: 'Nuremberg 1', location: 'Germany' },
        ],
      };

      const mockTypes = {
        server_types: [
          { id: 'cx11', name: 'CX11', cores: 1, memory: 2 },
        ],
      };

      let callCount = 0;
      mockClient.get = jest.fn().mockImplementation((endpoint: string) => {
        if (endpoint.includes('/regions')) {
          return Promise.resolve(mockRegions);
        }
        if (endpoint.includes('/server-types')) {
          return Promise.resolve(mockTypes);
        }
        return Promise.resolve(mockOverview);
      });

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'all',
      });

      expect(result).toContain('Informações Completas: HETZNER');
      expect(result).toContain('Overview do Provider');
      expect(result).toContain('Regiões Disponíveis');
      expect(result).toContain('Tipos de Servidores Disponíveis');
      expect(result).toContain('nbg1');
      expect(result).toContain('CX11');
    });
  });

  describe('Error handling', () => {
    it('should format API errors nicely', async () => {
      const mockError = new Error('Provider not configured');
      mockClient.get = jest.fn().mockRejectedValue(mockError);

      const result = await tool.execute({
        provider: 'hetzner',
        info_type: 'overview',
      });

      expect(result).toContain('Error');
    });
  });
});
