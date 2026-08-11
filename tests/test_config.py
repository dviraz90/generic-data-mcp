from __future__ import annotations

import pytest

from src.config import Config


def test_db_outside_allowed_dirs_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_DB_PATH", str(tmp_path / "db" / "store.db"))
    monkeypatch.setenv("MCP_ALLOWED_DIRS", str(tmp_path / "data"))

    config = Config.from_env()

    assert config.db_path == (tmp_path / "db" / "store.db").resolve()
    assert config.allowed_dirs == ((tmp_path / "data").resolve(),)


def test_db_inside_allowed_dir_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_DB_PATH", str(tmp_path / "data" / "store.db"))
    monkeypatch.setenv("MCP_ALLOWED_DIRS", str(tmp_path / "data"))

    with pytest.raises(ValueError, match="inside an allowed ingest directory"):
        Config.from_env()


def test_db_nested_deeper_inside_allowed_dir_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_DB_PATH", str(tmp_path / "data" / "nested" / "store.db"))
    monkeypatch.setenv("MCP_ALLOWED_DIRS", str(tmp_path / "data"))

    with pytest.raises(ValueError, match="inside an allowed ingest directory"):
        Config.from_env()


def test_multiple_allowed_dirs_all_checked(monkeypatch, tmp_path):
    allowed = f"{tmp_path / 'a'}:{tmp_path / 'b'}"
    monkeypatch.setenv("MCP_DB_PATH", str(tmp_path / "b" / "store.db"))
    monkeypatch.setenv("MCP_ALLOWED_DIRS", allowed)

    with pytest.raises(ValueError, match="inside an allowed ingest directory"):
        Config.from_env()


def test_defaults_are_mutually_safe(monkeypatch):
    monkeypatch.delenv("MCP_DB_PATH", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_DIRS", raising=False)

    config = Config.from_env()

    assert not any(
        config.db_path == d or d in config.db_path.parents
        for d in config.allowed_dirs
    )
