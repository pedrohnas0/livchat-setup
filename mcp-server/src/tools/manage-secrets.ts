/**
 * Tool: manage-secrets
 *
 * Manages encrypted secrets in Ansible Vault for LivChatSetup
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

/**
 * Input schema for manage-secrets tool
 */
export const ManageSecretsInputSchema = z.object({
  action: z.enum(['list', 'get', 'set', 'delete']).describe('Action: list, get, set, or delete secrets'),
  key: z.string().optional().describe('Secret key (e.g., "hetzner_token", "cloudflare_api_key")'),
  value: z.string().optional().describe('Secret value (for set action) - will be encrypted'),
});

export type ManageSecretsInput = z.infer<typeof ManageSecretsInputSchema>;

/**
 * Tool handler for manage-secrets
 */
export class ManageSecretsTool {
  constructor(private client: APIClient) {}

  /**
   * Execute the manage-secrets tool
   */
  async execute(input: ManageSecretsInput): Promise<string> {
    try {
      switch (input.action) {
        case 'list':
          return await this.listSecrets();
        case 'get':
          return await this.getSecret(input.key);
        case 'set':
          return await this.setSecret(input.key, input.value);
        case 'delete':
          return await this.deleteSecret(input.key);
        default:
          return '❌ Invalid action. Use: list, get, set, or delete';
      }
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  /**
   * List all secret keys (without values)
   */
  private async listSecrets(): Promise<string> {
    const secrets = await this.client.get<{ keys: string[] }>('/api/secrets');

    if (!secrets.keys || secrets.keys.length === 0) {
      return '✅ No secrets stored yet.\n\n💡 Use action: set to add secrets.';
    }

    let output = '✅ Stored Secret Keys:\n\n';
    for (const key of secrets.keys) {
      output += `  🔐 ${key}\n`;
    }

    output += '\n💡 Use action: get with a key to retrieve the decrypted value.';

    return output;
  }

  /**
   * Get a specific secret (decrypted)
   */
  private async getSecret(key?: string): Promise<string> {
    if (!key) {
      return '❌ Error: key parameter is required for get action';
    }

    const response = await this.client.get<{ key: string; value: string }>(`/api/secrets/${key}`);

    return `✅ Secret Retrieved:\n\n🔐 Key: ${response.key}\n🔓 Value: ${response.value}\n\n⚠️  Keep this secret safe!`;
  }

  /**
   * Set a secret (encrypted)
   */
  private async setSecret(key?: string, value?: string): Promise<string> {
    if (!key) {
      return '❌ Error: key parameter is required for set action';
    }

    if (!value) {
      return '❌ Error: value parameter is required for set action';
    }

    await this.client.put(`/api/secrets/${key}`, { value });

    return `✅ Secret Stored Successfully:\n\n🔐 Key: ${key}\n🔒 Value: [ENCRYPTED]\n\n💡 The secret is now encrypted in Ansible Vault.`;
  }

  /**
   * Delete a secret
   */
  private async deleteSecret(key?: string): Promise<string> {
    if (!key) {
      return '❌ Error: key parameter is required for delete action';
    }

    await this.client.delete(`/api/secrets/${key}`);

    return `✅ Secret Deleted:\n\n🔐 Key: ${key}\n\n💡 The secret has been removed from the vault.`;
  }
}
