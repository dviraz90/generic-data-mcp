from src.storage.types import SQLType, TypeInferrer


def test_integer_column():
    rows = [{"age": "25"}, {"age": "30"}, {"age": "40"}]
    schemas = TypeInferrer().infer(rows)
    assert schemas[0].sql_type == SQLType.INTEGER


def test_real_column():
    rows = [{"score": "3.14"}, {"score": "2.71"}]
    schemas = TypeInferrer().infer(rows)
    assert schemas[0].sql_type == SQLType.REAL


def test_text_fallback():
    rows = [{"val": "hello"}, {"val": "world"}]
    schemas = TypeInferrer().infer(rows)
    assert schemas[0].sql_type == SQLType.TEXT


def test_mixed_stays_text():
    rows = [{"val": "123"}, {"val": "abc"}]
    schemas = TypeInferrer().infer(rows)
    assert schemas[0].sql_type == SQLType.TEXT


def test_boolean_stays_text():
    rows = [{"flag": "true"}, {"flag": "false"}]
    schemas = TypeInferrer().infer(rows)
    assert schemas[0].sql_type == SQLType.TEXT


def test_empty_rows():
    assert TypeInferrer().infer([]) == []


def test_multiple_columns():
    rows = [{"id": "1", "name": "Alice", "score": "9.5"}]
    schemas = TypeInferrer().infer(rows)
    by_name = {s.name: s.sql_type for s in schemas}
    assert by_name["id"] == SQLType.INTEGER
    assert by_name["name"] == SQLType.TEXT
    assert by_name["score"] == SQLType.REAL
