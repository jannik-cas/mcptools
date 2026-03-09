# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-09

### Added

- `mcptools call` — invoke any MCP tool directly from the terminal without an IDE
- `--json` flag for `doctor`, `inspect`, and `call` — machine-readable output for scripting

### Changed

- Refactored `inspect/server.py` to separate data fetching from rendering
- Updated README with new commands and scripting examples

## [0.1.0] - 2025-01-01

### Added

- `mcptools doctor` — diagnose MCP server configuration and connectivity issues
- `mcptools inspect` — connect to any MCP server and list tools, resources, and prompts
- `mcptools proxy` — transparent proxy with real-time TUI dashboard
- `mcptools record` — capture MCP sessions to JSON
- `mcptools replay` — replay recorded sessions with speed control and filtering
- Auto-detection of MCP configs from Claude Desktop, Cursor, VS Code, and Windsurf
- Concurrent health checks across multiple servers
- Per-call latency measurement
- Session recording with timestamps and payload capture
