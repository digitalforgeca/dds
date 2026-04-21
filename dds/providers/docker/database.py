"""Docker/SSH database provider — manage Postgres in Docker containers."""

from __future__ import annotations

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import DatabaseProvider
from dds.providers.docker.utils import resolve_host, ssh


class DockerDatabaseProvider(DatabaseProvider):
    """Provision and check databases in Dockerized Postgres instances."""

    def provision(self, ctx: DeployContext) -> None:
        """Create a database in a Postgres Docker container."""
        host = resolve_host(ctx)
        container = ctx.svc_cfg.get("container", ctx.svc_cfg.get("server", ""))
        db_name = ctx.svc_cfg.get("database", ctx.name)
        db_user = ctx.svc_cfg.get("user", "postgres")

        if not container:
            console.print(
                "[red]No 'container' or 'server' configured.[/red] "
                "Docker database provider needs the Postgres container name."
            )
            raise SystemExit(1)

        console.print(f"\n[bold blue]🗄️  Provisioning database: {db_name}[/bold blue]")
        console.print(f"  Host: {host} | Container: {container}")

        # Check if database already exists
        check_cmd = (
            f"docker exec {container} psql -U {db_user} -tAc "
            f"\"SELECT 1 FROM pg_database WHERE datname='{db_name}'\""
        )
        try:
            result = ssh(host, check_cmd, verbose=ctx.verbose, capture=True)
            if result.strip() == "1":
                console.print(f"[green]✅ Database '{db_name}' already exists on {container}[/green]")
                return
        except RuntimeError:
            pass  # Container might not be reachable, proceed to create

        # Create database
        create_cmd = (
            f"docker exec {container} createdb -U {db_user} {db_name}"
        )
        ssh(host, create_cmd, verbose=ctx.verbose)
        console.print(f"[green]✅ Database '{db_name}' created on {container}[/green]")

    def status(self, ctx: DeployContext) -> None:
        """Show status for a database in a Docker container."""
        host = resolve_host(ctx)
        container = ctx.svc_cfg.get("container", ctx.svc_cfg.get("server", ""))
        db_name = ctx.svc_cfg.get("database", ctx.name)
        db_user = ctx.svc_cfg.get("user", "postgres")

        if not container:
            console.print(f"  [bold]{ctx.name}[/bold]: [dim]no container configured[/dim]")
            return

        try:
            result = ssh(
                host,
                f"docker exec {container} psql -U {db_user} -tAc "
                f"\"SELECT pg_size_pretty(pg_database_size('{db_name}'))\"",
                verbose=ctx.verbose,
                capture=True,
            )
            size = result.strip() if result else "?"
            console.print(
                f"  [bold]{ctx.name}[/bold] (db: {db_name} @ {container}): "
                f"[green]exists[/green] | size: {size}"
            )
        except Exception as e:
            console.print(
                f"  [bold]{ctx.name}[/bold] (db: {db_name} @ {container}): [red]Error: {e}[/red]"
            )
