"""Generic shell command utilities — shared by all providers."""

from __future__ import annotations

import os
import shlex
import subprocess

from dds.console import console


def run_cmd(
    cmd: str,
    verbose: bool = False,
    capture: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command with standard error handling.

    Shared subprocess wrapper for Docker, npm, and other non-provider-specific commands.
    """
    if verbose:
        console.print(f"[dim]$ {cmd}[/dim]")

    run_env = None
    if env:
        run_env = os.environ.copy()
        run_env.update(env)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, env=run_env)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    return result


def build_args_str(build_args: dict[str, str] | None) -> str:
    """Format a build-args dict into Docker --build-arg flags.

    Values are shell-quoted so that spaces and metacharacters in values do not
    break the command string when it is passed to the shell with shell=True.

    Example::

        >>> build_args_str({'NODE_ENV': 'production', 'LABEL': 'hello world'})
        "--build-arg NODE_ENV=production --build-arg LABEL='hello world'"
    """
    if not build_args:
        return ""
    return " ".join(
        f"--build-arg {k}={shlex.quote(str(v))}" for k, v in build_args.items()
    )
