"""Database deployer — managed Postgres provisioning and status."""

from __future__ import annotations

from dds.console import console
from dds.context import DeployContext
from dds.utils.azure import az, az_json


def provision_database(ctx: DeployContext) -> None:
    """Create a database on a managed Postgres Flex server."""
    server = ctx.svc_cfg.get("server", "")
    db_name = ctx.svc_cfg.get("database", ctx.name)
    charset = ctx.svc_cfg.get("charset", "UTF8")
    collation = ctx.svc_cfg.get("collation", "en_US.utf8")

    console.print(f"\n[bold blue]🗄️  Provisioning database: {db_name}[/bold blue]")
    console.print(f"  Server: {server} ({ctx.resource_group})")

    az(
        f"postgres flexible-server db create "
        f"--server-name {server} --resource-group {ctx.resource_group} "
        f"--database-name {db_name} --charset {charset} --collation {collation}",
        verbose=ctx.verbose,
    )
    console.print(f"[green]✅ Database '{db_name}' provisioned on {server}[/green]")


def status_database(ctx: DeployContext) -> None:
    """Show status for a managed Postgres database."""
    server = ctx.svc_cfg.get("server", "")
    db_name = ctx.svc_cfg.get("database", ctx.name)

    try:
        data = az_json(
            f"postgres flexible-server db show "
            f"--server-name {server} --resource-group {ctx.resource_group} "
            f"--database-name {db_name}"
        )
        console.print(
            f"  [bold]{ctx.name}[/bold] (db: {db_name} @ {server}): "
            f"[green]exists[/green] | charset: {data.get('charset', '?')} | "
            f"collation: {data.get('collation', '?')}"
        )
    except Exception as e:
        console.print(
            f"  [bold]{ctx.name}[/bold] (db: {db_name} @ {server}): [red]Error: {e}[/red]"
        )
