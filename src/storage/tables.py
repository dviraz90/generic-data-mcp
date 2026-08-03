from __future__ import annotations

import sqlite3

from src.exceptions import TableNotFoundError
from src.storage.types import ColumnSchema, SQLType, TableSchema
from src.validators.sql import validate_identifier


class TableManager:
    """Creates and inspects data tables in SQLite."""

    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection

    def create_table(self, schema: TableSchema) -> None:
        table_name = validate_identifier(schema.name)
        column_defs = ", ".join(
            f'"{validate_identifier(c.name)}" {c.sql_type.value}' for c in schema.columns
        )
        self._conn.execute(f'CREATE TABLE "{table_name}" ({column_defs})')
        self._conn.commit()

    def table_exists(self, table_name: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def get_schema(self, table_name: str) -> TableSchema:
        validate_identifier(table_name)
        if not self.table_exists(table_name):
            raise TableNotFoundError(
                f"Table '{table_name}' does not exist. Use list_datasets to see available tables."
            )
        cursor = self._conn.execute(f'PRAGMA table_info("{table_name}")')
        columns = tuple(
            ColumnSchema(name=row[1], sql_type=SQLType(row[2])) for row in cursor.fetchall()
        )
        return TableSchema(name=table_name, columns=columns)
