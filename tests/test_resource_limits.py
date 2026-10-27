import json

import pytest

from src.exceptions import ParseError
from src.parsers.json_parsers import JSONParser
from src.storage.sqlite_store import SQLiteStore
from src.tools import SearchTool


def test_json_over_size_cap_rejected_with_jsonl_hint(tmp_path):
    f = tmp_path / "big.json"
    f.write_text(json.dumps([{"a": "x" * 100}]))
    with pytest.raises(ParseError, match="JSON Lines"):
        list(JSONParser(max_bytes=50).parse(f))


def test_json_under_cap_parses(tmp_path):
    f = tmp_path / "ok.json"
    f.write_text(json.dumps([{"a": 1}]))
    assert list(JSONParser(max_bytes=1000).parse(f)) == [{"a": "1"}]


@pytest.fixture
def search_tool(tmp_path):
    store = SQLiteStore(tmp_path / "s.db")
    store.ingest("t", "t.csv", iter([{"w": f"apple {i}"} for i in range(1200)]))
    store.enable_search("t", ["w"])
    yield SearchTool(store)
    store.close()


def _search(tool, limit):
    return tool.execute({"action": "search", "table_name": "t", "query": "apple", "limit": limit})


def test_search_limit_clamped_to_max(search_tool):
    assert len(_search(search_tool, -1).data["results"]) == 1
    assert len(_search(search_tool, 0).data["results"]) == 1
    assert len(_search(search_tool, 10**9).data["results"]) == 1000


@pytest.mark.parametrize("bad", ["50", 2.5, True])
def test_search_non_integer_limit_rejected(search_tool, bad):
    res = _search(search_tool, bad)
    assert not res.success
    assert "integer" in res.error


def test_search_null_limit_uses_default(search_tool):
    assert len(_search(search_tool, None).data["results"]) == 50
