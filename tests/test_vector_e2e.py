import csv
import json

import pytest

from src.embeddings.base import BaseEmbedder
from src.parsers.registry import ParserRegistry
from src.storage.sqlite_store import SQLiteStore
from src.tools.ingest_file import IngestFileTool
from src.tools.vector_search import VectorSearchTool
from src.validators.path import PathValidator


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
def data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(tmp_path / "test.db", StubEmbedder())


@pytest.fixture
def path_validator(data_dir):
    return PathValidator([str(data_dir)])


@pytest.fixture
def products_csv(data_dir):
    p = data_dir / "products.csv"
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "description"])
        writer.writeheader()
        writer.writerows([
            {"id": "1", "description": "red apple"},
            {"id": "2", "description": "yellow banana"},
            {"id": "3", "description": "green lime"},
        ])
    return p


def test_enable_and_search(store, path_validator, products_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(products_csv), table_name="products"
    )
    tool = VectorSearchTool(store)

    enable_result = tool.run(action="enable", table="products", column="description")
    assert not enable_result.is_error
    assert "3 rows" in enable_result.content

    search_result = tool.run(
        action="search", table="products", column="description",
        query="tropical fruit", k=2,
    )
    assert not search_result.is_error
    rows = json.loads(search_result.content)
    assert isinstance(rows, list)
    assert len(rows) <= 2
    if rows:
        assert "_distance" in rows[0]


def test_list_action(store, path_validator, products_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(products_csv), table_name="products"
    )
    tool = VectorSearchTool(store)
    tool.run(action="enable", table="products", column="description")
    result = tool.run(action="list")
    assert not result.is_error
    data = json.loads(result.content)
    assert any(d["table"] == "products" for d in data)


def test_not_configured(tmp_path):
    store = SQLiteStore(tmp_path / "noembed.db", embedder=None)
    tool = VectorSearchTool(store)
    result = tool.run(action="enable", table="t", column="c")
    assert result.is_error
    assert "not configured" in result.content


def test_search_before_enable(store, path_validator, products_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(products_csv), table_name="products"
    )
    tool = VectorSearchTool(store)
    result = tool.run(
        action="search", table="products", column="description", query="apple"
    )
    assert result.is_error
    assert "enable" in result.content
