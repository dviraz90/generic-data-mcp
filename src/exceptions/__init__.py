class MCPError(Exception):
    pass

class ParseError(MCPError):
    pass

class StorageError(MCPError):
    pass

class ValidationError(MCPError):
    pass

class PathError(ValidationError):
    pass

class SQLError(ValidationError):
    pass

class ToolError(MCPError):
    pass

class EmbedError(MCPError):
    pass
