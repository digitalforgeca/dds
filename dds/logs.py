"""Container App log streaming — tail logs from Azure Container Apps."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from rich.console import Console

console = Console()


def tail_logs(
    app_name: str,
    rg: str,
    follow: bool = False,
    tail: int = 100,
    container: str | None = None,
    verbose: bool = False,
) -> None:
    """Stream or tail logs from a Container App.

    Uses `az containerapp logs show` for real-time log access.
    """
    cmd_parts = [
        "az", "containerapp", "logs", "show",
        "--name", app_name,
        "--resource-group", rg,
        "--type", "console",
        "--tail", str(tail),
    ]

    if follow:
        cmd_parts.append("--follow")

    if container:
        cmd_parts.extend(["--container", container])

    if verbose:
        console.print(f"[dim]$ {' '.join(cmd_parts)}[/dim]")

    console.print(f"[bold]📋 Logs: {app_name}[/bold]")
    if follow:
        console.print("[dim]Following logs... (Ctrl+C to stop)[/dim]\n")

    try:
        # Stream directly to stdout for follow mode
        proc = subprocess.run(
            cmd_parts,
            text=True,
            capture_output=not follow,
        )

        if not follow and proc.stdout:
            # Parse and pretty-print log lines
            for line in proc.stdout.strip().split("\n"):
                if line.strip():
                    console.print(line)

        if proc.returncode != 0 and proc.stderr:
            # Filter Azure warnings
            errors = [
                l for l in proc.stderr.split("\n")
                if l.strip() and not l.startswith("WARNING:")
            ]
            if errors:
                console.print(f"[red]{''.join(errors)}[/red]")

    except KeyboardInterrupt:
        console.print("\n[dim]Log stream stopped.[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to fetch logs: {e}[/red]")


def system_logs(
    app_name: str,
    rg: str,
    tail: int = 50,
    verbose: bool = False,
) -> None:
    """Show system/platform logs for a Container App (startup, scaling, errors)."""
    cmd_parts = [
        "az", "containerapp", "logs", "show",
        "--name", app_name,
        "--resource-group", rg,
        "--type", "system",
        "--tail", str(tail),
    ]

    if verbose:
        console.print(f"[dim]$ {' '.join(cmd_parts)}[/dim]")

    console.print(f"[bold]⚙️  System logs: {app_name}[/bold]\n")

    result = subprocess.run(cmd_parts, capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                console.print(line)
    elif result.returncode != 0:
        console.print(f"[red]Failed to fetch system logs[/red]")
