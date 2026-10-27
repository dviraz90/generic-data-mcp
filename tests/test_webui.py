import io

import pytest

from src.config import Config
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
from src.webui.server import create_app


@pytest.fixture
def client(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

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
    config = Config(db_path=tmp_path / "store.db", allowed_dirs=(data_dir,))
    app = create_app(registry=registry, config=config)
    app.config["TESTING"] = True
    return app.test_client()


_SAME_ORIGIN = {"Origin": "http://localhost"}


def _upload_orders(client, table_name=None):
    csv = (
        "id,customer,amount,note\n"
        "1,Alice,10.50,fast shipping please\n"
        "2,Bob,20,leave at the door\n"
        "3,Carol,15.25,call before delivery\n"
    )
    data = {"file": (io.BytesIO(csv.encode()), "orders.csv")}
    if table_name is not None:
        data["table_name"] = table_name
    return client.post(
        "/api/upload", data=data, content_type="multipart/form-data", headers=_SAME_ORIGIN
    )


def test_upload_returns_schema(client):
    res = _upload_orders(client)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["table_name"] == "orders"
    types_by_name = {c["name"]: c["type"] for c in body["columns"]}
    assert types_by_name["id"] == "INTEGER"
    assert types_by_name["amount"] == "REAL"
    assert types_by_name["customer"] == "TEXT"


def test_datasets_lists_uploaded(client):
    _upload_orders(client)
    res = client.get("/api/datasets")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    names = [d["table_name"] for d in body["datasets"]]
    assert "orders" in names
    orders = next(d for d in body["datasets"] if d["table_name"] == "orders")
    assert orders["row_count"] == 3


def test_describe_returns_columns_and_sample_rows(client):
    _upload_orders(client)
    res = client.get("/api/datasets/orders")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["table_name"] == "orders"
    col_names = [c["name"] for c in body["columns"]]
    assert col_names == ["id", "customer", "amount", "note"]
    assert len(body["sample_rows"]) == 3
    assert body["sample_rows"][0]["customer"] == "Alice"


def test_query_select_returns_rows(client):
    _upload_orders(client)
    res = client.post(
        "/api/query",
        json={"sql": "SELECT customer FROM orders WHERE amount > 12 ORDER BY customer"},
        headers=_SAME_ORIGIN,
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["rows"] == [["Bob"], ["Carol"]]


def test_query_non_select_rejected(client):
    _upload_orders(client)
    res = client.post(
        "/api/query", json={"sql": "DROP TABLE orders"}, headers=_SAME_ORIGIN
    )
    assert res.status_code == 400
    body = res.get_json()
    assert body["success"] is False
    assert "SELECT" in body["error"]


def test_upload_derives_table_name_from_supplied_value(client):
    res = _upload_orders(client, table_name="custom_orders")
    assert res.status_code == 200
    assert res.get_json()["table_name"] == "custom_orders"


def test_upload_missing_file_rejected(client):
    res = client.post(
        "/api/upload", data={}, content_type="multipart/form-data", headers=_SAME_ORIGIN
    )
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_index_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Ingestion Console" in res.data


def test_upload_with_foreign_origin_rejected(client):
    csv = io.BytesIO(b"a,b\n1,2\n")
    res = client.post(
        "/api/upload",
        data={"file": (csv, "evil.csv")},
        content_type="multipart/form-data",
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert res.get_json()["success"] is False
    assert client.get("/api/datasets").get_json()["datasets"] == []


def test_upload_without_origin_rejected(client):
    csv = io.BytesIO(b"a,b\n1,2\n")
    res = client.post(
        "/api/upload", data={"file": (csv, "x.csv")}, content_type="multipart/form-data"
    )
    assert res.status_code == 403


def test_query_with_foreign_origin_rejected(client):
    res = client.post(
        "/api/query", json={"sql": "SELECT 1"}, headers={"Origin": "https://evil.example"}
    )
    assert res.status_code == 403


@pytest.mark.parametrize("host", ["evil.example", "rebind.evil.example:8765", "127.0.0.1.evil.example"])
def test_foreign_host_rejected_on_reads(client, host):
    res = client.get("/api/datasets", headers={"Host": host})
    assert res.status_code == 403
    assert res.get_json()["success"] is False


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765"])
def test_local_hosts_allowed(client, host):
    res = client.get("/api/datasets", headers={"Host": host})
    assert res.status_code == 200
    res = client.post(
        "/api/query", json={"sql": "SELECT 1"}, headers={"Host": host, "Origin": f"http://{host}"}
    )
    assert res.status_code == 200


def test_security_headers_set(client):
    res = client.get("/")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"


def test_csp_header_set(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "frame-ancestors 'none'" in csp


def test_static_assets_served_and_confined(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/../server.py").status_code == 404
    assert client.get("/static/%2e%2e/server.py").status_code == 404


def test_page_has_no_inline_script_style_or_innerhtml(client):
    html = client.get("/").get_data(as_text=True)
    assert "<style" not in html
    assert 'style="' not in html
    assert "onclick=" not in html
    assert "</script>" in html and "<script src=" in html
    inline = [s for s in html.split("<script")[1:] if s.split(">", 1)[1].split("</script>")[0].strip()]
    assert inline == []
    assert "innerHTML" not in client.get("/static/app.js").get_data(as_text=True)
