import re
import sqlite3

from .types import TableSchema
from ..exceptions import StorageError

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _q(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise StorageError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


class TableManager:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(self, schema: TableSchema) -> None:
        col_defs = ", ".join(
            f"{_q(c.name)} {c.sql_type.value}" for c in schema.columns
        )
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_q(schema.name)} ({col_defs})"
        )
        self._conn.commit()

    def drop(self, table: str) -> None:
        self._conn.execute(f"DROP TABLE IF EXISTS {_q(table)}")
        self._conn.commit()

    def list_tables(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_%' ESCAPE '\\'"
        ).fetchall()
        return [r[0] for r in rows]

    def table_exists(self, table: str) -> bool:
        return table in self.list_tables()

    def get_schema(self, table: str) -> list[dict]:
        rows = self._conn.execute(f"PRAGMA table_info({_q(table)})").fetchall()
        return [{"name": r[1], "type": r[2]} for r in rows]
