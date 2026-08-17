from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.storage.ingest import DataIngestor
from src.storage.metadata import DatasetInfo, MetadataStore
from src.storage.query import QueryExecutor, QueryResult
from src.storage.search import SearchIndex
from src.storage.tables import TableManager
from src.storage.types import TableSchema, TypeInferrer
from src.validators.sql import SQLValidator


class SQLiteStore:
    """Composition root: wires the storage managers behind one façade.

    Every collaborator (TableManager, DataIngestor, QueryExecutor,
    SearchIndex, MetadataStore) is constructed here and shares one
    connection. Tools depend only on this façade, never on sqlite3 directly.
    """

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL;")
        self._connection.execute("PRAGMA busy_timeout=5000;")

        self.tables = TableManager(self._connection)
        self.metadata = MetadataStore(self._connection)
        self.ingestor = DataIngestor(self._connection, self.tables, self.metadata, TypeInferrer())
        self.query_executor = QueryExecutor(self._connection, SQLValidator())
        self.search_index = SearchIndex(self._connection, self.tables)

    def ingest(
        self, table_name: str, source_path: str, rows: Iterator[dict[str, str]]
    ) -> TableSchema:
        return self.ingestor.ingest(table_name, source_path, rows)

    def list_datasets(self) -> list[DatasetInfo]:
        return self.metadata.list_all()

    def describe_table(self, table_name: str) -> tuple[TableSchema, list[dict[str, Any]]]:
        schema = self.tables.get_schema(table_name)
        cursor = self._connection.execute(f'SELECT * FROM "{table_name}" LIMIT 5')
        columns = [d[0] for d in cursor.description]
        sample_rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return schema, sample_rows

    def query(self, sql: str) -> QueryResult:
        return self.query_executor.execute(sql)

    def enable_search(self, table_name: str, columns: list[str]) -> str:
        return self.search_index.enable(table_name, columns)

    def search(self, table_name: str, query: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.search_index.search(table_name, query, limit)

    def close(self) -> None:
        self._connection.close()
