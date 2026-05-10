# CLAUDE.md — generic-data-mcp

## Project Overview

An MCP (Model Context Protocol) server written in Python 3.11+. It ingests structured data files (CSV, TSV, pipe-delimited, JSON, JSONL) into an in-process SQLite database and exposes them as queryable tools that an LLM uses to answer natural-language questions about data.

The server runs over **stdio** — clients (Claude Desktop, Cursor, VS Code Copilot) spawn it as a subprocess.

---

## Quick Start

```bash
pip install -e ".[dev]"                          # install with dev dependencies
MCP_DB_PATH=./data/store.db MCP_ALLOWED_DIRS=./data generic-data-mcp   # run server
python -m pytest tests/ -v                       # run tests
```

Required environment variables:
- `MCP_DB_PATH` — path to the SQLite database file (created if absent)
- `MCP_ALLOWED_DIRS` — comma- or colon-separated list of directories `ingest_file` may read from

---

## Repository Layout

```
src/
  server.py              MCP entry point — wires the dependency graph, registers tools
  config.py              Reads MCP_DB_PATH / MCP_ALLOWED_DIRS from env
  exceptions/            Custom exception hierarchy (all inherit from a base MCPError)
  parsers/
    base.py              BaseParser ABC — yields rows as dicts
    delimited.py         CSV, TSV, pipe-delimited (strategy objects)
    json_parsers.py      JSON (array of objects), JSONL (one object per line)
    registry.py          ParserRegistry — maps file extension → parser instance
  storage/
    sqlite_store.py      SQLiteStore — composition root, owns the connection
    types.py             SQLType enum, ColumnSchema, TableSchema, TypeInferrer
    tables.py            TableManager — CREATE TABLE, DROP, list
    ingest.py            DataIngestor — streaming batch INSERT (1 000 rows/batch)
    query.py             QueryExecutor — validated SELECT, capped at 1 000 rows
    search.py            SearchIndex — FTS5 virtual table management + search
    metadata.py          MetadataStore — dataset registry (source path, row count, etc.)
  tools/
    base.py              BaseTool ABC, ToolResult dataclass, ToolRegistry
    ingest_file.py       ingest_file tool
    list_datasets.py     list_datasets tool
    describe_table.py    describe_table tool
    query.py             query tool
    search.py            search tool
  validators/
    sql.py               SQLValidator — sqlglot parse + AST walk, rejects non-SELECT
    path.py              PathValidator — resolves path, checks against MCP_ALLOWED_DIRS
tests/
  test_sql_validator.py
  test_type_inferrer.py
  test_e2e.py            builds a real SQLiteStore against tmp_path; exercises tools end-to-end
```

---

## Architecture & Design Principles

### 1. OOP throughout — follow existing patterns
Every concept is a class. When adding new behaviour:
- **New file format** → new class under `BaseParser`, register in `ParserRegistry`
- **New tool** → new class under `BaseTool`, register in `ToolRegistry` in `server.py`
- **New validator** → pure class with no side effects, raises on bad input

### 2. Dependency injection — no globals, no singletons
Every collaborator is passed through `__init__`. `server.py` is the single composition root. Unit tests instantiate classes directly with fakes — no patching of module-level state needed.

### 3. Tool descriptions are LLM-facing
`description` strings on every tool tell the LLM *when* to call the tool and how to compose inputs (e.g. *"call describe_table first if you don't know the schema"*). Keep them imperative and precise. Error messages must also be LLM-recoverable — explain *what went wrong* and *what to do instead*.

### 4. SQL safety — never bypass sqlglot
All SQL from the LLM or user goes through `SQLValidator` before execution:
- Parsed by sqlglot (not regex)
- Rejected if not a single SELECT statement
- AST-walked for forbidden node types (DDL, DML, ATTACH, etc.)
- Table/column identifiers validated against `[A-Za-z_][A-Za-z0-9_]*` and always quoted

### 5. Path safety — always resolve before checking
`PathValidator` calls `Path.resolve()` before comparing against allowed dirs, defeating symlinks and `..` traversal. Never skip this for any tool that touches the filesystem.

### 6. Type inference — conservative by design
`TypeInferrer` samples up to 200 rows. A column gets INTEGER only if *every* non-empty value parses as int; REAL if every value is numeric; otherwise TEXT. **Do not coerce booleans to integers** — semantics matter.

### 7. Streaming ingest
Parsers `yield` rows; `DataIngestor` accumulates 1 000 rows then executes a batch INSERT inside a single transaction. This keeps memory flat for arbitrarily large files. Do not collect all rows into a list before inserting.

### 8. FTS5 is opt-in
The `search` tool's `enable` action creates the FTS5 virtual table for a specific (table, columns) pair. Auto-indexing everything on ingest doubles storage. Triggers keep the index in sync.

---

## Key Classes at a Glance

| Class | File | Responsibility |
|---|---|---|
| `BaseParser` | `src/parsers/base.py` | ABC — `parse(path) -> Iterator[dict]` |
| `ParserRegistry` | `src/parsers/registry.py` | `get(path) -> BaseParser` |
| `SQLiteStore` | `src/storage/sqlite_store.py` | owns `sqlite3.Connection`; composes sub-managers |
| `TypeInferrer` | `src/storage/types.py` | `infer(rows) -> list[ColumnSchema]` |
| `DataIngestor` | `src/storage/ingest.py` | streaming batched INSERT |
| `QueryExecutor` | `src/storage/query.py` | `execute(sql, params) -> list[dict]` |
| `SearchIndex` | `src/storage/search.py` | FTS5 enable/search |
| `SQLValidator` | `src/validators/sql.py` | `validate(sql)` — raises on anything not a safe SELECT |
| `PathValidator` | `src/validators/path.py` | `validate(path)` — raises if outside allowed dirs |
| `BaseTool` | `src/tools/base.py` | ABC — `name`, `description`, `run(**kwargs) -> ToolResult` |
| `ToolRegistry` | `src/tools/base.py` | maps tool name → tool instance for MCP dispatch |

---

## Adding a New Parser

1. Create `src/parsers/myformat.py` with a class inheriting `BaseParser`
2. Implement `parse(path: Path) -> Iterator[dict[str, Any]]`
3. Register it in `ParserRegistry.__init__` with the relevant extension(s)
4. Add unit tests in `tests/test_parsers.py` (or a new file)

## Adding a New Tool

1. Create `src/tools/mytool.py` with a class inheriting `BaseTool`
2. Set `name`, `description` (LLM-facing), and `input_schema` (JSON Schema dict)
3. Implement `run(**kwargs) -> ToolResult`
4. In `server.py`, instantiate and pass to `ToolRegistry`

---

## Testing

Framework: **pytest** (≥ 8.0)

```bash
python -m pytest tests/ -v          # all tests
python -m pytest tests/test_e2e.py  # end-to-end only
```

### Patterns
- **Unit tests**: instantiate the class under test with minimal fakes; inject collaborators through the constructor
- **E2E tests** (`test_e2e.py`): build a real `SQLiteStore` against `pytest`'s `tmp_path` fixture; exercise tools end-to-end without mocking storage
- Do not use `monkeypatch` to patch module-level state — dependency injection makes that unnecessary

---

## Branch & Git

- Development branch: `claude/test-agents-rbzfV`
- Main branch: `main`
- Push: `git push -u origin claude/test-agents-rbzfV`

---

## Security Invariants — Never Violate

1. Every SQL string from outside the process goes through `SQLValidator` before `execute()`
2. Every file path from outside the process goes through `PathValidator` before `open()`
3. Table/column names are always quoted (e.g. `"my_table"`) even after identifier validation
4. No module-level mutable state — makes it impossible to leak data between requests

---

## Dependencies

| Package | Why |
|---|---|
| `mcp >= 1.0` | MCP protocol (tool registration, stdio transport) |
| `sqlglot >= 23.0` | SQL parsing + AST walking for safe query validation |
| `pytest >= 8.0` | Testing (dev only) |

Python standard library: `sqlite3`, `csv`, `json`, `pathlib`, `os`, `typing`, `dataclasses`, `abc`, `re`
