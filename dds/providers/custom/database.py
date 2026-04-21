"""Custom database provider — config-driven command templates."""

from __future__ import annotations

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import DatabaseProvider
from dds.providers.custom.template import (
    build_variables,
    resolve_commands,
    run_template,
    run_template_checked,
)


class CustomDatabaseProvider(DatabaseProvider):
    """Database provider driven by command templates."""

    def provision(self, ctx: DeployContext) -> None:
        commands = resolve_commands(ctx, "database")
        variables = build_variables(ctx)

        # Optional: check if exists first
        check_tmpl = commands.get("check", "")
        if check_tmpl:
            host = None
            if commands.get("ssh", False) or commands.get("remote", False):
                host = variables.get("host")

            result = run_template(
                check_tmpl, variables, verbose=ctx.verbose, host=host
            )
            if result.returncode == 0 and result.stdout.strip():
                console.print(
                    f"[green]✅ Database '{variables.get('database', ctx.name)}' "
                    f"already exists[/green]"
                )
                return

        provision_tmpl = commands.get("provision", "")
        if not provision_tmpl:
            console.print("[red]No 'provision' command configured for database[/red]")
            raise SystemExit(1)

        host = None
        if commands.get("ssh", False) or commands.get("remote", False):
            host = variables.get("host")

        console.print(f"\n[bold blue]🗄️  Provisioning database: {ctx.name}[/bold blue]")
        run_template_checked(
            provision_tmpl, variables, "Provision", verbose=ctx.verbose, host=host
        )
        console.print(f"[green]✅ Database provisioned[/green]")

    def status(self, ctx: DeployContext) -> None:
        commands = resolve_commands(ctx, "database")
        variables = build_variables(ctx)

        status_tmpl = commands.get("status", "")
        if not status_tmpl:
            console.print(f"  [bold]{ctx.name}[/bold]: [dim]no status command configured[/dim]")
            return

        host = None
        if commands.get("ssh", False) or commands.get("remote", False):
            host = variables.get("host")

        try:
            result = run_template(
                status_tmpl, variables, verbose=ctx.verbose, host=host
            )
            if result.returncode == 0 and result.stdout.strip():
                console.print(f"  [bold]{ctx.name}[/bold]: {result.stdout.strip()}")
            else:
                console.print(f"  [bold]{ctx.name}[/bold]: [yellow]no data[/yellow]")
        except Exception as e:
            console.print(f"  [bold]{ctx.name}[/bold]: [red]Error: {e}[/red]")
