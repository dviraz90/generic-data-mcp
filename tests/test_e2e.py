import pytest

from src.parsers.registry import ParserRegistry
from src.storage.sqlite_store import SQLiteStore
from src.tools import (
    DescribeTableTool,
    IngestFileTool,
    ListDatasetsTool,
    QueryTool,
    SearchTool,
    ToolRegistry,
)
from src.validators.path import PathValidator


@pytest.fixture
def workspace(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "orders.csv"
    csv_path.write_text(
        "id,customer,amount,note\n"
        "1,Alice,10.50,fast shipping please\n"
        "2,Bob,20,leave at the door\n"
        "3,Carol,15.25,call before delivery\n"
    )

    store = SQLiteStore(tmp_path / "store.db")
    path_validator = PathValidator((data_dir,))
    registry = ToolRegistry(
        [
            IngestFileTool(store, path_validator, ParserRegistry()),
            ListDatasetsTool(store),
            DescribeTableTool(store),
            QueryTool(store),
            SearchTool(store),
        ]
    )
    return registry, csv_path


def test_ingest_then_query(workspace):
    registry, csv_path = workspace

    ingest_result = registry.call("ingest_file", {"path": str(csv_path), "table_name": "orders"})
    assert ingest_result.success, ingest_result.error
    types_by_name = {c["name"]: c["type"] for c in ingest_result.data["columns"]}
    assert types_by_name["id"] == "INTEGER"
    assert types_by_name["amount"] == "REAL"
    assert types_by_name["customer"] == "TEXT"

    datasets_result = registry.call("list_datasets", {})
    assert datasets_result.success
    assert datasets_result.data["datasets"][0]["table_name"] == "orders"
    assert datasets_result.data["datasets"][0]["row_count"] == 3

    describe_result = registry.call("describe_table", {"table_name": "orders"})
    assert describe_result.success
    assert len(describe_result.data["sample_rows"]) == 3

    query_result = registry.call(
        "query", {"sql": "SELECT customer FROM orders WHERE amount > 12 ORDER BY customer"}
    )
    assert query_result.success, query_result.error
    assert query_result.data["rows"] == [["Bob"], ["Carol"]]


def test_query_rejects_non_select(workspace):
    registry, csv_path = workspace
    registry.call("ingest_file", {"path": str(csv_path), "table_name": "orders"})

    result = registry.call("query", {"sql": "DROP TABLE orders"})
    assert not result.success
    assert "SELECT" in result.error


def test_ingest_file_outside_allowed_dirs_fails(workspace, tmp_path):
    registry, _ = workspace
    outside = tmp_path / "outside.csv"
    outside.write_text("id\n1\n")

    result = registry.call("ingest_file", {"path": str(outside), "table_name": "outside"})
    assert not result.success
    assert "allowed" in result.error.lower()


def test_ingest_duplicate_table_name_fails(workspace):
    registry, csv_path = workspace
    registry.call("ingest_file", {"path": str(csv_path), "table_name": "orders"})

    result = registry.call("ingest_file", {"path": str(csv_path), "table_name": "orders"})
    assert not result.success
    assert "already exists" in result.error


def test_ingest_headers_with_spaces_are_normalized(workspace):
    registry, csv_path = workspace
    # Headers with spaces/punctuation (common in spreadsheet exports) must not
    # fail identifier validation — they are coerced to valid column names.
    csv_path.write_text(
        "Flights coming home pg ,Dep Time\n"
        "AA123,08:00\n"
        "BA456,09:30\n"
    )

    ingest_result = registry.call("ingest_file", {"path": str(csv_path), "table_name": "flights"})
    assert ingest_result.success, ingest_result.error
    names = [c["name"] for c in ingest_result.data["columns"]]
    assert names == ["Flights_coming_home_pg", "Dep_Time"]

    query_result = registry.call(
        "query", {"sql": 'SELECT "Flights_coming_home_pg" FROM flights ORDER BY "Dep_Time"'}
    )
    assert query_result.success, query_result.error
    assert query_result.data["rows"] == [["AA123"], ["BA456"]]


def test_describe_table_unknown_table_fails(workspace):
    registry, _ = workspace
    result = registry.call("describe_table", {"table_name": "does_not_exist"})
    assert not result.success


def test_search_enable_then_search(workspace):
    registry, csv_path = workspace
    registry.call("ingest_file", {"path": str(csv_path), "table_name": "orders"})

    enable_result = registry.call(
        "search", {"action": "enable", "table_name": "orders", "columns": ["note"]}
    )
    assert enable_result.success, enable_result.error

    search_result = registry.call(
        "search", {"action": "search", "table_name": "orders", "query": "delivery"}
    )
    assert search_result.success, search_result.error
    assert len(search_result.data["results"]) == 1
    assert search_result.data["results"][0]["customer"] == "Carol"


def test_search_before_enable_fails(workspace):
    registry, csv_path = workspace
    registry.call("ingest_file", {"path": str(csv_path), "table_name": "orders"})

    result = registry.call(
        "search", {"action": "search", "table_name": "orders", "query": "fast"}
    )
    assert not result.success
