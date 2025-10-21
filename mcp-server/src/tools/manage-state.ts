/**
 * Tool: manage-state
 *
 * Generic state management with dot notation path access to state.json
 * Provides read/write access to any nested field without specific tools
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

/**
 * Input schema for manage-state tool
 */
export const ManageStateInputSchema = z.object({
  action: z.enum(['get', 'set', 'delete', 'list']).describe('Action: get, set, delete, or list keys'),
  path: z.string().optional().describe('Dot notation path (e.g., "servers.prod.ip", "settings.admin_email"). Empty or null returns entire state.'),
  value: z.any().optional().describe('Value to set (for set action) - can be any JSON type: string, number, object, array, boolean, null'),
});

export type ManageStateInput = z.infer<typeof ManageStateInputSchema>;

/**
 * Tool handler for manage-state
 */
export class ManageStateTool {
  constructor(private client: APIClient) {}

  /**
   * Execute the manage-state tool
   */
  async execute(input: ManageStateInput): Promise<string> {
    try {
      switch (input.action) {
        case 'get':
          return await this.getValue(input.path);
        case 'set':
          return await this.setValue(input.path, input.value);
        case 'delete':
          return await this.deleteKey(input.path);
        case 'list':
          return await this.listKeys(input.path);
        default:
          return '❌ Invalid action. Use: get, set, delete, or list';
      }
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  /**
   * Get value at path (or entire state if no path)
   */
  private async getValue(path?: string): Promise<string> {
    const endpoint = path ? `/api/state?path=${encodeURIComponent(path)}` : '/api/state';
    const response = await this.client.get<any>(endpoint);

    if (!response.success) {
      return `❌ Error: ${response.error || 'Failed to get state value'}`;
    }

    // Format output based on what was retrieved
    if (!path || path === '') {
      // Entire state
      const formattedState = JSON.stringify(response.value, null, 2);
      return `✅ Entire State:\n\n\`\`\`json\n${formattedState}\n\`\`\`\n\n💡 Use path parameter to access specific nested values.`;
    } else {
      // Specific path
      const value = response.value;
      const valueType = typeof value;
      const isObject = valueType === 'object' && value !== null;

      let formattedValue: string;
      if (isObject) {
        formattedValue = JSON.stringify(value, null, 2);
      } else {
        formattedValue = String(value);
      }

      let output = `✅ State Value Retrieved:\n\n`;
      output += `📍 Path: ${path}\n`;
      output += `📦 Type: ${Array.isArray(value) ? 'array' : valueType}\n`;

      if (isObject) {
        output += `\n\`\`\`json\n${formattedValue}\n\`\`\``;
      } else {
        output += `\n💎 Value: ${formattedValue}`;
      }

      return output;
    }
  }

  /**
   * Set value at path
   */
  private async setValue(path?: string, value?: any): Promise<string> {
    if (!path) {
      return '❌ Error: path parameter is required for set action';
    }

    if (value === undefined) {
      return '❌ Error: value parameter is required for set action';
    }

    const response = await this.client.put<any>('/api/state', { path, value });

    if (!response.success) {
      return `❌ Error: ${response.error || 'Failed to set state value'}`;
    }

    const valueType = typeof value;
    const isObject = valueType === 'object' && value !== null;

    let formattedValue: string;
    if (isObject) {
      formattedValue = JSON.stringify(value, null, 2);
    } else {
      formattedValue = String(value);
    }

    let output = `✅ State Value Set Successfully:\n\n`;
    output += `📍 Path: ${path}\n`;
    output += `📦 Type: ${Array.isArray(value) ? 'array' : valueType}\n`;

    if (isObject) {
      output += `\n\`\`\`json\n${formattedValue}\n\`\`\``;
    } else {
      output += `\n💎 Value: ${formattedValue}`;
    }

    output += `\n\n💾 State saved to state.json`;

    return output;
  }

  /**
   * Delete key at path
   */
  private async deleteKey(path?: string): Promise<string> {
    if (!path) {
      return '❌ Error: path parameter is required for delete action';
    }

    const endpoint = `/api/state?path=${encodeURIComponent(path)}`;
    const response = await this.client.delete<any>(endpoint);

    if (!response.success) {
      return `❌ Error: ${response.error || 'Failed to delete state key'}`;
    }

    return `✅ State Key Deleted:\n\n📍 Path: ${path}\n\n💾 State saved to state.json`;
  }

  /**
   * List keys at path
   */
  private async listKeys(path?: string): Promise<string> {
    const endpoint = path ? `/api/state/keys?path=${encodeURIComponent(path)}` : '/api/state/keys';
    const response = await this.client.get<any>(endpoint);

    if (!response.success) {
      return `❌ Error: ${response.error || 'Failed to list keys'}`;
    }

    const keys = response.keys || [];

    if (keys.length === 0) {
      const location = path ? `at path "${path}"` : 'in root state';
      return `✅ No keys found ${location}.\n\n💡 Use action: set to add values.`;
    }

    const location = path ? `at path "${path}"` : 'in root state';
    let output = `✅ Keys ${location}:\n\n`;

    for (const key of keys) {
      const fullPath = path ? `${path}.${key}` : key;
      output += `  📁 ${key}  →  ${fullPath}\n`;
    }

    output += `\n💡 Use action: get with a path to retrieve values.`;

    return output;
  }
}
