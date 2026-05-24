import sqlite3
from typing import Any, Iterator

from .types import TableSchema
from ..exceptions import StorageError

_BATCH_SIZE = 1000


def _q(name: str) -> str:
    return f'"{name}"'


class DataIngestor:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def ingest(self, schema: TableSchema, rows: Iterator[dict[str, Any]]) -> int:
        col_names = [c.name for c in schema.columns]
        placeholders = ", ".join("?" * len(col_names))
        quoted_cols = ", ".join(_q(c) for c in col_names)
        sql = f"INSERT INTO {_q(schema.name)} ({quoted_cols}) VALUES ({placeholders})"

        total = 0
        batch: list[tuple] = []
        for row in rows:
            batch.append(tuple(row.get(c, None) for c in col_names))
            if len(batch) >= _BATCH_SIZE:
                self._flush(sql, batch)
                total += len(batch)
                batch = []

        if batch:
            self._flush(sql, batch)
            total += len(batch)

        return total

    def _flush(self, sql: str, batch: list[tuple]) -> None:
        try:
            with self._conn:
                self._conn.executemany(sql, batch)
        except sqlite3.Error as e:
            raise StorageError(f"Insert failed: {e}") from e
