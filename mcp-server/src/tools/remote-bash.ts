/**
 * Tool: remote-bash
 *
 * Execute SSH commands on remote servers with security validation
 * Lightweight async alternative to Ansible for quick diagnostics
 */

import { z } from 'zod';
import { APIClient } from '../api-client.js';
import { ErrorHandler } from '../error-handler.js';

/**
 * Input schema for remote-bash tool
 */
export const RemoteBashInputSchema = z.object({
  server_name: z.string().describe('Name of the server to execute command on'),
  command: z.string().min(1).describe('Shell command to execute (e.g., "docker ps", "tail -n 100 /var/log/app.log")'),
  timeout: z.number().int().min(1).max(300).optional().default(30).describe('Command timeout in seconds (default: 30, max: 300)'),
  working_dir: z.string().optional().describe('Optional working directory to execute command in (e.g., "/var/log")'),
  use_job: z.boolean().optional().default(false).describe('Execute via job system for long-running commands (allows monitoring via get-job-status)'),
});

export type RemoteBashInput = z.infer<typeof RemoteBashInputSchema>;

/**
 * Tool handler for remote-bash
 */
export class RemoteBashTool {
  constructor(private client: APIClient) {}

  /**
   * Execute the remote-bash tool
   */
  async execute(input: RemoteBashInput): Promise<string> {
    try {
      return await this.executeCommand(input);
    } catch (error) {
      return ErrorHandler.formatForMCP(error);
    }
  }

  /**
   * Execute remote SSH command
   */
  private async executeCommand(input: RemoteBashInput): Promise<string> {
    // Build request payload
    const payload: any = {
      command: input.command,
      timeout: input.timeout || 30,
      use_job: input.use_job || false,
    };

    if (input.working_dir) {
      payload.working_dir = input.working_dir;
    }

    // Call API endpoint
    const response = await this.client.post<any>(
      `/api/servers/${input.server_name}/exec`,
      payload
    );

    // Check if response is a job (async execution)
    if (response.job_id) {
      return this.formatJobResponse(response, input.server_name);
    }

    // Format sync execution result
    return this.formatCommandResult(response);
  }

  /**
   * Format command execution result for AI consumption
   */
  private formatCommandResult(result: any): string {
    const success = result.success;
    const exitCode = result.exit_code;
    const stdout = result.stdout || '';
    const stderr = result.stderr || '';
    const serverName = result.server_name;
    const command = result.command;
    const workingDir = result.working_dir;

    let output = '';

    // Header with status
    if (success) {
      output += `✅ Command Executed Successfully\n\n`;
    } else {
      output += `❌ Command Failed (Exit Code: ${exitCode})\n\n`;
    }

    // Command details
    output += `🖥️  Server: ${serverName}\n`;
    output += `💻 Command: ${command}\n`;

    if (workingDir) {
      output += `📁 Working Directory: ${workingDir}\n`;
    }

    output += `⏱️  Timeout: ${result.timeout_seconds}s\n`;
    output += `🚪 Exit Code: ${exitCode}\n\n`;

    // Standard output
    if (stdout && stdout.trim()) {
      output += `📤 STDOUT:\n\`\`\`\n${stdout}\n\`\`\`\n\n`;
    } else {
      output += `📤 STDOUT: (empty)\n\n`;
    }

    // Standard error
    if (stderr && stderr.trim()) {
      output += `⚠️  STDERR:\n\`\`\`\n${stderr}\n\`\`\`\n\n`;
    }

    // Truncation warning
    if (stdout.includes('[OUTPUT TRUNCATED') || stderr.includes('[OUTPUT TRUNCATED')) {
      output += `⚠️  Output was truncated (exceeds 10KB limit). Consider using filters or limiting output.\n\n`;
    }

    // Security note for failed commands
    if (!success && stderr.includes('security') || stderr.includes('rejected')) {
      output += `🔒 Security Note: This command may have been rejected by security policy.\n`;
      output += `   Dangerous patterns blocked: rm -rf /, dd, mkfs, fork bombs, pipe to shell.\n\n`;
    }

    // Usage tips
    if (success) {
      output += `💡 Tips:\n`;
      output += `   - Use grep/awk to filter large outputs\n`;
      output += `   - Set timeout for long-running commands (max 300s)\n`;
      output += `   - Use working_dir to execute in specific directories\n`;
    } else {
      output += `💡 Troubleshooting:\n`;
      output += `   - Check if command exists: which <command>\n`;
      output += `   - Verify permissions: ls -la <file>\n`;
      output += `   - Review logs: journalctl -xe\n`;
    }

    return output;
  }

  /**
   * Format job response for async execution
   */
  private formatJobResponse(response: any, serverName: string): string {
    let output = '✅ Command execution started via job system (async)\n\n';
    output += `🆔 Job ID: ${response.job_id}\n`;
    output += `📦 Server: ${serverName}\n`;
    output += `📝 Command: ${response.command || 'N/A'}\n\n`;
    output += '⏱️  The command is running in the background.\n';
    output += '💡 Use get-job-status to monitor progress:\n';
    output += `   get-job-status(job_id="${response.job_id}", tail_logs=50)\n\n`;
    output += '📊 When complete, the job result will contain:\n';
    output += '   - stdout: Command output\n';
    output += '   - stderr: Error output\n';
    output += '   - exit_code: Exit status\n';

    return output;
  }
}
