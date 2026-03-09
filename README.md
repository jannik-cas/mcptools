<p align="center">
  <h1 align="center">mcptools</h1>
  <p align="center">
    <strong>mitmproxy for MCP</strong> — intercept, inspect, debug, and replay MCP server traffic
  </p>
  <p align="center">
    <img alt="Python" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue">
    <a href="https://github.com/jannik-cas/mcptools/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/jannik-cas/mcptools/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://codecov.io/gh/jannik-cas/mcptools"><img alt="Coverage" src="https://codecov.io/gh/jannik-cas/mcptools/branch/main/graph/badge.svg"></a>
    <a href="https://github.com/jannik-cas/mcptools/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/jannik-cas/mcptools"></a>
    <a href="https://github.com/jannik-cas/mcptools/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/jannik-cas/mcptools?style=social"></a>
  </p>
</p>

---

<!-- TODO: Record a terminal demo with vhs or asciinema and embed here:
     ![mcptools demo](assets/demo.gif)

     Record with: vhs demo.tape  (see https://github.com/charmbracelet/vhs)
     Or: asciinema rec demo.cast && agg demo.cast demo.gif
-->

```
$ mcptools doctor --config examples/demo_config.json

Config: examples/demo_config.json

  Checking fetch...          ✓ 1 tool, 1 prompt
  Checking time...           ✓ 2 tools
  Checking broken-server...  ✗ Command not found: nonexistent-mcp-server-xyz
    → Ensure 'nonexistent-mcp-server-xyz' is installed and in your PATH

Summary: 2 healthy, 1 error
```

```
$ mcptools inspect uvx mcp-server-fetch

╭───────────────────────── MCP Server ─────────────────────────╮
│ mcp-fetch v1.26.0                                             │
╰──────────────────────────────────────────────────────────────╯
                         Tools (1)
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name  ┃ Description                ┃ Parameters             ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ fetch │ Fetches a URL and extracts │ url: string*,          │
│       │ its contents as markdown.  │ max_length: integer,   │
│       │                            │ raw: boolean           │
└───────┴────────────────────────────┴────────────────────────┘
```

---

Every MCP-powered IDE talks to MCP servers — but when tools break, there's zero visibility. **mcptools** gives you `doctor`, `inspect`, `proxy`, `record`, and `replay` for any MCP server. One `pip install`, works with any IDE, no config changes needed.

## Quick Start

```bash
pip install git+https://github.com/jannik-cas/mcptools.git

# Diagnose your setup in 2 seconds
mcptools doctor

# See what any server offers
mcptools inspect uvx mcp-server-fetch

# Try the demo config
mcptools doctor --config examples/demo_config.json
```

## The Problem

```
You: "Why isn't my MCP tool showing up?"
*restarts IDE* → *re-reads config* → *adds print statements* → *gives up*
```

MCP has no built-in observability. You're flying blind.

## The Fix

```bash
mcptools doctor
```

Found the issue in 2 seconds.

## Features

### `mcptools doctor` — Instant Config Diagnosis

Reads your IDE's MCP config, spins up each server, checks connectivity, and reports what's healthy and what's broken.

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
mcptools inspect uvx mcp-server-fetch
mcptools inspect uvx mcp-server-time
mcptools inspect python my_server.py
mcptools inspect npx @modelcontextprotocol/server-filesystem /tmp
```

### `mcptools proxy` — Live Traffic Interception

Sits between your IDE and MCP server as a transparent proxy. See every JSON-RPC message with a real-time TUI dashboard.

```
IDE (Claude Code / Cursor / Windsurf)
    ↓ stdio
mcptools proxy  ← intercepts, logs, measures
    ↓ stdio
MCP Server
```

```bash
mcptools proxy --config ~/.claude/claude_desktop_config.json --server github
mcptools proxy --config ~/.cursor/mcp.json --no-tui    # log mode
```

The TUI shows: live message stream, per-call latency, error highlighting, running stats, and full JSON payload details.

### `mcptools record` / `mcptools replay` — Session Capture

Record an entire MCP session to JSON for offline analysis, sharing, or filing bug reports.

```bash
mcptools record --config ~/.claude/claude_desktop_config.json -o session.json
mcptools replay session.json
mcptools replay session.json --speed 2 --filter "tools/*"
```

## Why mcptools?

| | mcptools | MCP Inspector | Manual debugging |
|---|---------|---------------|-----------------|
| Install | `pip install git+...` | Clone + npm | N/A |
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
├── jsonrpc.py          # Shared JSON-RPC 2.0 helpers
├── config/parser.py    # Multi-IDE config detection & parsing
├── proxy/
│   ├── interceptor.py  # Core proxy — message interception & relay
│   └── transport.py    # Stdio transport, JSON-RPC message handling
├── tui/dashboard.py    # Textual TUI with live stats & detail panel
├── inspect/server.py   # Server introspection via MCP protocol
├── record/
│   ├── recorder.py     # Session recording to JSON
│   └── replayer.py     # Session replay with timing & filtering
└── doctor/checks.py    # Concurrent health checks & diagnostics
```

Built on: [mcp SDK](https://github.com/modelcontextprotocol/python-sdk) (protocol), [Textual](https://github.com/textualize/textual) (TUI), [Rich](https://github.com/textualize/rich) (formatting), [Click](https://click.palletsprojects.com) (CLI), [Pydantic](https://docs.pydantic.dev) (validation).

## Quick Start for Contributors

```bash
git clone https://github.com/jannik-cas/mcptools.git
cd mcptools
pip install -e ".[dev]"
make test
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. [Good first issues](https://github.com/jannik-cas/mcptools/labels/good%20first%20issue) are a great place to start.

## License

MIT — see [LICENSE](LICENSE).
