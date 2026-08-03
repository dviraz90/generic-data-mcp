from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Server configuration, read once from environment variables."""

    db_path: Path
    allowed_dirs: tuple[Path, ...]

    @classmethod
    def from_env(cls) -> "Config":
        db_path = Path(os.environ.get("MCP_DB_PATH", "./data/store.db")).resolve()
        raw_dirs = os.environ.get("MCP_ALLOWED_DIRS", "./data")
        allowed_dirs = tuple(Path(d).resolve() for d in raw_dirs.split(":") if d)
        return cls(db_path=db_path, allowed_dirs=allowed_dirs)
