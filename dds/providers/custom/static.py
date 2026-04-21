"""Custom static site provider — config-driven command templates."""

from __future__ import annotations

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import StaticProvider
from dds.providers.custom.template import (
    build_variables,
    resolve_commands,
    run_template,
    run_template_checked,
)


class CustomStaticProvider(StaticProvider):
    """Static site provider driven by command templates."""

    def deploy(self, ctx: DeployContext) -> None:
        commands = resolve_commands(ctx, "static-site")
        variables = build_variables(ctx)

        console.print(f"\n[bold blue]🌐 Deploying static site: {ctx.name}[/bold blue]")

        # Build step (optional)
        build_tmpl = commands.get("build", "")
        if build_tmpl:
            console.print(f"[yellow]🔨 Building...[/yellow]")
            run_template_checked(
                build_tmpl, variables, "Build", verbose=ctx.verbose
            )

        # Deploy step
        deploy_tmpl = commands.get("deploy", "")
        if not deploy_tmpl:
            console.print("[red]No 'deploy' command configured for static-site[/red]")
            raise SystemExit(1)

        host = None
        if commands.get("ssh", False) or commands.get("remote", False):
            host = variables.get("host")

        console.print(f"[yellow]📤 Uploading...[/yellow]")
        run_template_checked(
            deploy_tmpl, variables, "Deploy", verbose=ctx.verbose, host=host
        )

        console.print(f"\n[green]✅ {ctx.name} deployed[/green]")

    def status(self, ctx: DeployContext) -> None:
        commands = resolve_commands(ctx, "static-site")
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
                console.print(f"  [bold]{ctx.name}[/bold]: [yellow]no status[/yellow]")
        except Exception as e:
            console.print(f"  [bold]{ctx.name}[/bold]: [red]Error: {e}[/red]")
