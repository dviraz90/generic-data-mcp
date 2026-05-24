import pytest

from src.exceptions import SQLError
from src.validators.sql import SQLValidator


@pytest.fixture
def validator():
    return SQLValidator()


def test_valid_select(validator):
    validator.validate("SELECT * FROM my_table")


def test_valid_select_with_where(validator):
    validator.validate("SELECT id, name FROM users WHERE age > 18")


def test_valid_select_with_join(validator):
    validator.validate("SELECT a.id, b.name FROM a JOIN b ON a.id = b.id")


def test_rejects_drop(validator):
    with pytest.raises(SQLError, match="Only SELECT"):
        validator.validate("DROP TABLE users")


def test_rejects_insert(validator):
    with pytest.raises(SQLError, match="Only SELECT"):
        validator.validate("INSERT INTO users VALUES (1, 'Alice')")


def test_rejects_update(validator):
    with pytest.raises(SQLError, match="Only SELECT"):
        validator.validate("UPDATE users SET name='Bob' WHERE id=1")


def test_rejects_multiple_statements(validator):
    with pytest.raises(SQLError, match="exactly 1 statement"):
        validator.validate("SELECT 1; SELECT 2")


def test_rejects_create(validator):
    with pytest.raises(SQLError):
        validator.validate("CREATE TABLE x (id INTEGER)")
