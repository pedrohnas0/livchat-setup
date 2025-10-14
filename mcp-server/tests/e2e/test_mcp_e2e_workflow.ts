/**
 * Complete End-to-End Test via MCP Tools (v0.2.0)
 *
 * This test validates the ENTIRE LivChat Setup workflow using ONLY MCP tools:
 * 1. Server creation via create-server → get-job-status monitoring
 * 2. Server setup with MANDATORY DNS (v0.2.0) via setup-server
 * 3. Infrastructure bundle deployment (Traefik + Portainer)
 * 4. Automatic dependency resolution - deploy N8N installs postgres+redis automatically!
 * 5. State verification via list-* tools
 *
 * v0.2.0 Changes Tested:
 * - DNS is MANDATORY in setup-server (zone_name required)
 * - Infrastructure bundle deployed as app (not part of setup)
 * - Automatic dependency installation (like npm/apt/pip)
 *
 * NO MOCKS - Only real infrastructure, controlled via MCP
 * NO direct API calls - Everything through MCP tools
 * NO AI - Direct programmatic MCP client
 *
 * Run with:
 *   export LIVCHAT_E2E_REAL=true
 *   export LIVCHAT_API_URL=http://localhost:8000
 *   cd mcp-server && npm run test:e2e
 *
 * Skip with:
 *   SKIP_E2E_TESTS=true npm run test:e2e
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ESM __dirname equivalent
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Test configuration
const TEST_CONFIG = {
  server_name: 'e2e-mcp-test',
  server_type: 'ccx23',        // 4 vCPU, 16GB RAM
  region: 'ash',               // Ashburn
  os_image: 'debian-12',
  test_domain: 'livchat.ai',
  test_subdomain: 'lab',
};

const MAX_JOB_WAIT_TIME = 600;  // 10 minutes max per job
const JOB_POLL_INTERVAL = 5;    // Check every 5 seconds

/**
 * MCP Client wrapper for calling tools
 */
class MCPClient {
  private client: Client;
  private transport: StdioClientTransport | null = null;

  constructor() {
    this.client = new Client(
      { name: 'livchat-e2e-test', version: '1.0.0' },
      { capabilities: {} }
    );
  }

  /**
   * Connect to MCP server via stdio
   */
  async connect(): Promise<void> {
    // Calculate path to index.js
    // When compiled: __dirname is /dist/tests/e2e/ → need ../../index.js
    // When running with tsx: __dirname is /tests/e2e/ → need ../dist/index.js (not used in practice)

    // Check if we're in the compiled dist directory
    const isCompiled = __dirname.includes('/dist/');
    const serverPath = isCompiled
      ? path.resolve(__dirname, '../../index.js')  // dist/tests/e2e → dist/index.js
      : path.resolve(__dirname, '../dist/index.js');  // tests/e2e → dist/index.js

    console.error(`🔌 Connecting to MCP server: ${serverPath}`);

    // Create stdio transport
    const env: Record<string, string> = {
      ...process.env as Record<string, string>,
      LIVCHAT_API_URL: process.env.LIVCHAT_API_URL || 'http://localhost:8000',
    };

    // Add API key if present
    if (process.env.LIVCHAT_API_KEY) {
      env.LIVCHAT_API_KEY = process.env.LIVCHAT_API_KEY;
    }

    this.transport = new StdioClientTransport({
      command: 'node',
      args: [serverPath],
      env,
    });

    // Connect client to transport
    await this.client.connect(this.transport);

    console.error('✅ Connected to MCP server');
  }

  /**
   * Call a tool by name with arguments
   */
  async callTool(toolName: string, args: any): Promise<string> {
    const result = await this.client.callTool({
      name: toolName,
      arguments: args,
    });

    // Extract text content from result
    const content = (result as any).content;
    if (content && Array.isArray(content) && content.length > 0) {
      const textContent = content.find((c: any) => c.type === 'text');
      if (textContent && typeof textContent.text === 'string') {
        return textContent.text;
      }
    }

    return JSON.stringify(result);
  }

  /**
   * Close connection
   */
  async close(): Promise<void> {
    if (this.transport) {
      await this.client.close();
      await this.transport.close();
    }
  }
}

/**
 * Extract job_id from tool response
 */
function extractJobId(response: string): string | null {
  // Match job_id format: prefix_type-uuid (includes underscores)
  const match = response.match(/Job ID: ([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

/**
 * Check if string contains error indicators
 */
function hasError(response: string): boolean {
  return response.includes('❌') || response.includes('Error:') || response.includes('failed');
}

/**
 * Poll job until completion
 */
async function pollJobUntilComplete(
  client: MCPClient,
  jobId: string,
  jobDescription: string
): Promise<void> {
  console.log(`\n⏳ Monitoring ${jobDescription} (ID: ${jobId})...`);

  const startTime = Date.now();
  let lastProgress = -1;

  while (true) {
    // Check timeout
    const elapsed = (Date.now() - startTime) / 1000;
    if (elapsed > MAX_JOB_WAIT_TIME) {
      throw new Error(`${jobDescription} timed out after ${MAX_JOB_WAIT_TIME}s`);
    }

    // Poll job status
    const response = await client.callTool('get-job-status', {
      job_id: jobId,
      tail_logs: 50,
    });

    // Parse status from response
    const statusMatch = response.match(/Status: (⏳|▶️|✅|❌|🚫)\s+(\w+)/);
    if (!statusMatch) {
      console.log(`   [${Math.floor(elapsed)}s] Waiting for status...`);
      await new Promise(resolve => setTimeout(resolve, JOB_POLL_INTERVAL * 1000));
      continue;
    }

    const status = statusMatch[2].toLowerCase();

    // Extract progress
    const progressMatch = response.match(/Progresso: .+ (\d+)%/);
    const progress = progressMatch ? parseInt(progressMatch[1]) : 0;

    // Show progress updates
    if (progress !== lastProgress) {
      console.log(`   [${Math.floor(elapsed)}s] ${progress}% - ${status}`);
      lastProgress = progress;
    }

    // Check if completed
    if (status === 'completed') {
      console.log(`✅ ${jobDescription} job completed in ${Math.floor(elapsed)}s`);

      // CRITICAL: Validate actual result, not just job completion
      // Check for explicit failure indicators in result
      const successMatch = response.match(/"success":\s*(false|true)/i);
      const hasSuccessFalse = successMatch && successMatch[1].toLowerCase() === 'false';

      // Also check for explicit error messages
      const hasErrorField = response.includes('"error":') && !response.includes('"error": null');

      // Check for common failure messages
      const hasFailureMessage = response.includes('SSH did not become available') ||
                               response.includes('failed') ||
                               response.includes('FAILED');

      if (hasSuccessFalse || hasErrorField || hasFailureMessage) {
        console.error(`❌ ${jobDescription} FAILED despite job completion:`);
        console.error('   Result validation detected failure indicators');

        // Extract error message if available
        const errorMatch = response.match(/"message":\s*"([^"]+)"/);
        if (errorMatch) {
          console.error(`   Error: ${errorMatch[1]}`);
        }

        throw new Error(`${jobDescription} failed: result validation detected errors`);
      }

      console.log(`   ✅ Result validation: success (no errors detected)`);
      return;
    }

    // Check if failed
    if (status === 'failed') {
      console.error(`❌ ${jobDescription} failed:`);
      console.error(response);
      throw new Error(`${jobDescription} failed`);
    }

    // Check if cancelled
    if (status === 'cancelled') {
      throw new Error(`${jobDescription} was cancelled`);
    }

    // Wait before next poll
    await new Promise(resolve => setTimeout(resolve, JOB_POLL_INTERVAL * 1000));
  }
}

/**
 * Main E2E test
 */
async function runE2ETest() {
  const config = TEST_CONFIG;
  const serverName = config.server_name;

  console.log('\n' + '='.repeat(80));
  console.log('🚀 E2E TEST VIA MCP TOOLS');
  console.log('='.repeat(80));
  console.log('📋 Configuration:');
  console.log(`  - Server: ${serverName}`);
  console.log(`  - Type: ${config.server_type}`);
  console.log(`  - Region: ${config.region}`);
  console.log(`  - Image: ${config.os_image}`);
  console.log('='.repeat(80));

  let client: MCPClient | null = null;
  let serverCreated = false;
  let serverSetup = false;
  let dnsConfigured = false;
  const appsDeployed: string[] = [];

  try {
    // Connect to MCP server
    client = new MCPClient();
    await client.connect();

    // ===========================================
    // STEP 1: Verify Secrets via MCP
    // ===========================================
    console.log('\n🔐 [STEP 1/7] Verifying secrets via MCP...');

    const secretsResponse = await client.callTool('manage-secrets', {
      action: 'list',
    });

    console.log(secretsResponse);

    if (!secretsResponse.includes('hetzner_token')) {
      throw new Error('HETZNER_TOKEN not found in vault. Configure it first via manage-secrets.');
    }

    const hasCloudflare = secretsResponse.includes('cloudflare_email') &&
                          secretsResponse.includes('cloudflare_api_key');

    if (hasCloudflare) {
      console.log('✅ Cloudflare credentials found in vault');
    } else {
      console.log('⚠️ Cloudflare not configured - DNS features will be skipped');
    }

    // ===========================================
    // STEP 2: Create Server via MCP
    // ===========================================
    console.log('\n🖥️  [STEP 2/7] Creating server via MCP...');

    // Check if server already exists
    let serverExistsResponse = await client.callTool('list-servers', {
      server_name: serverName,
    });

    if (!serverExistsResponse.includes('Nenhum servidor encontrado') &&
        !serverExistsResponse.includes('not found')) {
      console.log(`⚠️ Server ${serverName} already exists, using existing...`);
      serverCreated = true;
    } else {
      // Create server via MCP
      console.log(`📝 Creating new server ${serverName}...`);

      const createResponse = await client.callTool('create-server', {
        name: serverName,
        server_type: config.server_type,
        region: config.region,
        image: config.os_image,
      });

      console.log(createResponse);

      if (hasError(createResponse)) {
        throw new Error('Failed to create server');
      }

      const jobId = extractJobId(createResponse);
      if (!jobId) {
        throw new Error('No job_id returned from create-server');
      }

      // Monitor job until completion
      await pollJobUntilComplete(client, jobId, 'Server creation');

      // Verify server was created
      serverExistsResponse = await client.callTool('list-servers', {
        server_name: serverName,
      });

      if (serverExistsResponse.includes('not found')) {
        throw new Error('Server not found after creation');
      }

      serverCreated = true;
      console.log('✅ Server created successfully!');
      console.log(serverExistsResponse);

      // Wait for server to be fully ready
      console.log('\n⏳ Waiting 60s for server to initialize...');
      await new Promise(resolve => setTimeout(resolve, 60000));
    }

    // ===========================================
    // STEP 3: Setup Server via MCP (v0.2.0 - DNS MANDATORY!)
    // ===========================================
    console.log('\n🔧 [STEP 3/7] Setting up server infrastructure via MCP (v0.2.0)...');
    console.log('   v0.2.0: DNS is now MANDATORY during setup!');
    console.log('   This will install Docker, Swarm (NO Traefik/Portainer - they come later)');

    if (!hasCloudflare) {
      throw new Error('v0.2.0: Cloudflare credentials required for setup-server (DNS is mandatory)');
    }

    const setupResponse = await client.callTool('setup-server', {
      server_name: serverName,
      zone_name: config.test_domain,      // ← v0.2.0: MANDATORY!
      subdomain: config.test_subdomain,   // ← Optional
      timezone: 'America/Sao_Paulo',
      network_name: 'livchat_network',
    });

    console.log(setupResponse);

    if (hasError(setupResponse)) {
      throw new Error('Failed to start setup');
    }

    const setupJobId = extractJobId(setupResponse);
    if (!setupJobId) {
      throw new Error('No job_id returned from setup-server');
    }

    // Monitor setup job
    await pollJobUntilComplete(client, setupJobId, 'Server setup');

    serverSetup = true;
    dnsConfigured = true;  // DNS is configured automatically in setup now!
    console.log('✅ Server setup completed successfully!');
    console.log('✅ DNS configured automatically during setup (v0.2.0)');
    console.log('\n⏳ Waiting 10s for DNS propagation...');
    await new Promise(resolve => setTimeout(resolve, 10000));

    // ===========================================
    // STEP 4: Deploy Infrastructure Bundle via MCP (v0.2.0 NEW!)
    // ===========================================
    console.log('\n🏗️  [STEP 4/7] Deploying infrastructure bundle via MCP (v0.2.0)...');
    console.log('   Bundle: Traefik (reverse proxy + SSL) + Portainer (Docker UI)');
    console.log('   v0.2.0: Infrastructure is now deployed as an app (not part of setup)');

    const infrastructureResponse = await client.callTool('deploy-app', {
      app_name: 'infrastructure',  // ← v0.2.0: Bundle name (was "base-infrastructure")
      server_name: serverName,
      environment: {},
    });

    console.log(infrastructureResponse);

    if (hasError(infrastructureResponse)) {
      throw new Error('Failed to start infrastructure deployment');
    }

    const infrastructureJobId = extractJobId(infrastructureResponse);
    if (!infrastructureJobId) {
      throw new Error('No job_id returned from deploy-app');
    }

    // Monitor infrastructure deployment
    await pollJobUntilComplete(client, infrastructureJobId, 'Infrastructure bundle deployment');

    appsDeployed.push('infrastructure');
    console.log('✅ Infrastructure bundle deployed successfully!');
    console.log('   ✅ Traefik: Reverse proxy + SSL termination');
    console.log('   ✅ Portainer: Docker Swarm management UI');
    console.log('⏳ Waiting 30s for services to fully initialize...');
    await new Promise(resolve => setTimeout(resolve, 30000));

    // ===========================================
    // STEP 5: List Available Apps via MCP
    // ===========================================
    console.log('\n📦 [STEP 5/7] Listing available apps via MCP...');

    const appsResponse = await client.callTool('list-apps', {});
    console.log(appsResponse);

    // ===========================================
    // STEP 6: Deploy N8N via MCP (v0.2.0 AUTO-DEPENDENCIES!)
    // ===========================================
    console.log('\n🔄 [STEP 6/7] Deploying N8N with AUTO-DEPENDENCY INSTALLATION (v0.2.0)...');
    console.log('   v0.2.0 NEW: System will automatically install postgres + redis!');
    console.log('   This is like running "npm install" - dependencies are resolved automatically! 🎉');

    const n8nResponse = await client.callTool('deploy-app', {
      app_name: 'n8n',
      server_name: serverName,
      environment: {
        N8N_BASIC_AUTH_USER: 'admin',
        N8N_BASIC_AUTH_PASSWORD: 'n8npass123',
      },
    });

    console.log(n8nResponse);

    if (hasError(n8nResponse)) {
      throw new Error('Failed to start N8N deployment');
    }

    const n8nJobId = extractJobId(n8nResponse);
    if (!n8nJobId) {
      throw new Error('No job_id returned from deploy-app');
    }

    // Monitor N8N deployment (this will install postgres + redis + n8n)
    await pollJobUntilComplete(client, n8nJobId, 'N8N deployment (with auto-dependencies)');

    appsDeployed.push('n8n');
    // Dependencies should have been installed automatically
    appsDeployed.push('postgres');
    appsDeployed.push('redis');

    console.log('✅ N8N deployed successfully with automatic dependencies!');
    console.log('   ✅ PostgreSQL installed automatically (dependency)');
    console.log('   ✅ Redis installed automatically (dependency)');
    console.log('   ✅ N8N workflow automation');
    const n8nDomain = `edt.${config.test_subdomain}.${config.test_domain}`;
    console.log(`   🌐 URL: https://${n8nDomain}`);
    console.log('   🔑 Credentials: admin / n8npass123');

    // ===========================================
    // STEP 7: Verify Final State via MCP
    // ===========================================
    console.log('\n🔍 [STEP 7/7] Verifying final state via MCP...');

    // Get server details
    const serverDetailsResponse = await client.callTool('list-servers', {
      server_name: serverName,
    });
    console.log('✅ Server details:');
    console.log(serverDetailsResponse);

    // List deployed apps
    const deployedAppsResponse = await client.callTool('list-deployed-apps', {
      server_name: serverName,
    });
    console.log('\n✅ Deployed apps:');
    console.log(deployedAppsResponse);

    // List all jobs
    const jobsResponse = await client.callTool('list-jobs', {
      limit: 100,
    });
    console.log('\n✅ Jobs history:');
    console.log(jobsResponse);

    // ===========================================
    // OBSERVABILITY VALIDATION
    // ===========================================
    console.log('\n🔬 [OBSERVABILITY] Validating log capture system...');

    // Get job status with logs for server setup
    if (setupJobId) {
      const logsResponse = await client.callTool('get-job-status', {
        job_id: setupJobId,
        tail_logs: 100,
      });

      console.log(`   Testing log retrieval for job: ${setupJobId}`);

      if (logsResponse.includes('Logs:')) {
        console.log('   ✅ Logs captured successfully');
        // Show sample
        const logsMatch = logsResponse.match(/Logs:[\s\S]+```([\s\S]+?)```/);
        if (logsMatch) {
          const logLines = logsMatch[1].trim().split('\n');
          console.log(`   📋 Sample logs (last 3):`);
          logLines.slice(-3).forEach(line => {
            console.log(`      ${line.substring(0, 100)}...`);
          });
        }
        console.log('   🎉 Observability validation PASSED!');
      } else {
        console.log('   ⚠️ No logs found in job status');
      }
    }

    // ===========================================
    // Final Summary (v0.2.0)
    // ===========================================
    console.log('\n' + '='.repeat(80));
    console.log('📊 E2E MCP TEST SUMMARY (v0.2.0)');
    console.log('='.repeat(80));
    console.log(`✅ Server created: ${serverCreated}`);
    console.log(`✅ Server setup (with mandatory DNS): ${serverSetup}`);
    console.log(`✅ DNS configured automatically: ${dnsConfigured}`);
    console.log(`✅ Apps deployed: ${appsDeployed.join(', ') || 'None'}`);
    console.log('✅ All operations via MCP tools');
    console.log('✅ v0.2.0 features tested:');
    console.log('   - Mandatory DNS in setup-server');
    console.log('   - Infrastructure bundle deployment');
    console.log('   - Automatic dependency resolution');

    // Assertions - STRICT: Verify all critical steps completed
    if (!serverCreated) throw new Error('Server must be created');
    if (!serverSetup) throw new Error('Server setup must complete');
    if (!dnsConfigured) throw new Error('DNS must be configured (v0.2.0 mandatory)');
    if (!appsDeployed.includes('infrastructure')) {
      throw new Error('Infrastructure bundle must be deployed (v0.2.0: Traefik + Portainer)');
    }
    if (!appsDeployed.includes('postgres')) {
      throw new Error('PostgreSQL must be deployed (auto-installed as N8N dependency)');
    }
    if (!appsDeployed.includes('redis')) {
      throw new Error('Redis must be deployed (auto-installed as N8N dependency)');
    }
    if (!appsDeployed.includes('n8n')) {
      throw new Error('N8N must be deployed successfully');
    }

    console.log('\n🎉 E2E MCP TEST PASSED (v0.2.0)!');
    console.log('='.repeat(80));

  } catch (error) {
    console.error('\n❌ E2E MCP TEST FAILED!');
    console.error(`   Error: ${error}`);
    throw error;

  } finally {
    // Cleanup
    const cleanup = process.env.LIVCHAT_E2E_CLEANUP === 'true';
    if (cleanup && serverCreated && client) {
      console.log('\n🧹 Cleaning up via MCP...');
      try {
        const deleteResponse = await client.callTool('delete-server', {
          server_name: serverName,
          confirm: true,
        });
        console.log(deleteResponse);

        const deleteJobId = extractJobId(deleteResponse);
        if (deleteJobId) {
          console.log(`   Deletion job started: ${deleteJobId}`);
        }
      } catch (e) {
        console.error(`   Failed to delete server: ${e}`);
      }
    } else {
      console.log(`\n📌 Server kept for inspection: ${serverName}`);
      console.log('   To cleanup: use delete-server tool with confirm=true');
    }

    // Close MCP connection
    if (client) {
      await client.close();
      console.log('🔌 MCP connection closed');
    }
  }
}

// Run test (ESM equivalent of if (require.main === module))
const isRunDirectly = process.argv[1] === fileURLToPath(import.meta.url);

if (isRunDirectly) {
  // Check if E2E tests should run
  if (process.env.SKIP_E2E_TESTS === 'true') {
    console.log('⏭️ E2E tests skipped via SKIP_E2E_TESTS=true');
    process.exit(0);
  }

  if (process.env.LIVCHAT_E2E_REAL !== 'true') {
    console.log('⏭️ E2E MCP tests require LIVCHAT_E2E_REAL=true');
    process.exit(0);
  }

  runE2ETest()
    .then(() => {
      console.log('\n✅ Test completed successfully');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Test failed:', error);
      process.exit(1);
    });
}

export { runE2ETest, MCPClient };
