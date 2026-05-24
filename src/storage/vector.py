import json
import re
import sqlite3

from ..embeddings.base import BaseEmbedder
from ..exceptions import StorageError

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_EMBED_BATCH = 100


def _q(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise StorageError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def _vec_table(table: str, column: str) -> str:
    return f"_vec_{table}_{column}"


class VectorIndex:
    def __init__(self, conn: sqlite3.Connection, embedder: BaseEmbedder):
        self._conn = conn
        self._embedder = embedder
        self._vec_loaded = False
        self._init_meta()
        self._try_load_vec()

    def _init_meta(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _vec_meta (
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                dim INTEGER NOT NULL,
                model TEXT NOT NULL,
                PRIMARY KEY (table_name, column_name)
            )
        """)
        self._conn.commit()

    def _try_load_vec(self) -> None:
        try:
            import sqlite_vec  # noqa: F401
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._vec_loaded = True
        except Exception:
            self._vec_loaded = False

    def _require_vec(self) -> None:
        if not self._vec_loaded:
            raise StorageError(
                "sqlite-vec extension not available. "
                "Install it with: pip install sqlite-vec"
            )

    def enable(self, table: str, column: str) -> int:
        self._require_vec()
        cur = self._conn.execute(
            f"SELECT rowid, {_q(column)} FROM {_q(table)}"
        )
        rows = cur.fetchall()
        if not rows:
            raise StorageError(f"Table '{table}' is empty; nothing to index.")

        rowids = [r[0] for r in rows]
        texts = [str(r[1]) if r[1] is not None else "" for r in rows]

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            all_vectors.extend(self._embedder.embed(texts[i : i + _EMBED_BATCH]))

        if not all_vectors:
            raise StorageError("Embedder returned no vectors.")

        dim = len(all_vectors[0])
        vec_tbl = _vec_table(table, column)

        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {_q(vec_tbl)} "
            f"USING vec0(rowid INTEGER PRIMARY KEY, embedding float[{dim}])"
        )

        with self._conn:
            self._conn.executemany(
                f"INSERT OR REPLACE INTO {_q(vec_tbl)}(rowid, embedding) VALUES (?, ?)",
                [(rid, json.dumps(vec)) for rid, vec in zip(rowids, all_vectors)],
            )

        self._conn.execute(
            "INSERT OR REPLACE INTO _vec_meta (table_name, column_name, dim, model) "
            "VALUES (?, ?, ?, ?)",
            (table, column, dim, self._embedder.model_name),
        )
        self._conn.commit()
        return len(rowids)

    def search(self, table: str, column: str, query: str, k: int = 10) -> list[dict]:
        self._require_vec()
        if not self.is_enabled(table, column):
            raise StorageError(
                f"Vector search not enabled for table '{table}' column '{column}'. "
                "Call vector_search with action='enable' first."
            )

        meta = self._get_meta(table, column)
        query_vec = self._embedder.embed([query])[0]

        if len(query_vec) != meta["dim"]:
            raise StorageError(
                f"Embedding dimension mismatch: index has dim={meta['dim']} but "
                f"current model produced dim={len(query_vec)}. "
                "Re-enable the index with the current model."
            )

        vec_tbl = _vec_table(table, column)
        cur = self._conn.execute(
            f"SELECT v.rowid, v.distance FROM {_q(vec_tbl)} v "
            f"WHERE v.embedding MATCH ? AND k = ?",
            (json.dumps(query_vec), k),
        )
        hits = cur.fetchall()
        if not hits:
            return []

        rowids = [h[0] for h in hits]
        distances = {h[0]: h[1] for h in hits}

        placeholders = ",".join("?" * len(rowids))
        cur2 = self._conn.execute(
            f"SELECT rowid, * FROM {_q(table)} WHERE rowid IN ({placeholders})",
            rowids,
        )
        cols = [d[0] for d in cur2.description]
        result_map = {r[0]: dict(zip(cols, r)) for r in cur2.fetchall()}

        return [
            {**result_map[rid], "_distance": distances[rid]}
            for rid in rowids
            if rid in result_map
        ]

    def is_enabled(self, table: str, column: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM _vec_meta WHERE table_name=? AND column_name=?",
            (table, column),
        ).fetchone()
        return row is not None

    def list_indexes(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT table_name, column_name, dim, model FROM _vec_meta "
            "ORDER BY table_name, column_name"
        ).fetchall()
        return [
            {"table": r[0], "column": r[1], "dim": r[2], "model": r[3]}
            for r in rows
        ]

    def _get_meta(self, table: str, column: str) -> dict:
        row = self._conn.execute(
            "SELECT dim, model FROM _vec_meta WHERE table_name=? AND column_name=?",
            (table, column),
        ).fetchone()
        return {"dim": row[0], "model": row[1]} if row else {}
