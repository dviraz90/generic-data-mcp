from __future__ import annotations

import sqlite3

from src.exceptions import GenericDataMCPError
from src.storage.tables import TableManager
from src.validators.sql import validate_identifier

_FTS_SUFFIX = "_fts"


class SearchIndex:
    """Opt-in FTS5 full-text search over a (table, columns) pair.

    Nothing is indexed on ingest. The `search` tool's `enable` action creates
    an FTS5 external-content table plus triggers so the index stays in sync
    with the source table on insert/update/delete.
    """

    def __init__(self, connection: sqlite3.Connection, table_manager: TableManager):
        self._conn = connection
        self._tables = table_manager

    def _fts_table(self, table_name: str) -> str:
        return f"{table_name}{_FTS_SUFFIX}"

    def is_enabled(self, table_name: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (self._fts_table(table_name),),
        )
        return cursor.fetchone() is not None

    def enable(self, table_name: str, columns: list[str]) -> str:
        validate_identifier(table_name)
        schema = self._tables.get_schema(table_name)  # raises if table is missing
        valid_columns = set(schema.column_names())

        for column in columns:
            validate_identifier(column)
            if column not in valid_columns:
                raise GenericDataMCPError(
                    f"Column '{column}' not found on '{table_name}'. "
                    f"Available columns: {', '.join(schema.column_names())}."
                )

        if self.is_enabled(table_name):
            raise GenericDataMCPError(
                f"Search is already enabled on '{table_name}'. Use the 'search' action to query it."
            )

        fts_table = self._fts_table(table_name)
        column_list = ", ".join(f'"{c}"' for c in columns)
        new_values = ", ".join(f'new."{c}"' for c in columns)
        old_values = ", ".join(f'old."{c}"' for c in columns)

        self._conn.execute(
            f'''
            CREATE VIRTUAL TABLE "{fts_table}" USING fts5(
                {column_list}, content="{table_name}", content_rowid="rowid"
            )
            '''
        )
        self._conn.execute(
            f'INSERT INTO "{fts_table}"(rowid, {column_list}) '
            f'SELECT rowid, {column_list} FROM "{table_name}"'
        )
        self._conn.execute(
            f'''
            CREATE TRIGGER "{table_name}_ai" AFTER INSERT ON "{table_name}" BEGIN
                INSERT INTO "{fts_table}"(rowid, {column_list}) VALUES (new.rowid, {new_values});
            END
            '''
        )
        self._conn.execute(
            f'''
            CREATE TRIGGER "{table_name}_ad" AFTER DELETE ON "{table_name}" BEGIN
                INSERT INTO "{fts_table}"("{fts_table}", rowid, {column_list})
                VALUES ('delete', old.rowid, {old_values});
            END
            '''
        )
        self._conn.execute(
            f'''
            CREATE TRIGGER "{table_name}_au" AFTER UPDATE ON "{table_name}" BEGIN
                INSERT INTO "{fts_table}"("{fts_table}", rowid, {column_list})
                VALUES ('delete', old.rowid, {old_values});
                INSERT INTO "{fts_table}"(rowid, {column_list}) VALUES (new.rowid, {new_values});
            END
            '''
        )
        self._conn.commit()
        return fts_table

    def search(self, table_name: str, query: str, limit: int = 50) -> list[dict]:
        validate_identifier(table_name)
        if not self.is_enabled(table_name):
            raise GenericDataMCPError(
                f"Search is not enabled on '{table_name}'. "
                "Call the search tool's 'enable' action first with the columns to index."
            )

        fts_table = self._fts_table(table_name)
        cursor = self._conn.execute(
            f'''
            SELECT "{table_name}".*
            FROM "{fts_table}"
            JOIN "{table_name}" ON "{table_name}".rowid = "{fts_table}".rowid
            WHERE "{fts_table}" MATCH ?
            ORDER BY rank
            LIMIT ?
            ''',
            (query, limit),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
