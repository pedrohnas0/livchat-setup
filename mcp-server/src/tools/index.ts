/**
 * Tool Registry - Central export for all 13 MCP tools (config.yaml REMOVED in v0.2.5)
 */

// Export all tool classes
export { ManageSecretsTool, ManageSecretsInputSchema } from './manage-secrets.js';
export { GetProviderInfoTool, GetProviderInfoInputSchema } from './providers.js';
export {
  CreateServerTool,
  CreateServerInputSchema,
  ListServersTool,
  ListServersInputSchema,
  UpdateServerDNSTool,  // v0.2.0: replaces ConfigureServerDNSTool
  UpdateServerDNSInputSchema,
  SetupServerTool,
  SetupServerInputSchema,
  DeleteServerTool,
  DeleteServerInputSchema,
} from './servers.js';
export {
  ListAppsTool,
  ListAppsInputSchema,
  DeployAppTool,
  DeployAppInputSchema,
  UndeployAppTool,
  UndeployAppInputSchema,
  ListDeployedAppsTool,
  ListDeployedAppsInputSchema,
} from './apps.js';
export {
  GetJobStatusTool,
  GetJobStatusInputSchema,
  ListJobsTool,
  ListJobsInputSchema,
} from './jobs.js';

// Export type definitions
export type { ManageSecretsInput } from './manage-secrets.js';
export type { GetProviderInfoInput } from './providers.js';
export type {
  CreateServerInput,
  ListServersInput,
  UpdateServerDNSInput,  // v0.2.0: replaces ConfigureServerDNSInput
  SetupServerInput,
  DeleteServerInput,
} from './servers.js';
export type {
  ListAppsInput,
  DeployAppInput,
  UndeployAppInput,
  ListDeployedAppsInput,
} from './apps.js';
export type {
  GetJobStatusInput,
  ListJobsInput,
} from './jobs.js';
