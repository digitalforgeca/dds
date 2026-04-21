"""Docker/SSH utility functions — remote command execution over SSH."""

from __future__ import annotations

import subprocess

from dds.console import console
from dds.context import DeployContext


def ssh(
    host: str,
    cmd: str,
    verbose: bool = False,
    capture: bool = False,
) -> str:
    """Run a command on a remote host via SSH.

    Args:
        host: SSH host (hostname, IP, or ~/.ssh/config alias).
        cmd: Command to execute remotely.
        verbose: Print command and output.
        capture: Return stdout as string.

    Returns:
        stdout if capture=True, else empty string.
    """
    full_cmd = f"ssh -o BatchMode=yes -o ConnectTimeout=10 {host} {cmd!r}"

    if verbose:
        console.print(f"[dim]$ ssh {host} {cmd}[/dim]")

    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            console.print(f"[red]SSH command failed:[/red] {cmd}\n{stderr}")
            raise RuntimeError(f"SSH command failed on {host}: {cmd}")

    return result.stdout.strip() if capture else ""


def resolve_host(ctx: DeployContext) -> str:
    """Resolve the SSH host from config hierarchy.

    Checks: service → environment → project level.
    """
    host = (
        ctx.svc_cfg.get("host")
        or ctx.env_cfg.get("host")
        or ctx.project_cfg.get("host", "")
    )
    if not host:
        console.print(
            "[red]No 'host' configured.[/red] Docker provider requires an SSH host.\n"
            "  Set 'host' at the project, environment, or service level in dds.yaml."
        )
        raise SystemExit(1)
    return host


def resolve_compose_file(ctx: DeployContext) -> str:
    """Resolve the Docker Compose file path from config."""
    return (
        ctx.svc_cfg.get("compose_file")
        or ctx.env_cfg.get("compose_file")
        or ctx.project_cfg.get("compose_file", "docker-compose.yml")
    )


def resolve_compose_project_dir(ctx: DeployContext) -> str:
    """Resolve the remote project directory where docker-compose.yml lives."""
    return (
        ctx.svc_cfg.get("project_dir")
        or ctx.env_cfg.get("project_dir")
        or ctx.project_cfg.get("project_dir", "")
    )
