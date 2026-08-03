from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.validators.sql import SQLValidator

_ROW_LIMIT = 1000


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


class QueryExecutor:
    """Executes a single read-only SELECT statement, capped at 1000 rows."""

    def __init__(self, connection: sqlite3.Connection, sql_validator: SQLValidator):
        self._conn = connection
        self._validator = sql_validator

    def execute(self, sql: str) -> QueryResult:
        self._validator.validate(sql)

        cursor = self._conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(_ROW_LIMIT + 1)
        truncated = len(rows) > _ROW_LIMIT
        if truncated:
            rows = rows[:_ROW_LIMIT]
        return QueryResult(columns=columns, rows=rows, truncated=truncated)
