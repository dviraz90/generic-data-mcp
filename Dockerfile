# syntax=docker/dockerfile:1
FROM python:3.11-slim

LABEL org.opencontainers.image.title="generic-data-mcp" \
      org.opencontainers.image.description="MCP server: structured files → SQLite → LLM tools"

RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home --shell /bin/bash mcp

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

RUN mkdir -p /data && chown mcp:mcp /data
VOLUME /data

ENV MCP_DB_PATH=/data/store.db \
    MCP_ALLOWED_DIRS=/data

USER mcp
ENTRYPOINT ["generic-data-mcp"]
