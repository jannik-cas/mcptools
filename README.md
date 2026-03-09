<p align="center">
  <h1 align="center">mcptools</h1>
  <p align="center">
    <strong>mitmproxy for MCP</strong> — intercept, inspect, debug, and replay Model Context Protocol traffic
  </p>
  <p align="center">
    <a href="https://pypi.org/project/mcptools/"><img alt="PyPI" src="https://img.shields.io/pypi/v/mcptools?color=blue"></a>
    <a href="https://pypi.org/project/mcptools/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/mcptools"></a>
    <a href="https://github.com/jannik-cas/mcptools/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/jannik-cas/mcptools"></a>
  </p>
</p>

---

Every developer using **Claude Code**, **Cursor**, **Windsurf**, or **VS Code Copilot** relies on MCP servers for tool use. But when things break — tools not showing up, mysterious timeouts, config typos — there's no easy way to see what's going on under the hood.

**mcptools** is the missing DevTools for MCP. One `pip install` and you can inspect any server, diagnose config issues, intercept live traffic, and record sessions for replay.

## The Problem

```
You: "Why isn't my MCP tool showing up?"
You: *restarts IDE*
You: *re-reads config for the 5th time*
You: *adds random print statements to server code*
You: *gives up and rewrites the config from scratch*
```

Sound familiar? MCP has no built-in observability. You're flying blind.

## The Fix

```bash
pip install mcptools
mcptools doctor --config ~/.claude/claude_desktop_config.json
```

```
Config: ~/.claude/claude_desktop_config.json

  Checking fetch...          ✓ 1 tool, 1 prompt
  Checking time...           ✓ 2 tools
  Checking broken-server...  ✗ Command not found: nonexistent-mcp-server-xyz
    → Ensure 'nonexistent-mcp-server-xyz' is installed and in your PATH

Summary: 2 healthy, 1 error
```

Found the issue in 2 seconds.

## Features

### `mcptools doctor` — Instant Config Diagnosis

Reads your IDE's MCP config, spins up each server, checks connectivity, and reports what's healthy and what's broken — all in one command.

```bash
mcptools doctor                                          # auto-detects config
mcptools doctor --config ~/.cursor/mcp.json              # explicit config
mcptools doctor --server github --server filesystem      # check specific servers
```

Auto-detects configs from:

| IDE | Config Path |
|-----|-------------|
| Claude Desktop | `~/.claude/claude_desktop_config.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `~/.vscode/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

Catches: missing commands, unset env vars, timeouts, slow servers, init errors.

### `mcptools inspect` — See What a Server Offers

Connect to any MCP server and list all its tools, resources, and prompts — without launching an IDE.

```bash
$ mcptools inspect uvx mcp-server-fetch
```
```
╭───────────────────────────── MCP Server ─────────────────────────────╮
│ mcp-fetch v1.26.0                                                    │
╰──────────────────────────────────────────────────────────────────────╯
                                Tools (1)
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name  ┃ Description                       ┃ Parameters              ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ fetch │ Fetches a URL from the internet   │ url: string*,           │
│       │ and extracts its contents as      │ max_length: integer,    │
│       │ markdown.                         │ start_index: integer,   │
│       │                                   │ raw: boolean            │
└───────┴───────────────────────────────────┴─────────────────────────┘
                             Prompts (1)
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Name  ┃ Description                                    ┃ Arguments ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ fetch │ Fetch a URL and extract its contents           │ url*      │
└───────┴────────────────────────────────────────────────┴───────────┘
```

Works with any server — Python, Node, Go. If it speaks MCP over stdio, mcptools can inspect it:

```bash
mcptools inspect uvx mcp-server-time
mcptools inspect python my_server.py
mcptools inspect npx @modelcontextprotocol/server-filesystem /tmp
```

### `mcptools proxy` — Live Traffic Interception

Sits between your IDE and MCP server as a transparent proxy. See every JSON-RPC message flowing through with a real-time TUI dashboard.

```
IDE (Claude Code / Cursor / Windsurf)
    ↓ stdio
mcptools proxy  ← intercepts, logs, measures
    ↓ stdio
MCP Server
```

```bash
mcptools proxy --config ~/.claude/claude_desktop_config.json --server github
mcptools proxy --config ~/.cursor/mcp.json --no-tui    # log mode, no TUI
```

The TUI shows:
- Live message stream with request/response pairing
- Per-call latency measurement
- Error highlighting
- Running stats (total messages, errors, avg latency)

### `mcptools record` / `mcptools replay` — Session Capture

Record an entire MCP session to JSON for offline analysis, sharing with teammates, or filing bug reports.

```bash
# Record everything
mcptools record --config ~/.claude/claude_desktop_config.json -o session.json

# Replay it later
mcptools replay session.json

# Replay at 2x speed, only tool calls
mcptools replay session.json --speed 2 --filter "tools/*"
```

The recorded JSON includes timestamps, directions, full payloads, and latency — everything needed to reconstruct what happened.

## Quick Start

```bash
# Install
pip install mcptools

# Check your setup
mcptools doctor

# Inspect a server
mcptools inspect uvx mcp-server-fetch

# See all commands
mcptools --help
```

## Why mcptools?

| | mcptools | MCP Inspector | Manual debugging |
|---|---------|---------------|-----------------|
| Install | `pip install mcptools` | Clone + npm | N/A |
| Config diagnosis | `mcptools doctor` | - | Read JSON manually |
| Server inspection | `mcptools inspect <cmd>` | Web UI | - |
| Traffic proxy | `mcptools proxy` | - | Print statements |
| Record & replay | `mcptools record/replay` | - | - |
| Works in terminal | Yes | No (browser) | Sort of |
| Multi-IDE config | Auto-detect | Manual | Manual |

## Architecture

```
src/mcptools/
├── cli.py              # Click CLI — all 5 commands
├── config/parser.py    # Multi-IDE config detection & parsing
├── proxy/
│   ├── interceptor.py  # Core proxy — message interception & relay
│   └── transport.py    # Stdio transport, JSON-RPC message handling
├── tui/dashboard.py    # Textual TUI with live stats
├── inspect/server.py   # Server introspection via MCP protocol
├── record/
│   ├── recorder.py     # Session recording to JSON
│   └── replayer.py     # Session replay with timing & filtering
└── doctor/checks.py    # Concurrent health checks & diagnostics
```

Built on: [mcp SDK](https://github.com/modelcontextprotocol/python-sdk) (protocol), [Textual](https://github.com/textualize/textual) (TUI), [Rich](https://github.com/textualize/rich) (formatting), [Click](https://click.palletsprojects.com) (CLI), [Pydantic](https://docs.pydantic.dev) (validation).

## Development

```bash
git clone https://github.com/jannik-cas/mcptools.git
cd mcptools
uv venv && uv pip install -e . && uv pip install pytest pytest-asyncio
pytest
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Good first issues:
- Add support for SSE transport (currently stdio only)
- Add `mcptools call` command to invoke a tool directly from CLI
- Support `.env` file loading for server environment variables
- Add JSON output mode (`--json`) for all commands

## License

MIT — see [LICENSE](LICENSE).
