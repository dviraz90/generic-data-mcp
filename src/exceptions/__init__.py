class GenericDataMCPError(Exception):
    """Base exception for all generic-data-mcp errors."""


class ParseError(GenericDataMCPError):
    """Raised when a file cannot be parsed into rows."""


class UnsupportedFileTypeError(GenericDataMCPError):
    """Raised when no parser is registered for a file's extension."""


class PathValidationError(GenericDataMCPError):
    """Raised when a path falls outside the allowed directories."""


class SQLValidationError(GenericDataMCPError):
    """Raised when a SQL statement fails safety validation."""


class TableNotFoundError(GenericDataMCPError):
    """Raised when a referenced table does not exist."""
