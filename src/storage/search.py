import re
import sqlite3

from ..exceptions import StorageError

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _q(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise StorageError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def _fts_name(table: str, columns: list[str]) -> str:
    return f"_fts_{table}_{'_'.join(columns)}"


class SearchIndex:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def enable(self, table: str, columns: list[str]) -> None:
        fts = _fts_name(table, columns)
        col_list = ", ".join(_q(c) for c in columns)
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {_q(fts)} "
            f"USING fts5(content={_q(table)}, {col_list})"
        )
        self._conn.execute(f"INSERT INTO {_q(fts)}({_q(fts)}) VALUES('rebuild')")
        self._install_triggers(table, columns, fts)
        self._conn.commit()

    def search(
        self, table: str, columns: list[str], query: str, limit: int = 20
    ) -> list[dict]:
        fts = _fts_name(table, columns)
        if not self._exists(fts):
            raise StorageError(
                f"Full-text search not enabled for table '{table}' columns {columns}. "
                "Call search with action='enable' first."
            )
        cur = self._conn.execute(
            f"SELECT *, rank FROM {_q(fts)} WHERE {_q(fts)} MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def is_enabled(self, table: str, columns: list[str]) -> bool:
        return self._exists(_fts_name(table, columns))

    def _exists(self, name: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return row is not None

    def _install_triggers(self, table: str, columns: list[str], fts: str) -> None:
        col_list = ", ".join(_q(c) for c in columns)
        new_vals = ", ".join(f"new.{_q(c)}" for c in columns)
        self._conn.executescript(f"""
            CREATE TRIGGER IF NOT EXISTS "_fts_ai_{table}"
            AFTER INSERT ON {_q(table)} BEGIN
              INSERT INTO {_q(fts)}(rowid, {col_list}) VALUES (new.rowid, {new_vals});
            END;

            CREATE TRIGGER IF NOT EXISTS "_fts_ad_{table}"
            AFTER DELETE ON {_q(table)} BEGIN
              INSERT INTO {_q(fts)}({_q(fts)}, rowid) VALUES('delete', old.rowid);
            END;

            CREATE TRIGGER IF NOT EXISTS "_fts_au_{table}"
            AFTER UPDATE ON {_q(table)} BEGIN
              INSERT INTO {_q(fts)}({_q(fts)}, rowid) VALUES('delete', old.rowid);
              INSERT INTO {_q(fts)}(rowid, {col_list}) VALUES (new.rowid, {new_vals});
            END;
        """)
