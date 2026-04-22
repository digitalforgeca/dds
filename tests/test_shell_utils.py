"""Tests for dds.utils.shell — build_args_str() and run_cmd()."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from dds.utils.shell import build_args_str, run_cmd


class TestBuildArgsStr:
    """Tests for build_args_str()."""

    def test_none_returns_empty(self) -> None:
        assert build_args_str(None) == ""

    def test_empty_dict_returns_empty(self) -> None:
        assert build_args_str({}) == ""

    def test_single_simple_arg(self) -> None:
        result = build_args_str({"NODE_ENV": "production"})
        assert result == "--build-arg NODE_ENV=production"

    def test_multiple_args(self) -> None:
        result = build_args_str({"A": "1", "B": "2"})
        assert "--build-arg A=1" in result
        assert "--build-arg B=2" in result

    def test_value_with_spaces_is_quoted(self) -> None:
        result = build_args_str({"LABEL": "hello world"})
        # shlex.quote wraps in single quotes when the value contains spaces
        assert "--build-arg LABEL='hello world'" == result

    def test_value_with_dollar_sign_is_quoted(self) -> None:
        """Dollar signs must be quoted to prevent shell variable expansion."""
        result = build_args_str({"SECRET": "$MY_SECRET"})
        assert "--build-arg SECRET=" in result
        # The dollar sign must be inside quotes so the shell doesn't expand it
        assert "$MY_SECRET" not in result.replace("'$MY_SECRET'", "")

    def test_value_with_equals_sign(self) -> None:
        """Values containing = (e.g. base64, connection strings) must survive round-trip."""
        result = build_args_str({"DB_URL": "postgres://u:p@h/db?ssl=require"})
        assert "--build-arg DB_URL=" in result
        assert "postgres://u:p@h/db" in result

    def test_simple_value_not_over_quoted(self) -> None:
        """Simple alphanumeric values should not be wrapped in extra quotes."""
        result = build_args_str({"VER": "1.2.3"})
        # shlex.quote leaves safe strings unquoted
        assert result == "--build-arg VER=1.2.3"

    def test_integer_value_coerced_to_string(self) -> None:
        result = build_args_str({"PORT": 3000})  # type: ignore[arg-type]
        assert "--build-arg PORT=3000" == result


class TestRunCmd:
    """Tests for run_cmd()."""

    def test_returns_completed_process(self) -> None:
        result = run_cmd("echo hello")
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0

    def test_captures_stdout(self) -> None:
        result = run_cmd("echo captured", capture=True)
        assert "captured" in result.stdout

    def test_failing_command_returns_nonzero(self) -> None:
        result = run_cmd("exit 1")
        assert result.returncode != 0

    def test_cwd_is_passed(self, tmp_path) -> None:
        result = run_cmd("pwd", capture=True, cwd=str(tmp_path))
        assert str(tmp_path) in result.stdout

    def test_env_vars_are_merged(self, monkeypatch) -> None:
        monkeypatch.setenv("EXISTING", "yes")
        result = run_cmd("echo $EXISTING $INJECTED", capture=True, env={"INJECTED": "injected"})
        assert "yes" in result.stdout
        assert "injected" in result.stdout
