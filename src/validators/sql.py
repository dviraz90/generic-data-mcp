from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError as SqlglotParseError

from src.exceptions import SQLValidationError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_ALLOWED_ROOT_TYPES = (exp.Select, exp.With, exp.Union, exp.Subquery)

_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,  # catches PRAGMA, ATTACH, DETACH, VACUUM, REINDEX, etc.
    exp.Pragma,
    exp.Attach,
    exp.Merge,
    exp.Into,  # SELECT ... INTO, and INSERT/CREATE ... AS SELECT targets
)


def normalize_identifier(name: str) -> str:
    """Coerce an arbitrary column/table header into a valid identifier.

    Runs of characters outside [A-Za-z0-9_] collapse to a single underscore,
    surrounding underscores are trimmed, and a leading digit is prefixed with an
    underscore. Already-valid names pass through unchanged. Returns "" when no
    usable characters remain (callers substitute a positional fallback).
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def validate_identifier(name: str) -> str:
    """Validates a table/column identifier before it's interpolated into SQL.

    Defense-in-depth: identifiers are always double-quoted by callers too.
    """
    if not name or not _IDENTIFIER_RE.match(name):
        raise SQLValidationError(
            f"Invalid identifier '{name}'. Identifiers must match [A-Za-z_][A-Za-z0-9_]*."
        )
    return name


class SQLValidator:
    """Allows only single, read-only SELECT statements.

    Uses sqlglot's AST (not regex): the root statement must be a
    SELECT/WITH...SELECT/UNION, and the whole tree is walked to reject
    forbidden node types (PRAGMA, ATTACH, DDL/DML) as defense-in-depth.
    """

    def validate(self, sql: str) -> exp.Expression:
        stripped = sql.strip().rstrip(";").strip()
        if not stripped:
            raise SQLValidationError("Empty query. Provide a SELECT statement.")

        try:
            statements = [s for s in sqlglot.parse(stripped, read="sqlite") if s is not None]
        except SqlglotParseError as e:
            raise SQLValidationError(f"Could not parse SQL: {e}") from e

        if len(statements) != 1:
            raise SQLValidationError(f"Only a single statement is allowed; got {len(statements)}.")

        tree = statements[0]

        if not isinstance(tree, _ALLOWED_ROOT_TYPES):
            raise SQLValidationError(
                f"Only SELECT is allowed; got {type(tree).__name__}. "
                "To explore the schema, use describe_table."
            )

        for node in tree.walk():
            node_obj = node[0] if isinstance(node, tuple) else node
            if isinstance(node_obj, _FORBIDDEN_NODE_TYPES):
                raise SQLValidationError(
                    f"Disallowed SQL construct: {type(node_obj).__name__}. "
                    "Only read-only SELECT queries are permitted."
                )

        return tree
