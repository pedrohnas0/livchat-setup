# Changelog

## 0.1.5

- Added `livchat-setup serve` command for easy API server startup
- Updated MCP error messages to suggest the new `serve` command instead of raw uvicorn
- Support for `--reload` flag in serve command for development mode
- Support for custom `--host` and `--port` options in serve command
- Fixed module import path in serve command (src.api.server)

