from __future__ import annotations

from pathlib import Path

from src.exceptions import PathValidationError


class PathValidator:
    """Resolves a raw path and ensures it falls inside an allowed directory.

    Pure: raises on bad input, no side effects. Paths are resolved before the
    containment check so symlinks and `..` traversal can't escape the sandbox.
    """

    def __init__(self, allowed_dirs: tuple[Path, ...]):
        if not allowed_dirs:
            raise ValueError("allowed_dirs must not be empty")
        self._allowed_dirs = tuple(d.resolve() for d in allowed_dirs)

    def validate(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser().resolve()

        for allowed in self._allowed_dirs:
            if candidate == allowed or allowed in candidate.parents:
                if not candidate.exists():
                    raise PathValidationError(f"Path does not exist: {raw_path}")
                if not candidate.is_file():
                    raise PathValidationError(f"Path is not a file: {raw_path}")
                return candidate

        allowed_list = ", ".join(str(d) for d in self._allowed_dirs)
        raise PathValidationError(
            f"'{raw_path}' resolves outside the allowed directories ({allowed_list}). "
            "Move the file into an allowed directory or update MCP_ALLOWED_DIRS."
        )
