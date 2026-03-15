"""Static site deployer — build and upload to Azure Blob Storage static hosting."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from dds.builders.frontend import build_frontend, install_deps
from dds.utils.azure import az

console = Console()


def deploy_static_site(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Build a static site and upload to Azure Blob Storage $web container.

    Config keys:
        type: static-site
        storage_account: <azure-storage-account-name>
        build_cmd: <build command, e.g. 'npm run build'>
        build_dir: <output directory, e.g. 'dist'>
        project_dir: <frontend project root, default '.'>
        install_deps: true | false (default: true)
        env: {KEY: VALUE, ...}  # build-time env vars (NEXT_PUBLIC_*, VITE_*, etc.)
        custom_domain: <optional custom domain>
        index_document: <default: index.html>
        error_document: <default: index.html (SPA routing)>
    """
    storage_account = svc_cfg.get("storage_account", "")
    build_cmd = svc_cfg.get("build_cmd", "npm run build")
    build_dir = svc_cfg.get("build_dir", "dist")
    project_dir = svc_cfg.get("project_dir", ".")
    index_doc = svc_cfg.get("index_document", "index.html")
    error_doc = svc_cfg.get("error_document", "index.html")
    rg = env_cfg.get("resource_group", "")

    console.print(f"\n[bold blue]🌐 Deploying static site: {name}[/bold blue]")

    # Step 1: Enable static website hosting
    console.print("[yellow]📋 Enabling static website hosting...[/yellow]")
    az(
        f"storage blob service-properties update "
        f"--account-name {storage_account} "
        f"--static-website "
        f"--index-document {index_doc} "
        f"--404-document {error_doc}",
        verbose=verbose,
    )

    # Step 2: Install deps (optional)
    if svc_cfg.get("install_deps", True):
        install_deps(project_dir=project_dir, verbose=verbose)

    # Step 3: Build
    build_env = dict(svc_cfg.get("env", {}))
    build_frontend(
        build_cmd=build_cmd,
        project_dir=project_dir,
        env=build_env if build_env else None,
        verbose=verbose,
    )

    # Step 4: Upload to $web container
    console.print(f"[yellow]📤 Uploading {build_dir} to $web...[/yellow]")
    az(
        f"storage blob upload-batch "
        f"--account-name {storage_account} "
        f"--source {build_dir} "
        f"--destination '$web' "
        f"--overwrite",
        verbose=verbose,
    )

    # Step 5: Show URL
    url = az(
        f"storage account show --name {storage_account} --resource-group {rg} "
        f"--query primaryEndpoints.web -o tsv",
        verbose=verbose,
        capture=True,
    )

    console.print(f"\n[green]✅ {name} deployed[/green]")
    if url:
        console.print(f"  URL: {url}")


def status_static_site(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for a static site."""
    storage_account = svc_cfg.get("storage_account", "")
    rg = env_cfg.get("resource_group", "")

    try:
        url = az(
            f"storage account show --name {storage_account} --resource-group {rg} "
            f"--query primaryEndpoints.web -o tsv",
            verbose=verbose,
            capture=True,
        )
        console.print(f"  [bold]{name}[/bold] (static → {storage_account}): {url or '[dim]no URL[/dim]'}")
    except Exception:
        console.print(f"  [bold]{name}[/bold] (static → {storage_account}): [dim]check manually[/dim]")
