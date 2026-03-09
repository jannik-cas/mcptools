---
layout: default
title: "I Built mitmproxy for MCP — Because Debugging MCP Servers Shouldn't Require Print Statements"
---

# I Built mitmproxy for MCP — Because Debugging MCP Servers Shouldn't Require Print Statements

If you've ever stared at a Claude Desktop config wondering why your MCP tool isn't showing up, this post is for you. I'll show you the exact tool I built to fix it, and you can follow along — every example in this post runs against real MCP servers.

**Time to follow along: ~5 minutes. All you need is `pip`.**

---

## The moment I snapped

I was setting up three MCP servers for a project. Two worked. One didn't. No error messages. No logs. Nothing.

My debugging process looked like this:

```
1. Re-read the config JSON for the 12th time
2. Restart Claude Desktop
3. Wait 30 seconds
4. Still broken
5. Add print() to the server code
6. Realize prints go to stdout and break the JSON-RPC stream
7. Redirect to stderr
8. Restart again
9. Typo in the env var name
10. 45 minutes gone
```

The problem was a typo in an environment variable. **45 minutes for a typo.**

MCP has zero built-in observability. You can't see what messages your IDE sends. You can't see what the server responds. You can't even check if the server starts correctly — you just get silence.

So I built the tool I wished existed.

---

## Install it. Right now.

```bash
pip install mcptools
```

That's it. No npm. No Docker. No config changes. Let's use it.

---

## Round 1: "Is my setup broken?" → `mcptools doctor`

Let's create a config with three servers — two that work and one that's intentionally broken. Save this as `test_config.json`:

```json
{
  "mcpServers": {
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time"]
    },
    "broken": {
      "command": "nonexistent-mcp-server-xyz",
      "args": []
    }
  }
}
```

Or just use the one that ships with mcptools:

```bash
mcptools doctor --config examples/demo_config.json
```

Output:

```
Config: examples/demo_config.json

  Checking fetch...          ✓ 1 tool, 1 prompt
  Checking time...           ✓ 2 tools
  Checking broken...         ✗ Command not found: nonexistent-mcp-server-xyz
    → Ensure 'nonexistent-mcp-server-xyz' is installed and in your PATH

Summary: 2 healthy, 1 error
```

**That's 2 seconds.** Not 45 minutes. Two seconds.

`doctor` actually starts each server, sends the MCP `initialize` handshake, queries capabilities, and measures latency. It catches:

- Missing commands (typos in `"command"`)
- Unresolved environment variables
- Servers that start but don't speak MCP
- Slow servers (>2s warning, >5s error)
- Initialization failures

**Try it on your own config right now.** If you use Claude Desktop:

```bash
mcptools doctor --config ~/.claude/claude_desktop_config.json
```

Cursor:

```bash
mcptools doctor --config ~/.cursor/mcp.json
```

Or just let it auto-detect:

```bash
mcptools doctor
```

It searches Claude Desktop, Cursor, VS Code, and Windsurf config paths automatically.

---

## Round 2: "What can this server actually do?" → `mcptools inspect`

You found a cool MCP server on GitHub. Before you wire it into your IDE, you want to know: what tools does it expose? What parameters do they take?

```bash
mcptools inspect uvx mcp-server-fetch
```

```
╭───────────────────────── MCP Server ─────────────────────────╮
│ mcp-fetch v1.26.0                                             │
╰──────────────────────────────────────────────────────────────╯
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

Now you know exactly what `mcp-server-fetch` offers before adding it to your config. The `*` marks required parameters.

**Try another one:**

```bash
mcptools inspect uvx mcp-server-time
```

```
╭───────────────────────── MCP Server ─────────────────────────╮
│ mcp-server-time v0.6.2                                        │
╰──────────────────────────────────────────────────────────────╯
                         Tools (2)
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name             ┃ Description                ┃ Parameters             ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ get_current_time │ Get current time in a      │ timezone: string       │
│                  │ specific timezone          │                        │
│ convert_time     │ Convert time between       │ source_timezone:       │
│                  │ timezones                  │ string*, ...           │
└──────────────────┴────────────────────────────┴────────────────────────┘
```

This works with any MCP server — Python, Node, Go. If it speaks MCP over stdio, mcptools can inspect it:

```bash
mcptools inspect python my_server.py
mcptools inspect npx @modelcontextprotocol/server-filesystem /tmp
mcptools inspect node build/index.js
```

---

## Round 3: "What's actually happening on the wire?" → `mcptools proxy`

This is where it gets interesting. `mcptools proxy` sits between your IDE and the MCP server, intercepting every JSON-RPC message.

```
Your IDE (Claude Code / Cursor / Windsurf)
    ↓ stdin/stdout
mcptools proxy  ←  sees everything
    ↓ stdin/stdout
MCP Server
```

```bash
mcptools proxy --config ~/.claude/claude_desktop_config.json --server fetch
```

This opens a real-time TUI dashboard showing:

- Every request and response flowing through
- Direction arrows (→ outgoing, ← incoming)
- Per-call latency in milliseconds
- Errors highlighted in red
- Running stats (total messages, error count, average latency)

Click any row to see the **full JSON-RPC payload** in the detail panel at the bottom.

If you prefer plain logs:

```bash
mcptools proxy --config ~/.cursor/mcp.json --server github --no-tui
```

```
>>> initialize                        120ms
<<< initialize
>>> notifications/initialized
>>> tools/list                        45ms
<<< tools/list
>>> tools/call                        1205ms
<<< tools/call
```

Now you can see exactly what your IDE sends, what the server responds, and how long each call takes. No more guessing.

---

## Round 4: "Can I capture a session and replay it later?" → `mcptools record` + `replay`

Perfect for bug reports, sharing with teammates, or reproducing issues.

**Record:**

```bash
mcptools record --config ~/.claude/claude_desktop_config.json -o debug_session.json
```

This starts the proxy in recording mode. Use your IDE normally — every MCP message gets captured. Hit `Ctrl+C` to stop and save.

**Replay:**

```bash
mcptools replay debug_session.json
```

```
╭──────────────────── MCP Session Replay ────────────────────╮
│ Session: debug_session.json                                 │
│ Messages: 24 | Duration: 12.3s | Speed: 1x                 │
╰────────────────────────────────────────────────────────────╯

+0.0s >>> initialize
+0.1s <<< initialize                     120ms
+0.1s >>> notifications/initialized
+0.2s >>> tools/list                      45ms
+0.3s <<< tools/list
+2.1s >>> tools/call                      1205ms
+3.3s <<< tools/call
```

**Replay only tool calls at 2x speed:**

```bash
mcptools replay debug_session.json --speed 2 --filter "tools/*"
```

The recorded JSON has everything — timestamps, directions, full payloads, latency measurements. Attach it to a GitHub issue and the maintainer can see exactly what happened.

---

## Real-world scenario: "Why does my GitHub MCP server time out?"

Let me walk through a real debugging session.

**Step 1: Check if it's a config issue.**

```bash
mcptools doctor --server github
```

```
  Checking github...  ⚠ 35 tools — Slow response (3200ms)
```

OK, it starts — but it's slow. 3.2 seconds just to initialize.

**Step 2: Inspect what it offers.**

```bash
mcptools inspect uvx mcp-server-github
```

35 tools. That's a lot. The server might be doing heavy work during startup.

**Step 3: Watch the actual traffic.**

```bash
mcptools proxy --config ~/.claude/claude_desktop_config.json --server github --no-tui
```

Now use Claude Desktop and ask it to do something with GitHub. Watch the proxy output:

```
>>> initialize                           3205ms
<<< initialize
>>> tools/list                           89ms
<<< tools/list
>>> tools/call                           timeout
  ERROR: Request timed out after 30s
```

Found it. The `tools/call` is timing out. Now you can look at the specific tool being called, check if the GitHub token has the right scopes, or file a bug with the exact payload.

**Step 4: Record it for the bug report.**

```bash
mcptools record --server github -o github_timeout.json
# reproduce the issue
# Ctrl+C
```

Attach `github_timeout.json` to the issue. Done.

---

## How it works (in 30 seconds)

mcptools speaks the same JSON-RPC 2.0 protocol that MCP uses. When you run `inspect`, it:

1. Starts the server as a subprocess
2. Sends `initialize` with MCP protocol version
3. Sends `tools/list`, `resources/list`, `prompts/list`
4. Formats the responses into tables

When you run `proxy`, it:

1. Reads JSON-RPC from stdin (your IDE)
2. Forwards to the real server's stdin
3. Reads from the server's stdout
4. Forwards back to your IDE's stdout
5. Logs everything passing through

It's a transparent man-in-the-middle. Your IDE doesn't know it's there.

```
src/mcptools/
├── cli.py              # Click CLI — 5 commands
├── jsonrpc.py          # Shared JSON-RPC helpers
├── config/parser.py    # Auto-detects IDE configs
├── doctor/checks.py    # Concurrent health checks
├── inspect/server.py   # Server introspection
├── proxy/
│   ├── interceptor.py  # Traffic interception
│   └── transport.py    # Stdio transport layer
├── record/
│   ├── recorder.py     # Session capture
│   └── replayer.py     # Session replay
└── tui/dashboard.py    # Real-time TUI
```

---

## Your turn

```bash
pip install mcptools
mcptools doctor
```

That's it. Two commands. You'll either see all green checkmarks (great, your setup works) or you'll find the issue that's been bugging you for days.

**If mcptools saves you time, [star the repo](https://github.com/jannik-cas/mcptools).** It helps others find it.

**Found a bug or want a feature?** [Open an issue](https://github.com/jannik-cas/mcptools/issues). The codebase is ~2500 lines of Python — contributions are welcome.

---

*[mcptools on GitHub](https://github.com/jannik-cas/mcptools) | [PyPI](https://pypi.org/project/mcptools/) | MIT License*
