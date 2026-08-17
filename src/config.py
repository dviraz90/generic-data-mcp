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
    def from_env(cls) -> Config:
        db_path = Path(os.environ.get("MCP_DB_PATH", "./db/store.db")).resolve()
        raw_dirs = os.environ.get("MCP_ALLOWED_DIRS", "./data")
        allowed_dirs = tuple(Path(d).resolve() for d in raw_dirs.split(":") if d)
        cls._reject_db_inside_allowed_dirs(db_path, allowed_dirs)
        return cls(db_path=db_path, allowed_dirs=allowed_dirs)

    @staticmethod
    def _reject_db_inside_allowed_dirs(db_path: Path, allowed_dirs: tuple[Path, ...]) -> None:
        """The SQLite file must not sit inside an ingest-allowed directory.

        Otherwise `ingest_file` could be pointed at the store itself, letting the
        LLM read every other dataset's contents back through a single ingest.
        """
        for allowed in allowed_dirs:
            if db_path == allowed or allowed in db_path.parents:
                raise ValueError(
                    f"MCP_DB_PATH ({db_path}) is inside an allowed ingest directory "
                    f"({allowed}). Move the database outside MCP_ALLOWED_DIRS."
                )
