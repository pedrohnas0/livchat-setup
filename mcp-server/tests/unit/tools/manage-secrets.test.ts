/**
 * Tests for manage-secrets tool
 */

import { describe, it, expect, beforeEach } from '@jest/globals';
import { ManageSecretsTool, ManageSecretsInputSchema } from '../../../src/tools/manage-secrets.js';
import { APIClient } from '../../../src/api-client.js';

// Mock APIClient
function createMockClient(): APIClient {
  const client = new APIClient('http://localhost:8000');
  return client;
}

describe('ManageSecretsTool', () => {
  let tool: ManageSecretsTool;
  let mockClient: APIClient;

  beforeEach(() => {
    mockClient = createMockClient();
    tool = new ManageSecretsTool(mockClient);
  });

  describe('Input Schema', () => {
    it('should validate list action', () => {
      const input = { action: 'list' };
      const result = ManageSecretsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate get action with key and vault_password', () => {
      const input = {
        action: 'get',
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      };
      const result = ManageSecretsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate set action with all required fields', () => {
      const input = {
        action: 'set',
        key: 'hetzner_api_token',
        value: 'xxx-yyy-zzz',
        vault_password: 'secret123'
      };
      const result = ManageSecretsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should validate delete action', () => {
      const input = {
        action: 'delete',
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      };
      const result = ManageSecretsInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it('should reject invalid action', () => {
      const input = { action: 'update' };
      const result = ManageSecretsInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe('execute - list action', () => {
    it('should list all secret keys', async () => {
      const mockSecrets = {
        keys: ['hetzner_api_token', 'cloudflare_api_token', 'portainer_admin_password']
      };

      mockClient.get = jest.fn().mockResolvedValue(mockSecrets);

      const result = await tool.execute({ action: 'list' });

      expect(result).toContain('Stored Secret Keys');
      expect(result).toContain('hetzner_api_token');
      expect(result).toContain('cloudflare_api_token');
      expect(result).toContain('portainer_admin_password');
    });

    it('should show message when no secrets exist', async () => {
      const mockSecrets = { keys: [] };

      mockClient.get = jest.fn().mockResolvedValue(mockSecrets);

      const result = await tool.execute({ action: 'list' });

      expect(result).toContain('No secrets stored');
      expect(result).toContain('Use action: set');
    });
  });

  describe('execute - get action', () => {
    it('should get a decrypted secret', async () => {
      const mockResponse = {
        key: 'hetzner_api_token',
        value: 'xxx-yyy-zzz'
      };

      mockClient.post = jest.fn().mockResolvedValue(mockResponse);

      const result = await tool.execute({
        action: 'get',
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      });

      expect(result).toContain('Secret Retrieved');
      expect(result).toContain('hetzner_api_token');
      expect(result).toContain('xxx-yyy-zzz');
      expect(mockClient.post).toHaveBeenCalledWith('/secrets/get', {
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      });
    });

    it('should return error when key is missing', async () => {
      const result = await tool.execute({
        action: 'get',
        vault_password: 'secret123'
      });

      expect(result).toContain('key parameter is required');
    });

    it('should return error when vault_password is missing', async () => {
      const result = await tool.execute({
        action: 'get',
        key: 'hetzner_api_token'
      });

      expect(result).toContain('vault_password parameter is required');
    });
  });

  describe('execute - set action', () => {
    it('should set an encrypted secret', async () => {
      mockClient.post = jest.fn().mockResolvedValue({ success: true });

      const result = await tool.execute({
        action: 'set',
        key: 'hetzner_api_token',
        value: 'xxx-yyy-zzz',
        vault_password: 'secret123'
      });

      expect(result).toContain('Secret Stored Successfully');
      expect(result).toContain('hetzner_api_token');
      expect(result).toContain('[ENCRYPTED]');
      expect(result).not.toContain('xxx-yyy-zzz'); // Should not show plain value
      expect(mockClient.post).toHaveBeenCalledWith('/secrets/set', {
        key: 'hetzner_api_token',
        value: 'xxx-yyy-zzz',
        vault_password: 'secret123'
      });
    });

    it('should return error when key is missing', async () => {
      const result = await tool.execute({
        action: 'set',
        value: 'xxx-yyy-zzz',
        vault_password: 'secret123'
      });

      expect(result).toContain('key parameter is required');
    });

    it('should return error when value is missing', async () => {
      const result = await tool.execute({
        action: 'set',
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      });

      expect(result).toContain('value parameter is required');
    });

    it('should return error when vault_password is missing', async () => {
      const result = await tool.execute({
        action: 'set',
        key: 'hetzner_api_token',
        value: 'xxx-yyy-zzz'
      });

      expect(result).toContain('vault_password parameter is required');
    });
  });

  describe('execute - delete action', () => {
    it('should delete a secret', async () => {
      mockClient.post = jest.fn().mockResolvedValue({ success: true });

      const result = await tool.execute({
        action: 'delete',
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      });

      expect(result).toContain('Secret Deleted');
      expect(result).toContain('hetzner_api_token');
      expect(mockClient.post).toHaveBeenCalledWith('/secrets/delete', {
        key: 'hetzner_api_token',
        vault_password: 'secret123'
      });
    });

    it('should return error when key is missing', async () => {
      const result = await tool.execute({
        action: 'delete',
        vault_password: 'secret123'
      });

      expect(result).toContain('key parameter is required');
    });

    it('should return error when vault_password is missing', async () => {
      const result = await tool.execute({
        action: 'delete',
        key: 'hetzner_api_token'
      });

      expect(result).toContain('vault_password parameter is required');
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

    it('should handle authentication errors', async () => {
      const mockError = {
        status: 401,
        message: 'Invalid vault password'
      };
      mockClient.post = jest.fn().mockRejectedValue(mockError);

      const result = await tool.execute({
        action: 'get',
        key: 'hetzner_api_token',
        vault_password: 'wrong'
      });

      expect(result).toContain('Error');
    });
  });
});
