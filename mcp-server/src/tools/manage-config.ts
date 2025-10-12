/**
 * Tool: manage-config
 *
 * Manages non-sensitive YAML configuration for LivChatSetup
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

/**
 * Input schema for manage-config tool
 */
export const ManageConfigInputSchema = z.object({
  action: z.enum(['get', 'set', 'list']).describe('Action to perform: get, set, or list config keys'),
  key: z.string().optional().describe('Configuration key (e.g., "general.default_provider")'),
  value: z.any().optional().describe('Configuration value (for set action)'),
});

export type ManageConfigInput = z.infer<typeof ManageConfigInputSchema>;

/**
 * Tool handler for manage-config
 */
export class ManageConfigTool {
  constructor(private client: APIClient) {}

  /**
   * Execute the manage-config tool
   */
  async execute(input: ManageConfigInput): Promise<string> {
    try {
      switch (input.action) {
        case 'list':
          return await this.listConfig();
        case 'get':
          return await this.getConfig(input.key);
        case 'set':
          return await this.setConfig(input.key, input.value);
        default:
          return '❌ Invalid action. Use: get, set, or list';
      }
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  /**
   * List all configuration keys
   */
  private async listConfig(): Promise<string> {
    const config = await this.client.get<any>('/config');

    let output = '✅ Configuration Keys:\n\n';
    output += this.formatConfigTree(config);

    return output;
  }

  /**
   * Get a specific configuration value
   */
  private async getConfig(key?: string): Promise<string> {
    if (!key) {
      return '❌ Error: key parameter is required for get action';
    }

    const config = await this.client.get<any>('/config');
    const value = this.getNestedValue(config, key);

    if (value === undefined) {
      return `❌ Configuration key "${key}" not found\n\nUse action: list to see available keys`;
    }

    return `✅ Configuration Value:\n\nKey: ${key}\nValue: ${JSON.stringify(value, null, 2)}`;
  }

  /**
   * Set a configuration value
   */
  private async setConfig(key?: string, value?: any): Promise<string> {
    if (!key) {
      return '❌ Error: key parameter is required for set action';
    }

    if (value === undefined) {
      return '❌ Error: value parameter is required for set action';
    }

    await this.client.post('/config', { key, value });

    return `✅ Configuration Updated:\n\nKey: ${key}\nNew Value: ${JSON.stringify(value, null, 2)}`;
  }

  /**
   * Format configuration as a tree structure
   */
  private formatConfigTree(obj: any, prefix = ''): string {
    let output = '';

    for (const [key, value] of Object.entries(obj)) {
      const fullKey = prefix ? `${prefix}.${key}` : key;

      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        output += `${fullKey}/\n`;
        output += this.formatConfigTree(value, fullKey);
      } else {
        output += `  ${fullKey}: ${JSON.stringify(value)}\n`;
      }
    }

    return output;
  }

  /**
   * Get nested value from object using dot notation
   */
  private getNestedValue(obj: any, path: string): any {
    const keys = path.split('.');
    let current = obj;

    for (const key of keys) {
      if (current && typeof current === 'object' && key in current) {
        current = current[key];
      } else {
        return undefined;
      }
    }

    return current;
  }
}
