# Security Hardening Plan — generic-data-mcp

> On approval: first save this plan verbatim to `.claude/plans/security.md` in the repo
> (the location the user asked for), then implement the features in order, one commit each,
> on branch `ccr-1437c80a-ehma35`.

## Context

A security check of the project (all findings reproduced in a live session) found two high,
two medium and several low-severity issues. The core boundaries (PathValidator, the sqlglot
SQL validator, identifier validation, Docker hardening) held up. The gaps are in the local
upload GUI and in what a "read-only" SELECT can still reach in SQLite. The goal is to close
every finding, highest severity first. Each fix is a self-contained feature with its own
regression tests, and every change keeps the project's rules: constructor-injected
collaborators, no globals, and error messages written for LLM recovery.

Features are ordered by severity, which is also the implementation order. F2 must land before
F3, because F3 reuses the read-only connection F2 introduces.

---

## F1 — Web UI request-origin guard (HIGH, finding #1)

**Problem:** any website can POST uploads to `127.0.0.1:8765` (a multipart form needs no
CORS preflight), and DNS rebinding lets a foreign page read `/api/datasets` and `/api/query`.
The server checks neither `Host` nor `Origin`.

**Change:** `src/webui/server.py`, inside `create_app`:
- Add an `@app.before_request` guard:
  - Reject (403 JSON `{"success": false, "error": ...}`) any request whose `request.host`
    hostname is not in `{"127.0.0.1", "localhost", "[::1]"}`. This defeats DNS rebinding.
  - For every non-GET method, require an `Origin` header equal to `f"http://{request.host}"`.
    The browser always sends `Origin` on fetch POSTs, so the GUI's own requests pass and
    cross-site forms fail.
- Add an `@app.after_request` hook that sets `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer` (CSP is added in F4).

**Tests:** `tests/test_webui.py`. Upload with a foreign Origin returns 403; upload with no
Origin returns 403; GET with `Host: evil.example` returns 403; the same-origin upload still
succeeds. Update the existing upload/query tests to send
`headers={"Origin": "http://localhost"}`, since the Flask test client's default host is
`localhost`.

## F2 — Read-only, authorizer-guarded query connection (HIGH, findings #2 and #6)

**Problem:** `SELECT fts3_tokenizer('simple')` leaks a native pointer, and the two-argument
form overwrites the tokenizer's function pointer. The query runs on the same read-write
connection used for ingest, so the validator is the only barrier against writes.

**Change:**
- New `src/storage/authorizer.py`: `QueryAuthorizer`, a callable passed to
  `sqlite3.Connection.set_authorizer`.
  - Allow only `SQLITE_SELECT`, `SQLITE_READ`, `SQLITE_FUNCTION` and `SQLITE_RECURSIVE`;
    return `SQLITE_DENY` for everything else (writes, ATTACH, PRAGMA, transactions).
  - For `SQLITE_FUNCTION`, deny a lower-cased denylist: `fts3_tokenizer`, `load_extension`,
    `readfile`, `writefile`, `edit`, `fts5_source_id`.
  - For `SQLITE_READ`, deny table names starting with `pragma_`. This closes the path/
    compile-option leak from finding #10.
- `src/storage/sqlite_store.py`, `SQLiteStore.__init__`: after the main connection sets up
  WAL, open a second connection,
  `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)`, with
  `busy_timeout` and the authorizer installed. Pass it to `QueryExecutor` instead of the main
  connection. Close it in `close()`.
- `src/storage/query.py`, `QueryExecutor.execute`: catch `sqlite3.DatabaseError` whose
  message contains "not authorized" and re-raise it as `SQLValidationError` (from
  `src/exceptions/__init__.py`), with a recovery-oriented message ("This function/table is
  not available in read-only queries.").

**Tests:** new `tests/test_query_authorizer.py`, built on a real `SQLiteStore(tmp_path)` like
`test_e2e.py`:
- `fts3_tokenizer` with one and with two arguments, `load_extension`, and
  `SELECT * FROM pragma_database_list` all fail with a `SQLValidationError` message.
- A normal SELECT, a JOIN, and a recursive CTE with a LIMIT still work.
- Rows ingested after the read connection opens are visible to it (checks WAL visibility).

Also add the new cases to `evals/corpus/sql_cases.json`.

## F3 — Query cost limits (MEDIUM, finding #3)

**Problem:** an unbounded recursive CTE never finishes and freezes both transports; a
`randomblob(1e8)` query allocates about 100 MB per call.

**Change:** `src/storage/query.py`. `QueryExecutor` gains constructor params
`timeout_seconds: float = 5.0` and `max_value_bytes: int = 10_000_000`.
- In `__init__`, call
  `conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, max_value_bytes)` on the read-only connection
  (F2).
- In `execute()`, install `set_progress_handler(handler, 10_000)`. The handler returns
  non-zero once `time.monotonic()` passes the deadline. Remove the handler in a `finally`.
- Map `OperationalError("interrupted")` to a new `QueryTimeoutError(GenericDataMCPError)` in
  `src/exceptions/__init__.py`: "Query exceeded the 5s limit — add a WHERE/LIMIT or simplify
  recursive CTEs." Map "string or blob too big" to a similar message.

**Tests:** the infinite recursive CTE returns a timeout failure within about 6s (use a 0.5s
timeout in the test); `randomblob(20_000_000)` fails cleanly; normal queries are unaffected.

## F4 — Stored-XSS fix and Content-Security-Policy (MEDIUM, finding #4)

**Problem:** `src/webui/static/index.html`, in `loadDatasets()` and `describe()`, builds
markup with `innerHTML` from `d.source_path` and `d.table_name`. A file in an allowed folder
with an HTML filename, ingested via MCP, runs its script on the GUI's page.

**Change:**
- Rebuild those two snippets with `createElement` and `textContent`, reusing the pattern
  `showMsg`/`renderTable` already use. Replace the "No datasets" `innerHTML` literal the same
  way.
- Move the inline `<script>` and `<style>` into `static/app.js` and `static/app.css`, served
  through the existing `send_from_directory(_STATIC_DIR, ...)` route pattern (add a
  `/static/<path>` route). The `package-data` glob `static/*` already covers the new files.
- In the F1 `after_request` hook, add
  `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'; object-src 'none'`.

**Tests:** the webui test asserts the CSP header is present; a test asserts `index.html`
contains no inline `<script>` body, i.e. no `innerHTML =` with string concatenation (a simple
regex). Do a manual Playwright check in Verification.

## F5 — Upload file handling (LOW, finding #5)

**Change:** `src/webui/server.py`, `upload()`:
- If `upload_dir / filename` exists, save as `f"{stem}-{uuid4().hex[:8]}{suffix}"`. Never
  overwrite.
- If the `ingest_file` result is a failure, `unlink(missing_ok=True)` the saved file, so
  failed uploads don't pile up in the allowed directory.

**Tests:** two uploads with the same name produce two files and the first file's content is
unchanged; a failed ingest (e.g. a table-name collision) leaves no file behind.

## F6 — Parser and tool resource limits (LOW, finding #7)

**Change:**
- `src/tools/search.py`: validate `limit` as an `int` and clamp it to 1–1000, with a
  recovery message for non-integers.
- `src/parsers/json_parsers.py`, `JSONParser`: refuse files above a constructor-injected
  `max_bytes` (default 100 MB) with a message suggesting JSONL, which streams.
- `src/parsers/xlsx.py`: before `openpyxl.load_workbook`, sum `zipfile.ZipFile(path).infolist()`
  `file_size` values. Refuse above a constructor-injected cap (default 1 GB uncompressed) or
  when the compression ratio exceeds 100×. Raise `ParseError`.
- `pyproject.toml`: add `defusedxml>=0.7` to the `[ui]` extra; openpyxl uses it
  automatically.

**Tests:** extend `tests/test_xlsx_parser.py` with a crafted high-ratio zip; add a JSON
size-cap test and a search-limit clamp test.

## F7 — Serialize writes on the shared connection (LOW, finding #8)

**Change:** `src/storage/sqlite_store.py`. Add `self._write_lock = threading.RLock()` and take
it in the façade methods that use the main connection: `ingest`, `enable_search`, `search`
and `describe_table`. The query path already has its own connection (F2), so long SELECTs
don't block ingest. This keeps the fix transport-agnostic; there are no webui-specific locks.

**Tests:** a threaded test runs two concurrent ingests of different tables via
`ThreadPoolExecutor`. Both succeed and the row counts are correct.

## F8 — Supply chain and deployment hardening (LOW, findings #9 and #10)

**Change:**
- `.github/workflows/ci.yml`:
  - Add a top-level `permissions: contents: read`.
  - Pin `actions/checkout`, `setup-python` and `setup-buildx-action` to commit SHAs, keeping
    the version in a trailing comment.
  - Add a `pip-audit` step after installing.
- `Dockerfile`: pin `FROM python:3.11-slim@sha256:<digest>`, using the digest resolved at
  implementation time. If the registry is unreachable from the session, leave the existing
  comment and flag it.
- Read-only data mount, since the server only reads `/data`:
  - `docker-compose.yml`: `./data:/data:ro`.
  - README's client-config example: `:/data:ro`.
  - `scripts/install_claude_desktop_config.py`, `build_entry`: `f"{allowed_dirs}:/data:ro"`.
- `CLAUDE.md`: document the new guard (F1), the read-only query connection and limits
  (F2/F3), and the constructor defaults (F6).

**Tests:** existing tests plus `docker build` in CI. Run the install script's `--dry-run` to
check the `:ro` output.

---

## Critical files

- `src/webui/server.py`, `src/webui/static/index.html` (+ new `app.js`, `app.css`): F1, F4, F5
- `src/storage/sqlite_store.py`, `src/storage/query.py`, new `src/storage/authorizer.py`: F2, F3, F7
- `src/exceptions/__init__.py`: new `QueryTimeoutError`
- `src/tools/search.py`, `src/parsers/json_parsers.py`, `src/parsers/xlsx.py`, `pyproject.toml`: F6
- `.github/workflows/ci.yml`, `Dockerfile`, `docker-compose.yml`, `scripts/install_claude_desktop_config.py`, `README.md`, `CLAUDE.md`: F8
- Tests: `tests/test_webui.py`, new `tests/test_query_authorizer.py`, `tests/test_xlsx_parser.py`, `tests/test_e2e.py`, `evals/corpus/sql_cases.json`

## Verification

1. `python -m pytest tests/ -v` and `python -m evals.run` pass after every feature commit.
2. Re-run the original attack scripts in `/tmp/claude-0/probe/`. Each must now fail:
   - `probe.py`: `fts3_tokenizer`, `pragma_database_list`, the recursive CTE and
     `randomblob` are all blocked.
   - `web.py`: the foreign-Origin upload and the foreign-Host read are 403; the same-name
     upload doesn't overwrite.
3. Launch `generic-data-mcp-ui`. With Playwright:
   - Upload a CSV, browse it and run a query; the GUI still works with CSP on.
   - Ingest (via the registry) a file named `<img src=x onerror=alert(1)>.csv`; the dataset
     list shows the name as text and no dialog fires.
4. Start the MCP server over stdio and send an `initialize` request plus a `tools/call` for
   `query`; it responds normally.
5. `pip-audit` is clean; `bandit -r src` shows no new findings.
