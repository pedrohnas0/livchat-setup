# @livchat/setup-mcp

MCP Server for LivChatSetup - Infrastructure orchestration via AI using Claude.

## Overview

This MCP (Model Context Protocol) server provides 14 tools for managing infrastructure:
- Configuration & Secrets management
- Cloud provider info (Hetzner)
- Server lifecycle (create, setup, delete)
- DNS configuration
- Application deployment
- Job status tracking

## Installation

```bash
npm install @livchat/setup-mcp
```

## Usage

### With Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "livchat-setup": {
      "command": "npx",
      "args": ["@livchat/setup-mcp"],
      "env": {
        "LIVCHAT_API_URL": "http://localhost:8000",
        "LIVCHAT_API_KEY": "your-api-key-optional"
      }
    }
  }
}
```

### Environment Variables

- `LIVCHAT_API_URL` (required): LivChatSetup API URL (default: `http://localhost:8000`)
- `LIVCHAT_API_KEY` (optional): API key for authentication

## Tools

### Configuration & Secrets
- `manage-config` - Manage non-sensitive configuration (YAML)
- `manage-secrets` - Manage encrypted credentials (Ansible Vault)

### Providers
- `get-provider-info` - Get cloud provider information

### Servers
- `create-server` - Create new VPS server (async)
- `list-servers` - List managed servers
- `configure-server-dns` - Configure DNS for server
- `setup-server` - Setup server infrastructure (async)
- `delete-server` - Delete server (async)

### Applications
- `list-apps` - List available applications
- `deploy-app` - Deploy application (async)
- `undeploy-app` - Remove application (async)
- `list-deployed-apps` - List deployed applications

### Jobs
- `get-job-status` - Check async job status
- `list-jobs` - List jobs with filters

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Run tests
npm test

# Watch mode
npm run dev
```

## License

MIT
