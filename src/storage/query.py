from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from src.exceptions import QueryTimeoutError, SQLValidationError
from src.validators.sql import SQLValidator

_ROW_LIMIT = 1000
# SQLite VM instructions between progress-handler calls: small enough to stop a
# runaway query promptly, large enough that the callback overhead is negligible.
_PROGRESS_INTERVAL = 10_000


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


class QueryExecutor:
    """Executes a single read-only SELECT statement, capped at 1000 rows.

    Each query also has a wall-clock budget and a per-value size cap, so one
    runaway statement (an unbounded recursive CTE, ``randomblob(1e9)``) cannot
    freeze or exhaust the process every transport shares.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        sql_validator: SQLValidator,
        timeout_seconds: float = 5.0,
        max_value_bytes: int = 10_000_000,
    ):
        self._conn = connection
        self._validator = sql_validator
        self._timeout = timeout_seconds
        self._conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, max_value_bytes)

    def execute(self, sql: str) -> QueryResult:
        self._validator.validate(sql)

        deadline = time.monotonic() + self._timeout
        # A non-zero return aborts the running statement with "interrupted".
        self._conn.set_progress_handler(
            lambda: 1 if time.monotonic() > deadline else 0, _PROGRESS_INTERVAL
        )
        try:
            cursor = self._conn.execute(sql)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(_ROW_LIMIT + 1)
        except sqlite3.DatabaseError as e:
            # "not authorized" for denied statements/functions, "...is prohibited"
            # when the authorizer denies reading a table such as pragma_*.
            if "not authorized" in str(e) or "is prohibited" in str(e):
                raise SQLValidationError(
                    "That function or table is not available in read-only queries. "
                    "Use plain SELECTs over the loaded tables; call describe_table "
                    "for column names and types."
                ) from e
            if "interrupted" in str(e):
                raise QueryTimeoutError(
                    f"Query exceeded the {self._timeout:g}s limit. Add a WHERE clause or "
                    "LIMIT, or bound any recursive CTE."
                ) from e
            if "too big" in str(e):
                raise QueryTimeoutError(
                    "Query produced a value larger than the size limit. Select fewer or "
                    "smaller columns, or use substr() on large text."
                ) from e
            raise
        finally:
            self._conn.set_progress_handler(None, 0)
        truncated = len(rows) > _ROW_LIMIT
        if truncated:
            rows = rows[:_ROW_LIMIT]
        return QueryResult(columns=columns, rows=rows, truncated=truncated)
