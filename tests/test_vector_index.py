import pytest

from src.embeddings.base import BaseEmbedder
from src.exceptions import StorageError
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector import VectorIndex


class StubEmbedder(BaseEmbedder):
    @property
    def model_name(self) -> str:
        return "stub-4d"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(abs(hash(t)) % 1000) / 1000.0, 0.5, 0.1, 0.9]
            for t in texts
        ]


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(tmp_path / "test.db")


@pytest.fixture
def vector_index(store):
    return VectorIndex(store.conn, StubEmbedder())


def _seed(store: SQLiteStore) -> None:
    store.conn.execute(
        "CREATE TABLE IF NOT EXISTS fruits (name TEXT, description TEXT)"
    )
    store.conn.executemany(
        "INSERT INTO fruits (name, description) VALUES (?, ?)",
        [
            ("apple", "red crunchy fruit"),
            ("banana", "yellow tropical fruit"),
            ("cherry", "small red stone fruit"),
        ],
    )
    store.conn.commit()


def test_enable_creates_meta_entry(store, vector_index):
    _seed(store)
    count = vector_index.enable("fruits", "description")
    assert count == 3
    assert vector_index.is_enabled("fruits", "description")


def test_enable_returns_row_count(store, vector_index):
    _seed(store)
    assert vector_index.enable("fruits", "description") == 3


def test_search_before_enable_raises(store, vector_index):
    _seed(store)
    with pytest.raises(StorageError, match="not enabled"):
        vector_index.search("fruits", "description", "sweet fruit")


def test_list_indexes_after_enable(store, vector_index):
    _seed(store)
    vector_index.enable("fruits", "description")
    indexes = vector_index.list_indexes()
    assert len(indexes) == 1
    assert indexes[0]["table"] == "fruits"
    assert indexes[0]["column"] == "description"
    assert indexes[0]["model"] == "stub-4d"


def test_list_indexes_empty(store, vector_index):
    assert vector_index.list_indexes() == []


def test_empty_table_raises(store, vector_index):
    store.conn.execute("CREATE TABLE empty_tbl (val TEXT)")
    store.conn.commit()
    with pytest.raises(StorageError, match="empty"):
        vector_index.enable("empty_tbl", "val")
