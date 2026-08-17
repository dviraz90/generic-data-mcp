import pytest
from src.exceptions import SQLValidationError
from src.validators.sql import SQLValidator, validate_identifier


@pytest.fixture
def validator():
    return SQLValidator()


def test_allows_simple_select(validator):
    validator.validate("SELECT * FROM orders")


def test_allows_with_select(validator):
    validator.validate("WITH t AS (SELECT 1) SELECT * FROM t")


def test_allows_union(validator):
    validator.validate("SELECT id FROM a UNION SELECT id FROM b")


def test_rejects_insert(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("INSERT INTO orders (id) VALUES (1)")


def test_rejects_drop(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("DROP TABLE orders")


def test_rejects_pragma(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("PRAGMA table_info(orders)")


def test_rejects_attach(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("ATTACH DATABASE 'x.db' AS x")


def test_rejects_multiple_statements(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("SELECT 1; SELECT 2")


def test_rejects_empty_query(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("   ")


def test_rejects_unparseable_sql(validator):
    with pytest.raises(SQLValidationError):
        validator.validate("SELEKT * FORM orders")


def test_validate_identifier_accepts_valid_name():
    assert validate_identifier("orders_2024") == "orders_2024"


def test_validate_identifier_rejects_invalid_name():
    with pytest.raises(SQLValidationError):
        validate_identifier("orders; DROP TABLE x")


def test_validate_identifier_rejects_empty_name():
    with pytest.raises(SQLValidationError):
        validate_identifier("")
