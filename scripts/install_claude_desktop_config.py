#!/usr/bin/env python3
"""Add (or update) the generic-data-mcp entry in Claude Desktop's config.

Locates claude_desktop_config.json for the current OS (macOS or Windows),
merges in an mcpServers entry for this server, and writes the file back —
any other servers already configured are left untouched.

Usage:
    python scripts/install_claude_desktop_config.py \\
        --db-path ./db/store.db --allowed-dirs ./data

    python scripts/install_claude_desktop_config.py \\
        --db-path ./db/store.db --allowed-dirs ./data --docker
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path


def config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise SystemExit("APPDATA environment variable is not set")
        return Path(appdata) / "Claude/claude_desktop_config.json"
    raise SystemExit(f"Unsupported OS for Claude Desktop: {system} (only macOS and Windows are supported)")


def build_entry(db_path: Path, allowed_dirs: Path, docker: bool, image: str, command: str) -> dict:
    if docker:
        return {
            "command": "docker",
            "args": [
                "run", "--rm", "-i",
                "--network", "none",
                "-v", f"{allowed_dirs}:/data",
                "-v", f"{db_path.parent}:/db",
                "-e", "MCP_DB_PATH=/db/store.db",
                "-e", "MCP_ALLOWED_DIRS=/data",
                image,
            ],
        }
    return {
        "command": command,
        "env": {
            "MCP_DB_PATH": str(db_path),
            "MCP_ALLOWED_DIRS": str(allowed_dirs),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", required=True, help="Path to the SQLite store, e.g. ./db/store.db")
    parser.add_argument("--allowed-dirs", required=True, help="Directory ingest_file may read from, e.g. ./data")
    parser.add_argument("--name", default="generic-data-mcp", help="Server name/key in mcpServers (default: generic-data-mcp)")
    parser.add_argument("--docker", action="store_true", help="Configure the containerized server instead of a local install")
    parser.add_argument("--image", default="generic-data-mcp:latest", help="Docker image tag (only used with --docker)")
    parser.add_argument(
        "--command",
        default="generic-data-mcp",
        help=(
            "Executable to launch for a local (non-docker) install. Defaults to 'generic-data-mcp', "
            "which only works if it's on the PATH Claude Desktop's subprocess inherits (often a bare "
            "PATH that excludes venvs/Homebrew). If unsure, pass an absolute path, e.g. "
            "/path/to/project/.venv/bin/generic-data-mcp."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the resulting config instead of writing it")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    allowed_dirs = Path(args.allowed_dirs).expanduser().resolve()

    if not args.docker and not Path(args.command).is_absolute():
        resolved = shutil.which(args.command)
        if resolved is None:
            print(
                f"warning: '{args.command}' was not found on this shell's PATH. Claude Desktop's "
                "subprocess PATH is often even more restricted (it may exclude venvs and Homebrew "
                "entirely), so this entry may fail to launch. Re-run with --command set to an "
                "absolute path (e.g. /path/to/.venv/bin/generic-data-mcp) if it does.",
                file=sys.stderr,
            )

    # Mirrors Config.from_env()'s own check: if the DB sits inside the ingest tree,
    # ingest_file can be pointed at the store itself and read every dataset back out.
    if db_path == allowed_dirs or allowed_dirs in db_path.parents:
        raise SystemExit(
            f"--db-path ({db_path}) is inside --allowed-dirs ({allowed_dirs}). "
            "The store must live outside the ingest-allowed tree."
        )

    path = config_path()
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path} contains invalid JSON, refusing to overwrite it: {e}")

    existing.setdefault("mcpServers", {})
    existing["mcpServers"][args.name] = build_entry(db_path, allowed_dirs, args.docker, args.image, args.command)

    rendered = json.dumps(existing, indent=2) + "\n"

    if args.dry_run:
        print(rendered)
        return

    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
        print(f"Backed up existing config to {backup}")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically (temp file + rename) so a crash or Ctrl-C mid-write can't
    # leave a truncated/corrupt config behind, and lock it to the owner since
    # mcpServers entries (this one or others already in the file) can carry secrets.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(rendered)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise

    print(f"Wrote {args.name} to {path}")
    print("Restart Claude Desktop for the change to take effect.")


if __name__ == "__main__":
    main()
