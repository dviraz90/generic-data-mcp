import sqlite3

from ..exceptions import StorageError
from ..validators.sql import SQLValidator

_ROW_LIMIT = 1000


class QueryExecutor:
    def __init__(self, conn: sqlite3.Connection, validator: SQLValidator):
        self._conn = conn
        self._validator = validator

    def execute(self, sql: str) -> list[dict]:
        self._validator.validate(sql)
        try:
            cur = self._conn.execute(sql)
            rows = cur.fetchmany(_ROW_LIMIT)
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(
                f"Query failed: {e}. Check your SQL and try again."
            ) from e
