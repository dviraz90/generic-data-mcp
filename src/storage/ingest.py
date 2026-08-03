from __future__ import annotations

import itertools
import sqlite3
from typing import Iterator

from src.exceptions import GenericDataMCPError
from src.storage.metadata import MetadataStore
from src.storage.tables import TableManager
from src.storage.types import TableSchema, TypeInferrer
from src.validators.sql import validate_identifier

_BATCH_SIZE = 1000


class DataIngestor:
    """Streams parsed rows into a new SQLite table, batched in one transaction.

    Parsers yield rows lazily, so files larger than RAM work fine: only the
    first `TypeInferrer.SAMPLE_SIZE` rows are buffered (to infer the schema)
    before the rest streams straight through in fixed-size batches.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        table_manager: TableManager,
        metadata_store: MetadataStore,
        type_inferrer: TypeInferrer,
    ):
        self._conn = connection
        self._tables = table_manager
        self._metadata = metadata_store
        self._inferrer = type_inferrer

    def ingest(
        self, table_name: str, source_path: str, rows: Iterator[dict[str, str]]
    ) -> TableSchema:
        validate_identifier(table_name)

        if self._tables.table_exists(table_name):
            raise GenericDataMCPError(
                f"Table '{table_name}' already exists. Choose a different table_name."
            )

        sample_rows = list(itertools.islice(rows, self._inferrer.SAMPLE_SIZE))
        if not sample_rows:
            raise GenericDataMCPError(f"'{source_path}' contains no rows to ingest.")

        column_order = list(sample_rows[0].keys())
        inferred = self._inferrer.infer(sample_rows, column_order)
        schema = TableSchema(name=table_name, columns=inferred.columns)

        self._tables.create_table(schema)

        quoted_columns = ", ".join(f'"{c}"' for c in column_order)
        placeholders = ", ".join("?" for _ in column_order)
        insert_sql = f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'

        row_count = 0
        try:
            for batch in self._batched(itertools.chain(sample_rows, rows), _BATCH_SIZE):
                values = [tuple(row.get(col, "") for col in column_order) for row in batch]
                self._conn.executemany(insert_sql, values)
                row_count += len(values)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            self._conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            self._conn.commit()
            raise

        self._metadata.record(table_name, source_path, row_count)
        return schema

    @staticmethod
    def _batched(iterator: Iterator[dict[str, str]], size: int) -> Iterator[list[dict[str, str]]]:
        while True:
            batch = list(itertools.islice(iterator, size))
            if not batch:
                return
            yield batch
