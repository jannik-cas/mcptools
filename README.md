<p align="center">
  <h1 align="center">mcptools</h1>
  <p align="center">
    <strong>mitmproxy for MCP</strong> — intercept, inspect, debug, and replay MCP server traffic
  </p>
  <p align="center">
    <img alt="Python" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue">
    <a href="https://github.com/jannik-cas/mcptools/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/jannik-cas/mcptools/actions/workflows/ci.yml/badge.svg"></a>
    <a href="https://github.com/jannik-cas/mcptools/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/jannik-cas/mcptools"></a>
    <a href="https://github.com/jannik-cas/mcptools/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/jannik-cas/mcptools?style=social"></a>
  </p>
</p>

---

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
$ mcptools call uvx mcp-server-fetch --tool fetch --args '{"url": "https://example.com"}'

╭──── fetch ────╮
│ # Example     │
│ Domain        │
│ This domain   │
│ is for use in │
│ illustrative  │
│ examples...   │
╰───────────────╯
```

---

MCP servers talk to your IDE over stdio, but when something breaks you get zero feedback. No logs, no error messages, just a tool that doesn't show up and no way to figure out why.

**mcptools** gives you six commands to fix that: `doctor`, `inspect`, `call`, `proxy`, `record`, and `replay`. One install, works with any IDE, no config changes.

## Install

```bash
pip install git+https://github.com/jannik-cas/mcptools.git
```

## Commands

### `mcptools doctor` — check if your servers work

Reads your IDE config, starts each server, runs the MCP handshake, reports what's healthy and what's broken.

```bash
mcptools doctor                                          # auto-detects config
mcptools doctor --config ~/.cursor/mcp.json              # explicit
mcptools doctor --server github --server filesystem      # specific servers
mcptools doctor --json                                   # pipe to jq
```

Auto-detects configs from Claude Desktop, Cursor, VS Code, and Windsurf.

### `mcptools inspect` — see what a server exposes

```bash
mcptools inspect uvx mcp-server-fetch
mcptools inspect python my_server.py
mcptools inspect npx @modelcontextprotocol/server-filesystem /tmp
mcptools inspect uvx mcp-server-fetch --json             # machine-readable
```

```
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

### `mcptools call` — invoke a tool directly

Test any MCP tool from your terminal without opening an IDE.

```bash
mcptools call uvx mcp-server-fetch --tool fetch --args '{"url": "https://example.com"}'
mcptools call uvx mcp-server-time --tool get_current_time
mcptools call python my_server.py --tool greet --args '{"name": "World"}'
mcptools call uvx mcp-server-fetch --tool fetch --args '{"url": "..."}' --json
```

Returns pretty-printed output by default. JSON responses get syntax highlighting. Pass `--json` for machine-readable output you can pipe to `jq`.

### `mcptools proxy` — watch the traffic

Transparent man-in-the-middle between your IDE and MCP server.

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

TUI dashboard shows: live message stream, per-call latency, error highlighting, running stats, and a detail panel with the raw JSON-RPC payload.

### `mcptools record` / `mcptools replay`

Capture a full MCP session to JSON. Replay it later for debugging or attach it to a bug report.

```bash
mcptools record --config ~/.claude/claude_desktop_config.json -o session.json
mcptools replay session.json
mcptools replay session.json --speed 2 --filter "tools/*"
```

## `--json` for scripting

`doctor`, `inspect`, and `call` all support `--json` for pipeable output:

```bash
mcptools doctor --json | jq '.servers[] | select(.status != "healthy")'
mcptools inspect uvx mcp-server-fetch --json | jq '.tools[].name'
mcptools call uvx mcp-server-time --tool get_current_time --json | jq '.content[0].text'
```

## Architecture

```
src/mcptools/
├── cli.py              # Click CLI — 6 commands
├── jsonrpc.py          # Shared JSON-RPC 2.0 helpers
├── config/parser.py    # Multi-IDE config detection & parsing
├── proxy/
│   ├── interceptor.py  # Core proxy — message interception & relay
│   └── transport.py    # Stdio transport, JSON-RPC message handling
├── tui/dashboard.py    # Textual TUI with live stats & detail panel
├── inspect/
│   ├── server.py       # Server introspection via MCP protocol
│   └── caller.py       # Direct tool invocation
├── record/
│   ├── recorder.py     # Session recording to JSON
│   └── replayer.py     # Session replay with timing & filtering
└── doctor/checks.py    # Concurrent health checks & diagnostics
```

~2,500 lines of Python. Built on [mcp SDK](https://github.com/modelcontextprotocol/python-sdk), [Textual](https://github.com/textualize/textual), [Rich](https://github.com/textualize/rich), [Click](https://click.palletsprojects.com), [Pydantic](https://docs.pydantic.dev).

## Contributing

```bash
git clone https://github.com/jannik-cas/mcptools.git
cd mcptools
pip install -e ".[dev]"
make test
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details. Some things that would be useful:

- **SSE transport** — right now only stdio works
- **`.env` file support** — load server env vars from `.env`
- **Config generation** — `mcptools init` to scaffold a config
- **More health checks** — detect duplicate names, invalid schemas

[Good first issues](https://github.com/jannik-cas/mcptools/labels/good%20first%20issue) are labeled.

## License

MIT — see [LICENSE](LICENSE).
