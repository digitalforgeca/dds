"""Static site deployer — build and upload to Azure Blob Storage static hosting."""

from __future__ import annotations

from dds.builders.frontend import build_frontend, install_deps
from dds.console import console
from dds.context import DeployContext
from dds.utils.azure import az


def deploy_static_site(ctx: DeployContext) -> None:
    """Build a static site and upload to Azure Blob Storage $web container."""
    storage_account = ctx.svc_cfg.get("storage_account", "")
    build_cmd = ctx.svc_cfg.get("build_cmd", "npm run build")
    build_dir = ctx.svc_cfg.get("build_dir", "dist")
    project_dir = ctx.svc_cfg.get("project_dir", ".")
    index_doc = ctx.svc_cfg.get("index_document", "index.html")
    error_doc = ctx.svc_cfg.get("error_document", "index.html")

    console.print(f"\n[bold blue]🌐 Deploying static site: {ctx.name}[/bold blue]")

    # Enable static website hosting
    az(
        f"storage blob service-properties update "
        f"--account-name {storage_account} --static-website "
        f"--index-document {index_doc} --404-document {error_doc}",
        verbose=ctx.verbose,
    )

    # Install deps
    if ctx.svc_cfg.get("install_deps", True):
        install_deps(project_dir=project_dir, verbose=ctx.verbose)

    # Build
    build_env = dict(ctx.svc_cfg.get("env", {}))
    build_frontend(
        build_cmd=build_cmd,
        project_dir=project_dir,
        env=build_env if build_env else None,
        verbose=ctx.verbose,
    )

    # Upload
    console.print(f"[yellow]📤 Uploading {build_dir} to $web...[/yellow]")
    az(
        f"storage blob upload-batch --account-name {storage_account} "
        f"--source {build_dir} --destination '$web' --overwrite",
        verbose=ctx.verbose,
    )

    url = az(
        f"storage account show --name {storage_account} --resource-group {ctx.resource_group} "
        f"--query primaryEndpoints.web -o tsv",
        verbose=ctx.verbose,
        capture=True,
    )
    console.print(f"\n[green]✅ {ctx.name} deployed[/green]")
    if url:
        console.print(f"  URL: {url}")


def status_static_site(ctx: DeployContext) -> None:
    """Show status for a static site."""
    storage_account = ctx.svc_cfg.get("storage_account", "")
    try:
        url = az(
            f"storage account show --name {storage_account} --resource-group {ctx.resource_group} "
            f"--query primaryEndpoints.web -o tsv",
            verbose=ctx.verbose,
            capture=True,
        )
        console.print(
            f"  [bold]{ctx.name}[/bold] (static → {storage_account}): {url or '[dim]no URL[/dim]'}"
        )
    except Exception:
        console.print(
            f"  [bold]{ctx.name}[/bold] (static → {storage_account}): [dim]check manually[/dim]"
        )
