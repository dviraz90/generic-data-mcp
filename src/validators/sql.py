import sqlglot
import sqlglot.expressions as exp

from ..exceptions import SQLError

_FORBIDDEN = (
    exp.Create, exp.Drop, exp.Insert, exp.Update, exp.Delete,
    exp.Command, exp.Transaction, exp.Pragma,
)


class SQLValidator:
    def validate(self, sql: str) -> None:
        try:
            statements = sqlglot.parse(sql)
        except sqlglot.errors.ParseError as e:
            raise SQLError(
                f"Could not parse SQL: {e}. Only SELECT statements are allowed."
            ) from e

        if len(statements) != 1:
            raise SQLError(
                f"Expected exactly 1 statement, got {len(statements)}. "
                "Send one SELECT at a time."
            )

        stmt = statements[0]
        if not isinstance(stmt, exp.Select):
            raise SQLError(
                f"Only SELECT is allowed; got {type(stmt).__name__}. "
                "To explore schema use describe_table; to run queries use query."
            )

        for node in stmt.walk():
            if isinstance(node, _FORBIDDEN):
                raise SQLError(
                    f"Statement contains a forbidden operation ({type(node).__name__}). "
                    "Only read-only SELECT is permitted."
                )
