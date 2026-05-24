import sqlite3
from dataclasses import dataclass


@dataclass
class DatasetMeta:
    table_name: str
    source_path: str
    row_count: int


class MetadataStore:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._init()

    def _init(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _datasets (
                table_name TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                ingested_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.commit()

    def register(self, table_name: str, source_path: str, row_count: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO _datasets (table_name, source_path, row_count) "
            "VALUES (?, ?, ?)",
            (table_name, source_path, row_count),
        )
        self._conn.commit()

    def deregister(self, table_name: str) -> None:
        self._conn.execute(
            "DELETE FROM _datasets WHERE table_name = ?", (table_name,)
        )
        self._conn.commit()

    def list_datasets(self) -> list[DatasetMeta]:
        rows = self._conn.execute(
            "SELECT table_name, source_path, row_count FROM _datasets ORDER BY table_name"
        ).fetchall()
        return [DatasetMeta(r[0], r[1], r[2]) for r in rows]

    def get(self, table_name: str) -> DatasetMeta | None:
        row = self._conn.execute(
            "SELECT table_name, source_path, row_count FROM _datasets WHERE table_name = ?",
            (table_name,),
        ).fetchone()
        return DatasetMeta(row[0], row[1], row[2]) if row else None
