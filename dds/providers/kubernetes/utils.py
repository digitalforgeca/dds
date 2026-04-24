"""Kubernetes CLI wrapper utilities — kubectl and helm."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from dds.console import console


def kubectl(
    cmd: str,
    verbose: bool = False,
    capture: bool = False,
    namespace: str | None = None,
) -> str:
    """Run a kubectl command.

    Args:
        cmd: Command arguments (without 'kubectl' prefix).
        verbose: Print command and output.
        capture: Return stdout as string.
        namespace: Optional namespace flag.

    Returns:
        stdout if capture=True, else empty string.
    """
    ns_flag = f" -n {namespace}" if namespace else ""
    full_cmd = f"kubectl{ns_flag} {cmd}"

    if verbose:
        console.print(f"[dim]$ {full_cmd}[/dim]")

    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            console.print(f"[red]Command failed:[/red] {full_cmd}\n{stderr}")
            raise RuntimeError(f"Command failed: {full_cmd}")

    return result.stdout.strip() if capture else ""


def kubectl_json(cmd: str, verbose: bool = False, namespace: str | None = None) -> dict[str, Any]:
    """Run a kubectl command and parse JSON output."""
    output = kubectl(f"{cmd} -o json", verbose=verbose, capture=True, namespace=namespace)
    return json.loads(output) if output else {}


def kubectl_apply_kustomize(overlay_dir: str, verbose: bool = False) -> None:
    """Apply a Kustomize overlay directory."""
    kubectl(f"apply -k {overlay_dir}", verbose=verbose)


def helm(cmd: str, verbose: bool = False, capture: bool = False) -> str:
    """Run a helm command."""
    full_cmd = f"helm {cmd}"

    if verbose:
        console.print(f"[dim]$ {full_cmd}[/dim]")

    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            console.print(f"[red]Command failed:[/red] {full_cmd}\n{stderr}")
            raise RuntimeError(f"Command failed: {full_cmd}")

    return result.stdout.strip() if capture else ""
