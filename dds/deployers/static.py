"""Static site deployer — build and upload to Azure Blob Storage static hosting."""

from __future__ import annotations

import subprocess
from typing import Any

from rich.console import Console

from dds.utils.azure import az

console = Console()


def deploy_static_site(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Build a static site and upload to Azure Blob Storage $web container."""
    storage_account = svc_cfg.get("storage_account", "")
    build_cmd = svc_cfg.get("build_cmd", "npm run build")
    build_dir = svc_cfg.get("build_dir", "dist")
    rg = env_cfg.get("resource_group", "")

    console.print(f"\n[bold blue]🌐 Deploying static site: {name}[/bold blue]")

    # Step 1: Enable static website hosting if not already
    console.print("[yellow]📋 Enabling static website hosting...[/yellow]")
    az(
        f"storage blob service-properties update "
        f"--account-name {storage_account} "
        f"--static-website --index-document index.html --404-document index.html",
        verbose=verbose,
    )

    # Step 2: Build
    console.print(f"[yellow]🔨 Building ({build_cmd})...[/yellow]")
    result = subprocess.run(
        build_cmd,
        shell=True,
        capture_output=not verbose,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]Build failed:[/red]\n{result.stderr}")
        raise SystemExit(1)

    # Step 3: Upload to $web container
    console.print(f"[yellow]📤 Uploading {build_dir} to $web...[/yellow]")
    az(
        f"storage blob upload-batch "
        f"--account-name {storage_account} "
        f"--source {build_dir} "
        f"--destination '$web' "
        f"--overwrite",
        verbose=verbose,
    )

    # Step 4: Get the static site URL
    console.print(f"\n[green]✅ {name} deployed to static hosting[/green]")

    # Show the URL
    az(
        f"storage account show --name {storage_account} --resource-group {rg} "
        f"--query primaryEndpoints.web -o tsv",
        verbose=verbose,
        capture=True,
    )


def status_static_site(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for a static site."""
    storage_account = svc_cfg.get("storage_account", "")
    console.print(f"  [bold]{name}[/bold] (static → {storage_account}): [dim]check manually[/dim]")
