"""Frontend build steps — npm/pnpm/yarn for SPAs and static sites."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def detect_package_manager(project_dir: str = ".") -> str:
    """Detect which package manager to use based on lockfiles."""
    p = Path(project_dir)

    if (p / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (p / "yarn.lock").exists():
        return "yarn"
    if (p / "bun.lockb").exists():
        return "bun"
    return "npm"


def install_deps(
    project_dir: str = ".",
    package_manager: str | None = None,
    verbose: bool = False,
) -> None:
    """Install Node.js dependencies."""
    pm = package_manager or detect_package_manager(project_dir)
    cmd = f"{pm} install"

    console.print(f"[yellow]📦 Installing deps ({pm})...[/yellow]")
    if verbose:
        console.print(f"[dim]$ cd {project_dir} && {cmd}[/dim]")

    result = subprocess.run(
        cmd, shell=True, cwd=project_dir, capture_output=not verbose, text=True
    )
    if result.returncode != 0:
        console.print(f"[red]Dependency install failed[/red]")
        if result.stderr:
            console.print(result.stderr[-500:])
        raise RuntimeError(f"{pm} install failed in {project_dir}")


def build_frontend(
    build_cmd: str = "npm run build",
    project_dir: str = ".",
    env: dict[str, str] | None = None,
    verbose: bool = False,
) -> None:
    """Run the frontend build command.

    Supports injecting environment variables (critical for NEXT_PUBLIC_* etc).
    """
    import os

    build_env = os.environ.copy()
    if env:
        build_env.update(env)

    console.print(f"[yellow]🔨 Building frontend ({build_cmd})...[/yellow]")
    if verbose:
        console.print(f"[dim]$ cd {project_dir} && {build_cmd}[/dim]")

    result = subprocess.run(
        build_cmd,
        shell=True,
        cwd=project_dir,
        capture_output=not verbose,
        text=True,
        env=build_env,
    )
    if result.returncode != 0:
        console.print(f"[red]Frontend build failed[/red]")
        if result.stderr:
            console.print(result.stderr[-500:])
        raise RuntimeError(f"Build failed: {build_cmd}")

    console.print("[green]✅ Frontend build complete[/green]")
