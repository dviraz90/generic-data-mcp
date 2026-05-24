import csv
import json

import pytest

from src.parsers.registry import ParserRegistry
from src.storage.sqlite_store import SQLiteStore
from src.tools.describe_table import DescribeTableTool
from src.tools.ingest_file import IngestFileTool
from src.tools.list_datasets import ListDatasetsTool
from src.tools.query import QueryTool
from src.tools.search import SearchTool
from src.validators.path import PathValidator


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(tmp_path / "test.db")


@pytest.fixture
def path_validator(data_dir):
    return PathValidator([str(data_dir)])


@pytest.fixture
def sample_csv(data_dir):
    p = data_dir / "people.csv"
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "age", "city"])
        writer.writeheader()
        writer.writerows([
            {"name": "Alice", "age": "30", "city": "New York"},
            {"name": "Bob", "age": "25", "city": "London"},
            {"name": "Carol", "age": "35", "city": "New York"},
        ])
    return p


def test_ingest_and_query(store, path_validator, sample_csv):
    ingest = IngestFileTool(store, ParserRegistry(), path_validator)
    result = ingest.run(path=str(sample_csv), table_name="people")
    assert not result.is_error
    assert "3 rows" in result.content

    result = QueryTool(store).run(sql="SELECT * FROM people ORDER BY name")
    rows = json.loads(result.content)
    assert len(rows) == 3
    assert rows[0]["name"] == "Alice"


def test_list_datasets(store, path_validator, sample_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(sample_csv), table_name="people"
    )
    result = ListDatasetsTool(store).run()
    data = json.loads(result.content)
    assert any(d["table"] == "people" for d in data)


def test_describe_table(store, path_validator, sample_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(sample_csv), table_name="people"
    )
    result = DescribeTableTool(store).run(table_name="people")
    data = json.loads(result.content)
    assert "schema" in data
    assert "sample" in data
    col_names = [c["name"] for c in data["schema"]]
    assert "name" in col_names


def test_describe_missing_table(store):
    result = DescribeTableTool(store).run(table_name="nonexistent")
    assert result.is_error
    assert "not found" in result.content


def test_fts_search(store, path_validator, sample_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(sample_csv), table_name="people"
    )
    search = SearchTool(store)
    search.run(action="enable", table="people", columns=["city"])
    result = search.run(
        action="search", table="people", columns=["city"], query="New York"
    )
    rows = json.loads(result.content)
    assert len(rows) >= 1


def test_path_blocked(store, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    validator = PathValidator([str(allowed)])
    outside = tmp_path / "secret.csv"
    outside.write_text("a,b\n1,2")
    result = IngestFileTool(store, ParserRegistry(), validator).run(
        path=str(outside), table_name="secret"
    )
    assert result.is_error


def test_sql_injection_blocked(store, path_validator, sample_csv):
    IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(sample_csv), table_name="people"
    )
    result = QueryTool(store).run(sql="DROP TABLE people")
    assert result.is_error


def test_json_ingest(store, path_validator, data_dir):
    p = data_dir / "items.json"
    p.write_text(json.dumps([{"id": 1, "label": "foo"}, {"id": 2, "label": "bar"}]))
    result = IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(p), table_name="items"
    )
    assert not result.is_error
    rows = json.loads(QueryTool(store).run(sql="SELECT * FROM items").content)
    assert len(rows) == 2


def test_jsonl_ingest(store, path_validator, data_dir):
    p = data_dir / "log.jsonl"
    p.write_text('{"event": "login"}\n{"event": "logout"}\n')
    result = IngestFileTool(store, ParserRegistry(), path_validator).run(
        path=str(p), table_name="log"
    )
    assert not result.is_error
    rows = json.loads(QueryTool(store).run(sql="SELECT * FROM log").content)
    assert len(rows) == 2
