import time

import pytest

from src.exceptions import QueryTimeoutError
from src.storage.query import QueryExecutor
from src.storage.sqlite_store import SQLiteStore
from src.validators.sql import SQLValidator


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "store.db")
    s.ingest("t", "t.csv", iter([{"a": "1"}]))
    # Short budget so the runaway-query tests stay fast.
    s.query_executor = QueryExecutor(s._query_connection, SQLValidator(), timeout_seconds=0.5)
    yield s
    s.close()


def test_infinite_recursive_cte_times_out(store):
    start = time.monotonic()
    with pytest.raises(QueryTimeoutError, match="limit"):
        store.query(
            "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c"
        )
    assert time.monotonic() - start < 3


def test_oversized_value_rejected(store):
    with pytest.raises(QueryTimeoutError, match="size limit"):
        store.query("SELECT length(randomblob(20000000))")


def test_connection_usable_after_timeout(store):
    with pytest.raises(QueryTimeoutError):
        store.query(
            "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c"
        )
    assert store.query("SELECT a FROM t").rows == [(1,)]


def test_normal_queries_unaffected(store):
    result = store.query(
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 1000) SELECT sum(x) FROM c"
    )
    assert result.rows == [(500500,)]
