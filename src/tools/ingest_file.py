from pathlib import Path

from .base import BaseTool, ToolResult
from ..exceptions import MCPError
from ..parsers.registry import ParserRegistry
from ..storage.sqlite_store import SQLiteStore
from ..storage.types import TableSchema
from ..validators.path import PathValidator


class IngestFileTool(BaseTool):
    @property
    def name(self) -> str:
        return "ingest_file"

    @property
    def description(self) -> str:
        return (
            "Parse a structured data file (CSV, TSV, pipe-delimited, JSON, JSONL) "
            "and load it into a queryable SQLite table. Provide the absolute path "
            "and a table name. After ingesting, call describe_table to verify the schema."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the data file",
                },
                "table_name": {
                    "type": "string",
                    "description": "Name for the SQLite table (letters, digits, underscores)",
                },
            },
            "required": ["path", "table_name"],
        }

    def __init__(
        self,
        store: SQLiteStore,
        parser_registry: ParserRegistry,
        path_validator: PathValidator,
    ):
        self._store = store
        self._parsers = parser_registry
        self._path_validator = path_validator

    def run(self, **kwargs) -> ToolResult:
        try:
            path = self._path_validator.validate(kwargs["path"])
            table_name = kwargs["table_name"]

            parser = self._parsers.get(path)
            rows = list(parser.parse(path))

            if not rows:
                return ToolResult(
                    content=f"File '{Path(kwargs['path']).name}' appears to be empty.",
                    is_error=True,
                )

            schemas = self._store.types.infer(rows)
            schema = TableSchema(name=table_name, columns=schemas)
            self._store.tables.create(schema)
            count = self._store.ingestor.ingest(schema, iter(rows))
            self._store.metadata.register(table_name, str(path), count)

            col_summary = ", ".join(
                f"{c.name} ({c.sql_type.value})" for c in schemas
            )
            return ToolResult(
                content=f"Ingested {count} rows into '{table_name}'. Columns: {col_summary}."
            )
        except MCPError as e:
            return ToolResult(content=str(e), is_error=True)
