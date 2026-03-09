# mcptools

**mitmproxy for MCP** — intercept, inspect, debug, and replay MCP server traffic.

MCP (Model Context Protocol) powers tool use in Claude Code, Cursor, Windsurf, and VS Code Copilot. When things break — tools not appearing, slow responses, cryptic errors — debugging is painful. `mcptools` fixes that.

## Quick Start

```bash
pip install mcptools

# Diagnose your MCP server setup
mcptools doctor

# Inspect any MCP server directly
mcptools inspect uvx mcp-server-github

# Intercept traffic with a live TUI dashboard
mcptools proxy --config ~/.claude/claude_desktop_config.json

# Record a session for debugging
mcptools record -o debug-session.json

# Replay it later
mcptools replay debug-session.json
```

## Features

### `mcptools doctor` — Diagnose Config Issues

Validates your MCP configuration and checks server connectivity:

```
$ mcptools doctor
Config: ~/.claude/claude_desktop_config.json

  Checking filesystem... ✓ 3 tools
  Checking github... ✗ Connection timeout (10s)
    → Check if GITHUB_TOKEN is set
  Checking brave-search... ⚠ 1 tool — Slow response (2340ms)

Summary: 1 healthy, 1 warning, 1 error
```

Auto-detects configs from Claude Desktop, Cursor, VS Code, and Windsurf.

### `mcptools inspect` — Server Introspection

Connect to any MCP server and list its capabilities:

```
$ mcptools inspect uvx mcp-server-filesystem /tmp

┌─────────────────────────┐
│     MCP Server          │
│  filesystem-server v1.0 │
└─────────────────────────┘

Tools (3)
┌──────────────┬──────────────────────────┬────────────────────┐
│ Name         │ Description              │ Parameters         │
├──────────────┼──────────────────────────┼────────────────────┤
│ read_file    │ Read a file from disk    │ path: string*      │
│ write_file   │ Write content to a file  │ path: string*, ... │
│ list_dir     │ List directory contents  │ path: string*      │
└──────────────┴──────────────────────────┴────────────────────┘
```

### `mcptools proxy` — Traffic Interception

Sits between your IDE and MCP server, capturing all traffic with a real-time TUI:

```
IDE (Claude Code / Cursor)
    ↓ stdio
mcptools proxy (intercepts + displays)
    ↓ stdio
MCP Server
```

Features:
- Live message log with request/response pairs
- Latency tracking per call
- Error highlighting
- Stats panel (total messages, errors, avg latency)

### `mcptools record` / `mcptools replay` — Session Capture

Record MCP traffic to JSON for offline debugging:

```bash
# Record
mcptools record --config ~/.claude/claude_desktop_config.json -o session.json

# Replay with timing
mcptools replay session.json

# Replay at 2x speed, filtered to tool calls
mcptools replay session.json --speed 2 --filter "tools/*"
```

## Configuration

`mcptools` auto-detects MCP config files from these locations:

| IDE | Config Path |
|-----|-------------|
| Claude Desktop | `~/.claude/claude_desktop_config.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `~/.vscode/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

Or specify explicitly: `mcptools doctor --config /path/to/config.json`

## Development

```bash
git clone https://github.com/jannikc/mcptools.git
cd mcptools
pip install -e ".[dev]"
pytest
```

## License

MIT
