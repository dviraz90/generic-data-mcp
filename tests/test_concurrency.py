from concurrent.futures import ThreadPoolExecutor

import pytest

from src.exceptions import GenericDataMCPError
from src.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "store.db")
    yield s
    s.close()


def _rows(n):
    return iter([{"id": str(i), "v": f"row {i}"} for i in range(n)])


def test_concurrent_ingests_of_different_tables_all_succeed(store):
    names = [f"t{i}" for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: store.ingest(n, f"{n}.csv", _rows(3000)), names))
    counts = {d.table_name: d.row_count for d in store.list_datasets()}
    assert counts == dict.fromkeys(names, 3000)
    for n in names:
        assert store.query(f'SELECT COUNT(*) FROM "{n}"').rows == [(3000,)]


def test_failed_ingest_does_not_disturb_a_concurrent_one(store):
    def good():
        return store.ingest("good", "good.csv", _rows(5000))

    def bad():
        def exploding():
            yield {"id": "1", "v": "x"}
            raise GenericDataMCPError("boom")

        with pytest.raises(GenericDataMCPError):
            store.ingest("bad", "bad.csv", exploding())

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(good)] + [pool.submit(bad) for _ in range(3)]
        for f in futures:
            f.result()
    assert {d.table_name for d in store.list_datasets()} == {"good"}
    assert store.query("SELECT COUNT(*) FROM good").rows == [(5000,)]


def test_concurrent_queries_during_ingest(store):
    store.ingest("seed", "seed.csv", _rows(10))

    def ingest():
        store.ingest("big", "big.csv", _rows(20000))

    def query():
        return [store.query("SELECT COUNT(*) FROM seed").rows for _ in range(50)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(ingest)] + [pool.submit(query) for _ in range(3)]
        results = [f.result() for f in futs]
    assert all(r == [(10,)] for res in results[1:] for r in res)
