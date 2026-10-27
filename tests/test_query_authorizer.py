import pytest

from src.exceptions import SQLValidationError
from src.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "store.db")
    s.ingest("orders", "orders.csv", iter([{"id": "1", "customer": "Alice"}, {"id": "2", "customer": "Bob"}]))
    yield s
    s.close()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT fts3_tokenizer('simple')",
        "SELECT fts3_tokenizer('simple', x'4141414141414141')",
        "SELECT hex(fts3_tokenizer('simple', fts3_tokenizer('porter')))",
        "SELECT load_extension('/tmp/x')",
        "SELECT * FROM pragma_database_list",
        "SELECT * FROM pragma_compile_options",
        "SELECT name FROM pragma_table_info('orders')",
    ],
)
def test_dangerous_calls_are_denied(store, sql):
    with pytest.raises(SQLValidationError, match="not available in read-only"):
        store.query(sql)


def test_query_connection_cannot_write(store):
    # Bypass the SQL validator to prove the connection itself is read-only.
    for sql in ("DELETE FROM orders", "CREATE TABLE x (a)", "ATTACH ':memory:' AS m", "PRAGMA journal_mode=DELETE"):
        with pytest.raises(Exception):
            store._query_connection.execute(sql)
    assert store.query("SELECT COUNT(*) FROM orders").rows == [(2,)]


def test_normal_queries_still_work(store):
    assert store.query("SELECT customer FROM orders ORDER BY id").rows == [("Alice",), ("Bob",)]
    joined = store.query("SELECT a.id, b.id FROM orders a JOIN orders b ON a.id = b.id ORDER BY a.id")
    assert joined.rows == [(1, 1), (2, 2)]
    cte = store.query(
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 5) SELECT x FROM c"
    )
    assert [r[0] for r in cte.rows] == [1, 2, 3, 4, 5]


def test_rows_ingested_after_open_are_visible(store):
    store.ingest("later", "later.csv", iter([{"v": "7"}]))
    assert store.query("SELECT v FROM later").rows == [(7,)]


def test_search_tables_remain_queryable(store):
    store.enable_search("orders", ["customer"])
    assert store.query("SELECT COUNT(*) FROM orders_fts").rows == [(2,)]
    assert [r["customer"] for r in store.search("orders", "alice")] == ["Alice"]


def test_readfile_is_unavailable(store):
    # Not compiled into stock SQLite; the authorizer denylist covers builds that have it.
    with pytest.raises(Exception, match="readfile"):
        store.query("SELECT readfile('/etc/passwd')")
