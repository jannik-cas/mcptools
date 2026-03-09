# Contributing to mcptools

## Setup

```bash
git clone https://github.com/jannik-cas/mcptools.git
cd mcptools
pip install -e ".[dev]"
```

Or with uv:

```bash
uv venv && uv pip install -e ".[dev]"
```

## Running tests

```bash
make test          # pytest with coverage
make lint          # ruff check + format check
make format        # auto-fix formatting
```

Or directly:

```bash
pytest -v
ruff check .
ruff format .
```

## Branching strategy

We use **GitHub Flow** — all work happens on short-lived branches off `main`:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/<name>` | New features | `feat/sse-transport` |
| `fix/<name>` | Bug fixes | `fix/timeout-handling` |
| `refactor/<name>` | Code improvements | `refactor/dry-handshake` |
| `docs/<name>` | Documentation only | `docs/api-reference` |

All branches merge to `main` via pull request. Direct pushes to `main` are
blocked by branch protection rules.

## Making changes

1. Fork the repo, create a branch from `main` using the prefixes above
2. Write your code
3. Add tests for new functionality
4. Run `make test && make lint`
5. Open a pull request

## PR guidelines

- One feature or fix per PR
- Add tests for new commands or behavior changes
- Update the README if you're adding user-facing features
- Write a clear description — explain *why*, not just *what*

## Project structure

```
src/mcptools/
├── cli.py              # CLI entry point — add new commands here
├── jsonrpc.py          # Shared JSON-RPC 2.0 helpers
├── config/parser.py    # Config file detection and parsing
├── proxy/              # Proxy and transport layer
├── tui/                # TUI dashboard (Textual)
├── inspect/
│   ├── server.py       # Server introspection
│   └── caller.py       # Direct tool invocation (mcptools call)
├── record/             # Record and replay
└── doctor/             # Health checks
```

## Ideas for contributions

Things that would genuinely be useful but aren't built yet:

- **SSE transport support** — only stdio is implemented right now
- **`.env` file support** — load server env vars from `.env` files
- **`mcptools init`** — scaffold a config file interactively
- **JSON output for `proxy`** — structured log output for `--no-tui` mode
- **More health checks** — detect duplicate server names, invalid JSON schemas, version mismatches
- **Shell completions** — bash/zsh/fish completions for commands and `--server` names
- **Config validation** — `mcptools lint` to check config files for common mistakes
