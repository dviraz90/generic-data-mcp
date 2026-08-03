from src.storage.types import SQLType, TypeInferrer


def test_infers_integer_column():
    inferrer = TypeInferrer()
    rows = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    schema = inferrer.infer(rows, ["id"])
    assert schema.columns[0].sql_type == SQLType.INTEGER


def test_infers_real_column():
    inferrer = TypeInferrer()
    rows = [{"price": "1.5"}, {"price": "2"}, {"price": "3.25"}]
    schema = inferrer.infer(rows, ["price"])
    assert schema.columns[0].sql_type == SQLType.REAL


def test_infers_text_column_on_mixed_values():
    inferrer = TypeInferrer()
    rows = [{"name": "Alice"}, {"name": "Bob"}]
    schema = inferrer.infer(rows, ["name"])
    assert schema.columns[0].sql_type == SQLType.TEXT


def test_booleans_are_not_coerced_to_integer():
    inferrer = TypeInferrer()
    rows = [{"active": "true"}, {"active": "false"}]
    schema = inferrer.infer(rows, ["active"])
    assert schema.columns[0].sql_type == SQLType.TEXT


def test_empty_values_are_skipped_when_inferring():
    inferrer = TypeInferrer()
    rows = [{"id": "1"}, {"id": ""}, {"id": "3"}]
    schema = inferrer.infer(rows, ["id"])
    assert schema.columns[0].sql_type == SQLType.INTEGER


def test_all_empty_column_defaults_to_text():
    inferrer = TypeInferrer()
    rows = [{"id": ""}, {"id": ""}]
    schema = inferrer.infer(rows, ["id"])
    assert schema.columns[0].sql_type == SQLType.TEXT


def test_only_first_sample_size_rows_considered():
    inferrer = TypeInferrer()
    rows = [{"id": "1"} for _ in range(200)] + [{"id": "not-a-number"}]
    schema = inferrer.infer(rows, ["id"])
    assert schema.columns[0].sql_type == SQLType.INTEGER
