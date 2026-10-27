from __future__ import annotations

import sqlite3

# Functions that touch process memory, the filesystem or the loader. None are
# needed to read ingested data, and `fts3_tokenizer` in particular leaks (one
# argument) and overwrites (two arguments) a native function pointer.
_DENIED_FUNCTIONS = frozenset(
    {
        "fts3_tokenizer",
        "load_extension",
        "readfile",
        "writefile",
        "edit",
    }
)

_ALLOWED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)

_PRAGMA_TABLE_PREFIX = "pragma_"

# FTS5 reads this internally to detect schema changes; without it no *_fts table
# can be queried.
_ALLOWED_PRAGMAS = frozenset({"data_version"})


class QueryAuthorizer:
    """SQLite authorizer for the connection that runs user-supplied SELECTs.

    Second layer behind ``SQLValidator``: the validator reasons about the SQL
    text, this denies at statement-prepare time anything outside read-only
    access, no matter how the text was phrased. Install with
    ``connection.set_authorizer(QueryAuthorizer())``.
    """

    def __call__(
        self,
        action: int,
        arg1: str | None,
        arg2: str | None,
        db_name: str | None,
        source: str | None,
    ) -> int:
        if action == sqlite3.SQLITE_PRAGMA:
            return (
                sqlite3.SQLITE_OK
                if (arg1 or "").lower() in _ALLOWED_PRAGMAS
                else sqlite3.SQLITE_DENY
            )
        if action not in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _DENIED_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        # pragma_* table-valued functions are PRAGMA by another name; they expose
        # the database file path and the SQLite build configuration.
        if action == sqlite3.SQLITE_READ and (arg1 or "").lower().startswith(_PRAGMA_TABLE_PREFIX):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
