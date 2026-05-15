"""Tests for dds.secrets module."""

from pathlib import Path

from dds.secrets import load_env_file, resolve_secrets


class TestLoadEnvFile:
    """Tests for load_env_file()."""

    def test_missing_file(self) -> None:
        result = load_env_file("/nonexistent/.env")
        assert result == {}

    def test_basic_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        result = load_env_file(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_comments_and_blanks(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nFOO=bar\n  # another\nBAZ=qux\n")
        result = load_env_file(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_quoted_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=\"hello world\"\nBAR='single'\n")
        result = load_env_file(str(env_file))
        assert result == {"FOO": "hello world", "BAR": "single"}

    def test_equals_in_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgres://user:pass@host/db?sslmode=require\n")
        result = load_env_file(str(env_file))
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

    def test_inline_comment_stripped_from_unquoted_value(self, tmp_path: Path) -> None:
        """Inline comments after unquoted values must be stripped (dotenv standard)."""
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgres://localhost/mydb  # local dev only\n")
        result = load_env_file(str(env_file))
        assert result["DATABASE_URL"] == "postgres://localhost/mydb"

    def test_inline_comment_stripped_tab_separator(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("API_URL=https://api.example.com\t# production endpoint\n")
        result = load_env_file(str(env_file))
        assert result["API_URL"] == "https://api.example.com"

    def test_inline_comment_not_stripped_from_quoted_value(self, tmp_path: Path) -> None:
        """Hash inside quoted strings must be preserved as part of the value."""
        env_file = tmp_path / ".env"
        env_file.write_text('PASSWORD="hunter#2"  # good password\n')
        result = load_env_file(str(env_file))
        assert result["PASSWORD"] == "hunter#2"

    def test_quoted_value_with_trailing_comment(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text('GREETING="hello world"  # a greeting\n')
        result = load_env_file(str(env_file))
        assert result["GREETING"] == "hello world"
