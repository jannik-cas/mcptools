# Contributing to mcptools

Thanks for your interest in contributing! Here's how to get started.

## Setup

```bash
git clone https://github.com/jannik-cas/mcptools.git
cd mcptools
uv venv && uv pip install -e . && uv pip install pytest pytest-asyncio ruff
```

## Running Tests

```bash
pytest                  # run all tests
pytest -v               # verbose output
pytest tests/test_cli.py  # specific test file
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .            # lint
ruff format .           # format
```

## Making Changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Run `pytest` and `ruff check .` to verify
5. Open a pull request

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Add tests for new commands or behavior changes
- Update the README if adding new user-facing features
- Write a clear PR description explaining *why*, not just *what*

## Project Structure

```
src/mcptools/
├── cli.py              # CLI entry point — add new commands here
├── config/parser.py    # Config file detection and parsing
├── proxy/              # Proxy and transport layer
├── tui/                # TUI dashboard (Textual)
├── inspect/            # Server introspection
├── record/             # Record and replay
└── doctor/             # Health checks
```

## Ideas for Contributions

- **SSE transport support** — currently only stdio is implemented
- **`mcptools call <tool>`** — invoke a tool directly from the CLI
- **JSON output mode** — `--json` flag for scripting/piping
- **`.env` file support** — load server env vars from `.env` files
- **Config generation** — `mcptools init` to scaffold a config file
- **More health checks** — detect duplicate server names, invalid JSON schemas, etc.
