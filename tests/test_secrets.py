"""Tests for dds.secrets module."""

import os
from pathlib import Path

from dds.secrets import _load_env_file, resolve_secrets


class TestLoadEnvFile:
    """Tests for _load_env_file()."""

    def test_missing_file(self) -> None:
        result = _load_env_file("/nonexistent/.env")
        assert result == {}

    def test_basic_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        result = _load_env_file(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_comments_and_blanks(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nFOO=bar\n  # another\nBAZ=qux\n")
        result = _load_env_file(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_quoted_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text('FOO="hello world"\nBAR=\'single\'\n')
        result = _load_env_file(str(env_file))
        assert result == {"FOO": "hello world", "BAR": "single"}

    def test_equals_in_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgres://user:pass@host/db?sslmode=require\n")
        result = _load_env_file(str(env_file))
        assert result["DATABASE_URL"] == "postgres://user:pass@host/db?sslmode=require"


class TestResolveSecrets:
    """Tests for resolve_secrets()."""

    def test_inline_env_vars(self) -> None:
        result = resolve_secrets(
            svc_cfg={"env": {"FOO": "bar", "NUM": 42}},
            env_cfg={},
            project_cfg={},
        )
        assert result == {"FOO": "bar", "NUM": "42"}

    def test_env_file_layer(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("BASE=from_file\n")
        result = resolve_secrets(
            svc_cfg={"env": {"OVERRIDE": "inline"}},
            env_cfg={"env_file": str(env_file)},
            project_cfg={},
        )
        assert result["BASE"] == "from_file"
        assert result["OVERRIDE"] == "inline"

    def test_env_var_secret(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_SECRET", "secret_value")
        result = resolve_secrets(
            svc_cfg={"secrets": [{"name": "DB_PASS", "env": "MY_SECRET"}]},
            env_cfg={},
            project_cfg={},
        )
        assert result["DB_PASS"] == "secret_value"

    def test_missing_env_var_secret(self, monkeypatch) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        result = resolve_secrets(
            svc_cfg={"secrets": [{"name": "MISSING", "env": "NONEXISTENT_VAR"}]},
            env_cfg={},
            project_cfg={},
        )
        assert "MISSING" not in result
