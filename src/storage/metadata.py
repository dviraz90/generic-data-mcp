from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

_METADATA_TABLE = "_mcp_datasets"


@dataclass(frozen=True)
class DatasetInfo:
    table_name: str
    source_path: str
    row_count: int
    ingested_at: str


class MetadataStore:
    """Tracks which tables were ingested by generic-data-mcp, and from where.

    Backs the `list_datasets` tool. Kept separate from sqlite_master so
    internal/FTS tables never leak into the dataset listing.
    """

    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            f'''
            CREATE TABLE IF NOT EXISTS "{_METADATA_TABLE}" (
                table_name TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                ingested_at TEXT NOT NULL
            )
            '''
        )
        self._conn.commit()

    def record(self, table_name: str, source_path: str, row_count: int) -> None:
        ingested_at = datetime.now(UTC).isoformat()
        self._conn.execute(
            rf'''
            INSERT INTO "{_METADATA_TABLE}" (table_name, source_path, row_count, ingested_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(table_name) DO UPDATE SET
                source_path = excluded.source_path,
                row_count = excluded.row_count,
                ingested_at = excluded.ingested_at
            ''',
            (table_name, source_path, row_count, ingested_at),
        )
        self._conn.commit()

    def list_all(self) -> list[DatasetInfo]:
        cursor = self._conn.execute(
            f"SELECT table_name, source_path, row_count, ingested_at "
            f'FROM "{_METADATA_TABLE}" ORDER BY table_name'
        )
        return [DatasetInfo(*row) for row in cursor.fetchall()]
