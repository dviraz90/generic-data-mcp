# syntax=docker/dockerfile:1
# Pinned to a digest for reproducible builds (multi-arch index for python:3.11-slim).
# To update: docker pull python:3.11-slim && docker inspect python:3.11-slim --format='{{index .RepoDigests 0}}'
FROM python:3.11-slim@sha256:ae952e0a57138a4317b9b61caaa19a8217c2f356803f8d7e63aad08769950937

LABEL org.opencontainers.image.title="generic-data-mcp" \
      org.opencontainers.image.description="MCP server: structured files → SQLite → LLM tools"

# no-login shell; no extra packages baked in (sqlite3 CLI available via a separate ephemeral container)
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin mcp

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# /data  -- user files (ingest_file reads from here)
# /db    -- SQLite DB on a separate volume, outside the ingest-allowed tree
RUN mkdir -p /data /db && chown mcp:mcp /data /db
VOLUME /data
VOLUME /db

ENV MCP_DB_PATH=/db/store.db \
    MCP_ALLOWED_DIRS=/data

USER mcp
ENTRYPOINT ["generic-data-mcp"]
