# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode (required before running anything)
pip install -e .

# Run the server
MCP_DB_PATH=./data/store.db MCP_ALLOWED_DIRS=./data generic-data-mcp

# Run all tests
python -m pytest tests/ -v

# Run a single test
python -m pytest tests/test_e2e.py::test_ingest_then_query -v
```

No linter is configured. No build step is needed beyond `pip install -e .`.

## Architecture

This is an MCP server that ingests structured files (CSV, TSV, pipe-delimited, JSON, JSONL) into SQLite and exposes five tools to LLMs: `ingest_file`, `list_datasets`, `describe_table`, `query`, `search`.

**Dependency graph (wired in `server.py`):**


**Key design decisions:**

- **All collaborators are constructor-injected** — no globals, no singletons, no module-level state. Every class is independently testable (see `test_e2e.py` which builds a real `SQLiteStore` against `tmp_path`).
- **Parsers yield `dict[str, str]`** — raw strings only. Type inference happens in the storage layer (`TypeInferrer` in `storage/types.py`), not in parsers. Samples 200 rows; a column becomes INTEGER/REAL only if every non-empty value parses cleanly.
- **`server.py` is the only MCP boundary** — the `@server.list_tools()` and `@server.call_tool()` decorators live there and delegate immediately to `ToolRegistry`. Tool classes know nothing about MCP.
- **Tool errors are written for LLM recovery** — `ToolResult.fail(error)` messages tell the LLM what to do next (e.g., "call describe_table first"). `ToolResult.ok(**data)` wraps the success payload.
- **SQL safety uses sqlglot AST walking** — not regex. Allows SELECT/WITH…SELECT/UNION; rejects everything else including `PRAGMA`/`ATTACH` via `exp.Command`.
- **FTS5 is opt-in** — the `search` tool's `enable` action creates the FTS5 virtual table and triggers for a specific (table, columns) pair. Not auto-created on ingest.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_DB_PATH` | `./data/store.db` | SQLite file location |
| `MCP_ALLOWED_DIRS` | `./data` | Colon-separated list of directories `ingest_file` may read from |

## Adding a New Parser

1. Subclass `BaseParser` in `src/parsers/`, set `name`, `extensions`, implement `parse()` as a generator yielding `dict[str, str]`.
2. Register it in `src/parsers/registry.py` (`ParserRegistry.__init__`).

## Adding a New Tool

1. Subclass `BaseTool` in `src/tools/`, set `name`, `description` (written for the LLM), `input_schema` (JSON Schema), implement `execute()` returning `ToolResult`.
2. Add it to the list in `MCPServer._build_registry()` in `server.py`.
3. Export it from `src/tools/__init__.py`.

╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Docker Containerization Plan: generic-data-mcp                                                                                                                                                                                     

 Context

 The project is a Python MCP (Model Context Protocol) server that ingests structured files into SQLite and exposes query/search tools to LLMs. MCP clients (Claude Desktop, Cursor, VS Code) spawn the server as a subprocess and
 communicate via stdio (stdin/stdout). The goal is to package this as a Docker image so users can run it without a local Python environment, and so the server is isolated and reproducible.

 Critical Design Constraints

 - stdio transport — the server reads JSON-RPC from stdin and writes to stdout. No HTTP, no ports. docker run -i keeps stdin open; tty must be false (a TTY merges stderr into stdout, corrupting MCP framing).
 - PathValidator — src/validators/path.py resolves every ingest path against MCP_ALLOWED_DIRS. The env var must match the volume mount path inside the container or all ingest_file calls will fail.
 - SQLite persistence — the DB lives in /data (a volume), not in the container layer.

 Files to Create

 1. Dockerfile

 # syntax=docker/dockerfile:1
 FROM python:3.11-slim

 LABEL org.opencontainers.image.title="generic-data-mcp" \
       org.opencontainers.image.description="MCP server: structured files → SQLite → LLM tools"

 # no-login shell; sqlite3 CLI omitted (use a separate ephemeral container to inspect DB)
 RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin mcp

 WORKDIR /app
 COPY pyproject.toml ./
 COPY src/ ./src/
 RUN pip install --no-cache-dir .

 # /data -- user files (ingest_file reads from here)
 # /db   -- SQLite DB on a separate volume, outside the ingest-allowed tree
 RUN mkdir -p /data /db && chown mcp:mcp /data /db
 VOLUME /data
 VOLUME /db

 ENV MCP_DB_PATH=/db/store.db \
     MCP_ALLOWED_DIRS=/data

 USER mcp
 ENTRYPOINT ["generic-data-mcp"]

 Key decisions:
 - Single-stage (no multi-stage needed -- pure Python, nothing to compile)
 - No extra packages -- sqlite3 CLI available via a separate ephemeral container
 - Non-root mcp user (uid 1000) with nologin shell; /data and /db pre-owned
 - DB lives at /db (separate volume) so the SQLite file is outside the ingest-allowed tree
 - pip install . (not editable) -- installs the src.server:main entry point to /usr/local/bin/generic-data-mcp
 - Pin base image to a digest: docker pull python:3.11-slim && docker inspect python:3.11-slim --format='{{index .RepoDigests 0}}'

 2. docker-compose.yml

 services:
   generic-data-mcp:
     build:
       context: .
       dockerfile: Dockerfile
     image: generic-data-mcp:dev
     stdin_open: true   # required: keeps stdin open for MCP stdio transport
     tty: false         # required: TTY would corrupt MCP JSON-RPC framing on stdout
     network_mode: "none"
     read_only: true
     security_opt:
       - "no-new-privileges:true"
     cap_drop:
       - ALL
     mem_limit: 512m
     pids_limit: 128
     tmpfs:
       - /tmp:size=64m,mode=1777
     volumes:
       - ./data:/data   # user files for ingest_file
       - db-data:/db    # SQLite DB isolated from ingest-allowed tree
     environment:
       MCP_DB_PATH: /db/store.db
       MCP_ALLOWED_DIRS: /data

 volumes:
   db-data:

 Note: use docker compose run --rm generic-data-mcp for interactive sessions, not up.

 3. .dockerignore

 .git
 .gitignore
 .idea/
 .vscode/
 __pycache__/
 *.py[cod]
 *.egg-info/
 dist/
 build/
 .venv/
 venv/
 .pytest_cache/
 .coverage
 data/          # CRITICAL: must not bake user data into image layers
 *.md
 !README.md
 .github/
 *.log
 .DS_Store

 data/ exclusion is critical — baking it in would embed user data into the image.

 4. MCP Client Config (example: Claude Desktop)

 {
   "mcpServers": {
     "generic-data-mcp": {
       "command": "docker",
       "args": [
         "run", "--rm", "-i",
         "--network", "none",
         "-v", "/absolute/path/to/data:/data",
         "-v", "/absolute/path/to/db:/db",
         "-e", "MCP_DB_PATH=/db/store.db",
         "-e", "MCP_ALLOWED_DIRS=/data",
         "generic-data-mcp:latest"
       ]
     }
   }
 }

 --rm removes the container when the session ends. -i keeps stdin open. Replace /absolute/path/to/data with a real host path.

 Build & Verify

 # Build
 docker build -t generic-data-mcp:latest .

 # Smoke test (server starts, exits on EOF -- correct behaviour)
 echo '{}' | docker run --rm -i --network none -v "$(pwd)/data:/data" -v "$(pwd)/db:/db" generic-data-mcp:latest

 # Run tests against host Python (tests don't need Docker)
 python -m pytest tests/ -v

 # Inspect DB after a session (ephemeral container; not the production image)
 docker run --rm -it -v "$(pwd)/db:/db" --entrypoint sqlite3 python:3.11-slim /db/store.db ".tables"

 Critical Files (read before implementing)

 - pyproject.toml — package name, entry point declaration, dependencies
 - src/server.py — main() entry point, server startup/shutdown
 - src/config.py — how MCP_DB_PATH and MCP_ALLOWED_DIRS are read
 - src/validators/path.py — why MCP_ALLOWED_DIRS must match the mount path exactly