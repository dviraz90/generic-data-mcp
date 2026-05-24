from pathlib import Path

from ..exceptions import PathError


class PathValidator:
    def __init__(self, allowed_dirs: list[str]):
        self._allowed = [Path(d).resolve() for d in allowed_dirs]

    def validate(self, path: str | Path) -> Path:
        resolved = Path(path).resolve()
        for allowed in self._allowed:
            try:
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue
        allowed_str = ", ".join(str(a) for a in self._allowed)
        raise PathError(
            f"Path '{resolved}' is not under any allowed directory ({allowed_str}). "
            "Move the file to an allowed directory or update MCP_ALLOWED_DIRS."
        )
