import os

DB_PATH = os.environ.get("MCP_DB_PATH", ":memory:")
ALLOWED_DIRS = [
    d.strip()
    for d in os.environ.get("MCP_ALLOWED_DIRS", "").replace(":", ",").split(",")
    if d.strip()
]
EMBED_URL = os.environ.get("MCP_EMBED_URL", "https://api.openai.com/v1/embeddings")
EMBED_MODEL = os.environ.get("MCP_EMBED_MODEL", "text-embedding-3-small")
EMBED_API_KEY = os.environ.get("MCP_EMBED_API_KEY")
