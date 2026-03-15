"""Database deployer — managed Postgres provisioning and migration."""

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
    """Create a database on a managed Postgres Flex server."""
    server = db_cfg.get("server", "")
    rg = db_cfg.get("resource_group", env_cfg.get("resource_group", ""))
    db_name = db_cfg.get("database", name)

    console.print(f"\n[bold blue]🗄️  Provisioning database: {db_name}[/bold blue]")
    console.print(f"  Server: {server} ({rg})")

    az(
        f"postgres flexible-server db create "
        f"--server-name {server} --resource-group {rg} "
        f"--database-name {db_name} --charset UTF8 --collation en_US.utf8",
        verbose=verbose,
    )

    console.print(f"[green]✅ Database '{db_name}' created on {server}[/green]")
