from dataclasses import dataclass
from enum import Enum
from typing import Any


class SQLType(Enum):
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"


@dataclass
class ColumnSchema:
    name: str
    sql_type: SQLType


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnSchema]


_SAMPLE_SIZE = 200


class TypeInferrer:
    def infer(self, rows: list[dict[str, Any]]) -> list[ColumnSchema]:
        if not rows:
            return []
        sample = rows[:_SAMPLE_SIZE]
        columns = list(sample[0].keys())
        return [
            ColumnSchema(name=col, sql_type=self._infer_type(
                [str(r.get(col, "")) for r in sample if str(r.get(col, "")).strip()]
            ))
            for col in columns
        ]

    def _infer_type(self, values: list[str]) -> SQLType:
        if not values:
            return SQLType.TEXT
        if all(self._is_int(v) for v in values):
            return SQLType.INTEGER
        if all(self._is_real(v) for v in values):
            return SQLType.REAL
        return SQLType.TEXT

    @staticmethod
    def _is_int(v: str) -> bool:
        try:
            int(v)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_real(v: str) -> bool:
        try:
            float(v)
            return True
        except ValueError:
            return False
