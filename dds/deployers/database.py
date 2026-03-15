"""Database deployer — managed Postgres provisioning and status."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from dds.utils.azure import az, az_json

console = Console()


def provision_database(
    name: str,
    db_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Create a database on a managed Postgres Flex server.

    Config keys:
        type: database
        server: <postgres-flex-server-name>
        database: <database-name>
        resource_group: <override rg, defaults to env rg>
        charset: <default UTF8>
        collation: <default en_US.utf8>
    """
    server = db_cfg.get("server", "")
    rg = db_cfg.get("resource_group", env_cfg.get("resource_group", ""))
    db_name = db_cfg.get("database", name)
    charset = db_cfg.get("charset", "UTF8")
    collation = db_cfg.get("collation", "en_US.utf8")

    console.print(f"\n[bold blue]🗄️  Provisioning database: {db_name}[/bold blue]")
    console.print(f"  Server: {server} ({rg})")

    az(
        f"postgres flexible-server db create "
        f"--server-name {server} --resource-group {rg} "
        f"--database-name {db_name} --charset {charset} --collation {collation}",
        verbose=verbose,
    )

    console.print(f"[green]✅ Database '{db_name}' provisioned on {server}[/green]")


def status_database(
    name: str,
    db_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for a managed Postgres database."""
    server = db_cfg.get("server", "")
    rg = db_cfg.get("resource_group", env_cfg.get("resource_group", ""))
    db_name = db_cfg.get("database", name)

    try:
        data = az_json(
            f"postgres flexible-server db show "
            f"--server-name {server} --resource-group {rg} "
            f"--database-name {db_name}"
        )
        charset = data.get("charset", "?")
        collation = data.get("collation", "?")
        console.print(
            f"  [bold]{name}[/bold] (db: {db_name} @ {server}): "
            f"[green]exists[/green] | charset: {charset} | collation: {collation}"
        )
    except Exception as e:
        console.print(f"  [bold]{name}[/bold] (db: {db_name} @ {server}): [red]Error: {e}[/red]")
