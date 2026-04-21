"""Frontend build steps — npm/pnpm/yarn/bun for SPAs and static sites."""

from __future__ import annotations

from pathlib import Path

from dds.console import console
from dds.utils.shell import run_cmd


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

    console.print(f"[yellow]📦 Installing deps ({pm})...[/yellow]")
    result = run_cmd(f"{pm} install", verbose=verbose, cwd=project_dir)
    if result.returncode != 0:
        console.print("[red]Dependency install failed[/red]")
        if result.stderr:
            console.print(result.stderr[-500:])
        raise RuntimeError(f"{pm} install failed in {project_dir}")


def build_frontend(
    build_cmd: str = "npm run build",
    project_dir: str = ".",
    env: dict[str, str] | None = None,
    verbose: bool = False,
) -> None:
    """Run the frontend build command with optional env var injection."""
    console.print(f"[yellow]🔨 Building frontend ({build_cmd})...[/yellow]")
    result = run_cmd(build_cmd, verbose=verbose, cwd=project_dir, env=env)
    if result.returncode != 0:
        console.print("[red]Frontend build failed[/red]")
        if result.stderr:
            console.print(result.stderr[-500:])
        raise RuntimeError(f"Build failed: {build_cmd}")

    console.print("[green]✅ Frontend build complete[/green]")
