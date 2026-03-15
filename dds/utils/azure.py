"""Azure CLI wrapper utilities."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from rich.console import Console

console = Console()


def az(
    cmd: str,
    verbose: bool = False,
    use_docker: bool = False,
    capture: bool = False,
) -> str:
    """Run an Azure CLI or Docker command.

    Args:
        cmd: Command arguments (without 'az' prefix for Azure, with 'docker' prefix for Docker).
        verbose: Print command output in real-time.
        use_docker: If True, run as a docker command instead of az command.
        capture: Return stdout as string.

    Returns:
        stdout if capture=True, else empty string.
    """
    prefix = "" if use_docker else "az "
    full_cmd = f"{prefix}{cmd}"

    if verbose:
        console.print(f"[dim]$ {full_cmd}[/dim]")

    result = subprocess.run(
        full_cmd,
        shell=True,
        capture_output=True,
        text=True,
    )

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Filter out common Azure warnings
        error_lines = [
            line for line in stderr.split("\n")
            if not line.startswith("WARNING:")
        ]
        if error_lines:
            error_msg = "\n".join(error_lines)
            console.print(f"[red]Command failed:[/red] {full_cmd}\n{error_msg}")
            raise RuntimeError(f"Command failed: {full_cmd}")

    if capture:
        return result.stdout.strip()
    return ""


def az_json(cmd: str, verbose: bool = False) -> dict[str, Any]:
    """Run an az command and parse JSON output."""
    output = az(f"{cmd} -o json", verbose=verbose, capture=True)
    return json.loads(output)
