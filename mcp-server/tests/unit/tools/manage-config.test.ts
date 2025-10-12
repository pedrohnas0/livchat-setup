/**
 * Tests for manage-config tool
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import { ManageConfigTool, ManageConfigInputSchema } from '../../../src/tools/manage-config.js';
import { APIClient } from '../../../src/api-client.js';

// Mock APIClient
function createMockClient(): APIClient {
  const client = new APIClient('http://localhost:8000');
  return client;
}

describe('ManageConfigTool', () => {
  let tool: ManageConfigTool;
  let mockClient: APIClient;

  beforeEach(() => {
    mockClient = createMockClient();
    tool = new ManageConfigTool(mockClient);
  });

  describe('Input Schema', () => {
    it('should validate correct list action', () => {
      const input = { action: 'list' };
      const result = ManageConfigInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate correct get action', () => {
      const input = { action: 'get', key: 'general.default_provider' };
      const result = ManageConfigInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate correct set action', () => {
      const input = { action: 'set', key: 'general.default_provider', value: 'hetzner' };
      const result = ManageConfigInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should reject invalid action', () => {
      const input = { action: 'delete' };
      const result = ManageConfigInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('execute - list action', () => {
    it('should list all configuration keys', async () => {
      const mockConfig = {
        general: {
          default_provider: 'hetzner',
          default_region: 'nbg1'
        },
        providers: {
          hetzner: {
            regions: ['nbg1', 'fsn1']
          }
        }
      };

      mockClient.get = jest.fn().mockResolvedValue(mockConfig);

      const result = await tool.execute({ action: 'list' });

      expect(result).toContain('Configuration Keys');
      expect(result).toContain('general.default_provider');
      expect(result).toContain('providers.hetzner');
    });
  });

  describe('execute - get action', () => {
    it('should get a specific configuration value', async () => {
      const mockConfig = {
        general: {
          default_provider: 'hetzner'
        }
      };

      mockClient.get = jest.fn().mockResolvedValue(mockConfig);

      const result = await tool.execute({
        action: 'get',
        key: 'general.default_provider'
      });

      expect(result).toContain('Configuration Value');
      expect(result).toContain('general.default_provider');
      expect(result).toContain('hetzner');
    });

    it('should return error when key is missing', async () => {
      const result = await tool.execute({ action: 'get' });

      expect(result).toContain('key parameter is required');
    });

    it('should return error when key is not found', async () => {
      const mockConfig = {
        general: {
          default_provider: 'hetzner'
        }
      };

      mockClient.get = jest.fn().mockResolvedValue(mockConfig);

      const result = await tool.execute({
        action: 'get',
        key: 'nonexistent.key'
      });

      expect(result).toContain('not found');
      expect(result).toContain('nonexistent.key');
    });
  });

  describe('execute - set action', () => {
    it('should set a configuration value', async () => {
      mockClient.post = jest.fn().mockResolvedValue({ success: true });

      const result = await tool.execute({
        action: 'set',
        key: 'general.default_provider',
        value: 'digitalocean'
      });

      expect(result).toContain('Configuration Updated');
      expect(result).toContain('general.default_provider');
      expect(result).toContain('digitalocean');
      expect(mockClient.post).toHaveBeenCalledWith('/config', {
        key: 'general.default_provider',
        value: 'digitalocean'
      });
    });

    it('should return error when key is missing', async () => {
      const result = await tool.execute({
        action: 'set',
        value: 'hetzner'
      });

      expect(result).toContain('key parameter is required');
    });

    it('should return error when value is missing', async () => {
      const result = await tool.execute({
        action: 'set',
        key: 'general.default_provider'
      });

      expect(result).toContain('value parameter is required');
    });
  });

  describe('Error handling', () => {
    it('should format API errors nicely', async () => {
      const mockError = new Error('Network error: ECONNREFUSED');
      mockClient.get = jest.fn().mockRejectedValue(mockError);

      const result = await tool.execute({ action: 'list' });

      expect(result).toContain('Error');
      expect(result).toContain('Type: network_error');
    });
  });
});
