from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from src.exceptions import QueryTimeoutError
from src.validators.sql import SQLValidator

_ROW_LIMIT = 1000
DEFAULT_TIMEOUT_SECONDS = 10.0

# SQLite calls the progress handler every N virtual-machine instructions. Small
# enough that an overrun is caught within milliseconds, large enough that the
# Python callback is negligible next to the query's own work.
_PROGRESS_INTERVAL = 10_000


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


class QueryExecutor:
    """Executes a single read-only SELECT statement, capped at 1000 rows and a time budget.

    The row cap bounds what is returned, not the work done: a valid SELECT such as
    an unbounded recursive CTE never produces a row and would run forever, holding
    the store's one shared connection. The deadline interrupts it instead.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        sql_validator: SQLValidator,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._conn = connection
        self._validator = sql_validator
        self._timeout = timeout_seconds

    def execute(self, sql: str) -> QueryResult:
        self._validator.validate(sql)

        deadline = time.monotonic() + self._timeout
        # A truthy return from the handler makes SQLite abort the statement with
        # OperationalError("interrupted"). It must also cover fetchmany, which is
        # where most of the stepping happens.
        self._conn.set_progress_handler(lambda: time.monotonic() > deadline, _PROGRESS_INTERVAL)
        try:
            cursor = self._conn.execute(sql)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(_ROW_LIMIT + 1)
        except sqlite3.OperationalError as e:
            if time.monotonic() <= deadline:
                raise
            raise QueryTimeoutError(
                f"Query stopped after {self._timeout:g}s. Narrow it with WHERE or LIMIT, "
                "make sure any recursive CTE has a terminating condition, and check table "
                "sizes with list_datasets before joining large tables."
            ) from e
        finally:
            self._conn.set_progress_handler(None, 0)

        truncated = len(rows) > _ROW_LIMIT
        if truncated:
            rows = rows[:_ROW_LIMIT]
        return QueryResult(columns=columns, rows=rows, truncated=truncated)
