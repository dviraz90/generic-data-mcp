from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SQLType(str, Enum):
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    sql_type: SQLType


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[ColumnSchema, ...]

    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


class TypeInferrer:
    """Infers a conservative SQLite column type per field from sampled rows.

    A column becomes INTEGER/REAL only if every non-empty sampled value
    parses cleanly; otherwise it stays TEXT. Booleans are intentionally NOT
    coerced to integers — "true"/"false" fail int()/float() and land as TEXT,
    preserving their semantics.
    """

    SAMPLE_SIZE = 200

    def infer(self, rows: list[dict[str, str]], column_order: list[str]) -> TableSchema:
        samples: dict[str, list[str]] = {name: [] for name in column_order}
        for row in rows[: self.SAMPLE_SIZE]:
            for name in column_order:
                value = row.get(name, "")
                if value != "":
                    samples[name].append(value)

        columns = tuple(
            ColumnSchema(name=name, sql_type=self._infer_column_type(samples[name]))
            for name in column_order
        )
        return TableSchema(name="", columns=columns)

    def _infer_column_type(self, values: list[str]) -> SQLType:
        if not values:
            return SQLType.TEXT
        if all(self._is_int(v) for v in values):
            return SQLType.INTEGER
        if all(self._is_real(v) for v in values):
            return SQLType.REAL
        return SQLType.TEXT

    @staticmethod
    def _is_int(value: str) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_real(value: str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False
