# generic-data-mcp

An MCP server that ingests structured data files (CSV, TSV, pipe-delimited, JSON, JSONL) into SQLite and exposes them as queryable tools for an LLM. The user asks questions in natural language; the LLM composes the tools to answer.

## Tools

| Tool | What it does |
|------|--------------|
| `ingest_file` | Parse a file, infer types, create a SQLite table |
| `list_datasets` | Show every loaded table with row counts and source paths |
| `describe_table` | Schema + sample rows for one table |
| `query` | Run a read-only SELECT (single statement, capped at 1000 rows) |
| `search` | Enable FTS5 on (table, columns), then run keyword searches |

## Design notes

**OOP throughout.** Every concept is a class. Parsers are a strategy hierarchy under `BaseParser` with a `ParserRegistry` for resolution. The storage layer splits into four focused managers (`TableManager`, `DataIngestor`, `QueryExecutor`, `SearchIndex`) under a single `SQLiteStore`. Tools are command objects under `BaseTool`, held by `ToolRegistry`. Validators are pure: they raise on bad input and have no side effects.

**Dependency injection.** Every collaborator is passed through the constructor. No globals, no singletons, no module-level state outside class definitions. Means every class is unit-testable in isolation — see the e2e test that builds a real `SQLiteStore` against `tmp_path` and exercises the tools directly.

**Tool descriptions are written for the LLM.** Each `description` says *when* to use the tool and how to compose inputs (e.g. *"call describe_table first if you don't know the schema"*). Errors are written so the LLM can recover — *"Only SELECT is allowed; got DROP. To explore the schema, use describe_table"* is more useful than *"Invalid SQL"*.

**SQL safety.** I pass user/LLM SQL through `sqlglot` (a real parser, not regex), reject any non-SELECT, reject multi-statement queries, and walk the AST for forbidden node types as defense-in-depth. Identifiers passed through other tools (`table_name`, columns) are validated against `[A-Za-z_][A-Za-z0-9_]*` even though I always quote them.

**Path safety.** `ingest_file` only accepts paths under `MCP_ALLOWED_DIRS`. Paths are resolved (`Path.resolve()`) before the check, so symlinks and `..` traversal can't escape. Belt-and-braces against the LLM passing `/etc/passwd` or similar.

**Type inference is conservative.** Sample 200 rows; a column is INTEGER only if every non-empty value parses as int, REAL if every value parses as a number, otherwise TEXT. Booleans are intentionally NOT coerced to integers — too easy to lose semantics.

**Streaming ingest.** Parsers yield rows; `DataIngestor` batches them (1000 at a time) inside a single transaction. Files larger than RAM work fine.

**FTS5 is opt-in.** Auto-indexing every table doubles storage. Instead, the `search` tool's `enable` action lets the LLM (or user) index a specific (table, columns) pair. Triggers keep the index in sync with the source table.

## With more time

- **More parsers**: Excel (openpyxl), Parquet, YAML, TOML, fixed-width text
- **Vector search**: add `sqlite-vec` so the LLM can search by meaning, not just keywords
- **Watch mode**: re-ingest files when they change on disk
- **Sampling/aggregation helpers**: `sample(table, n)`, `group_by(table, col, agg)` so the LLM doesn't always have to write SQL
- **Multi-tenant workspaces**: isolated SQLite databases per tenant

## Running

```bash
pip install -e .
MCP_DB_PATH=./data/store.db MCP_ALLOWED_DIRS=./data generic-data-mcp
```

## Client configuration

Any MCP-compatible client works. The server communicates over **stdio** — the client spawns it as a subprocess and passes `MCP_DB_PATH` and `MCP_ALLOWED_DIRS` as environment variables.

**Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "generic-data-mcp": {
      "command": "generic-data-mcp",
      "env": {
        "MCP_DB_PATH": "/absolute/path/to/store.db",
        "MCP_ALLOWED_DIRS": "/absolute/path/to/data"
      }
    }
  }
}
```

**Cursor** — `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project-level):

```json
{
  "mcpServers": {
    "generic-data-mcp": {
      "command": "generic-data-mcp",
      "env": {
        "MCP_DB_PATH": "/absolute/path/to/store.db",
        "MCP_ALLOWED_DIRS": "/absolute/path/to/data"
      }
    }
  }
}
```

**VS Code (GitHub Copilot)** — `.vscode/mcp.json` in the workspace:

```json
{
  "servers": {
    "generic-data-mcp": {
      "command": "generic-data-mcp",
      "env": {
        "MCP_DB_PATH": "/absolute/path/to/store.db",
        "MCP_ALLOWED_DIRS": "/absolute/path/to/data"
      }
    }
  }
}
```

## Layout

```
src/
  server.py              MCP entry point, wires the dependency graph
  config.py              Config from env vars
  exceptions/            Custom exception hierarchy
  parsers/
    base.py              BaseParser ABC
    delimited.py         CSV, TSV, pipe-delimited
    json_parsers.py      JSON, JSONL
    registry.py          ParserRegistry (auto-detect by extension)
  storage/
    sqlite_store.py      Composition root
    types.py             SQLType, ColumnSchema, TableSchema, TypeInferrer
    tables.py            TableManager
    ingest.py            DataIngestor (batched, transactional)
    query.py             QueryExecutor (capped result set)
    search.py            SearchIndex (FTS5)
    metadata.py          MetadataStore (dataset registry)
  tools/
    base.py              BaseTool, ToolResult, ToolRegistry
    ingest_file.py
    list_datasets.py
    describe_table.py
    query.py
    search.py
  validators/
    sql.py               SQLValidator (sqlglot)
    path.py              PathValidator (allowed dirs)
tests/
  test_sql_validator.py
  test_type_inferrer.py
  test_e2e.py
```

Run tests: `python -m pytest tests/ -v`
