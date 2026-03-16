"""Azure CLI wrapper utilities."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from dds.console import console


def az(
    cmd: str,
    verbose: bool = False,
    capture: bool = False,
) -> str:
    """Run an Azure CLI command.

    Args:
        cmd: Command arguments (without 'az' prefix).
        verbose: Print command and output.
        capture: Return stdout as string.

    Returns:
        stdout if capture=True, else empty string.
    """
    full_cmd = f"az {cmd}"

    if verbose:
        console.print(f"[dim]$ {full_cmd}[/dim]")

    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    if result.returncode != 0:
        stderr = result.stderr.strip()
        error_lines = [line for line in stderr.split("\n") if not line.startswith("WARNING:")]
        if error_lines:
            error_msg = "\n".join(error_lines)
            console.print(f"[red]Command failed:[/red] {full_cmd}\n{error_msg}")
            raise RuntimeError(f"Command failed: {full_cmd}")

    return result.stdout.strip() if capture else ""


def az_json(cmd: str, verbose: bool = False) -> dict[str, Any]:
    """Run an az command and parse JSON output."""
    output = az(f"{cmd} -o json", verbose=verbose, capture=True)
    return json.loads(output)


def run_cmd(
    cmd: str,
    verbose: bool = False,
    capture: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command with standard error handling.

    Shared subprocess wrapper for Docker, npm, and other non-az commands.
    """
    if verbose:
        console.print(f"[dim]$ {cmd}[/dim]")

    import os

    run_env = None
    if env:
        run_env = os.environ.copy()
        run_env.update(env)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, env=run_env)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    return result
