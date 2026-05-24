import sqlite3
from pathlib import Path

from .ingest import DataIngestor
from .metadata import MetadataStore
from .query import QueryExecutor
from .search import SearchIndex
from .tables import TableManager
from .types import TypeInferrer
from .vector import VectorIndex
from ..embeddings.base import BaseEmbedder
from ..validators.sql import SQLValidator


class SQLiteStore:
    def __init__(
        self, db_path: str | Path, embedder: BaseEmbedder | None = None
    ):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)

        validator = SQLValidator()
        self.tables = TableManager(self._conn)
        self.ingestor = DataIngestor(self._conn)
        self.query = QueryExecutor(self._conn, validator)
        self.search = SearchIndex(self._conn)
        self.metadata = MetadataStore(self._conn)
        self.types = TypeInferrer()
        self.vector: VectorIndex | None = (
            VectorIndex(self._conn, embedder) if embedder is not None else None
        )

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()
