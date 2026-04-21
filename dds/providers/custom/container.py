"""Custom container provider — config-driven command templates."""

from __future__ import annotations

import subprocess
import time

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import ContainerProvider
from dds.providers.custom.template import (
    build_variables,
    interpolate,
    resolve_commands,
    run_template,
    run_template_checked,
)


class CustomContainerProvider(ContainerProvider):
    """Container provider driven by command templates in dds.yaml."""

    def build(self, ctx: DeployContext) -> str:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)

        build_tmpl = commands.get("build", "")
        if not build_tmpl:
            console.print("[dim]No 'build' command configured — skipping build[/dim]")
            return variables.get("image", f"{ctx.name}:latest")

        host = self._resolve_host(commands, variables)

        console.print(f"\n[bold blue]🚀 Building {ctx.name}[/bold blue]")
        run_template_checked(
            build_tmpl, variables, "Build", verbose=ctx.verbose, host=host
        )

        return variables.get("image", f"{ctx.name}:latest")

    def deploy(self, ctx: DeployContext, image: str) -> None:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        variables["image"] = image

        deploy_tmpl = commands.get("deploy", "")
        if not deploy_tmpl:
            console.print("[red]No 'deploy' command configured for container-app[/red]")
            raise SystemExit(1)

        host = self._resolve_host(commands, variables)

        console.print(f"[yellow]🚢 Deploying {ctx.name}...[/yellow]")
        run_template_checked(
            deploy_tmpl, variables, "Deploy", verbose=ctx.verbose, host=host
        )

        console.print(f"\n[green]✅ {ctx.name} deployed[/green]")

    def status(self, ctx: DeployContext) -> None:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)

        status_tmpl = commands.get("status", "")
        if not status_tmpl:
            console.print(f"  [bold]{ctx.name}[/bold]: [dim]no status command configured[/dim]")
            return

        host = self._resolve_host(commands, variables)

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

    def rollback(self, ctx: DeployContext, target_revision: str | None = None) -> bool:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        if target_revision:
            variables["target_revision"] = target_revision
            variables["image"] = target_revision

        rollback_tmpl = commands.get("rollback", "")
        if not rollback_tmpl:
            console.print("[red]No 'rollback' command configured for container-app[/red]")
            return False

        host = self._resolve_host(commands, variables)

        console.print(f"\n[bold yellow]⏪ Rolling back {ctx.name}...[/bold yellow]")
        try:
            run_template_checked(
                rollback_tmpl, variables, "Rollback", verbose=ctx.verbose, host=host
            )
            console.print(f"[green]✅ Rolled back {ctx.name}[/green]")
            return True
        except RuntimeError:
            return False

    def revisions(self, ctx: DeployContext) -> None:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)

        revisions_tmpl = commands.get("revisions", "")
        if not revisions_tmpl:
            console.print(f"[dim]No 'revisions' command configured for {ctx.name}[/dim]")
            return

        host = self._resolve_host(commands, variables)

        console.print(f"\n[bold]📜 Revisions: {ctx.name}[/bold]\n")
        result = run_template(
            revisions_tmpl, variables, verbose=ctx.verbose, host=host
        )
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                console.print(f"  {line}")

    def logs(
        self,
        ctx: DeployContext,
        follow: bool = False,
        tail: int = 100,
        system: bool = False,
    ) -> None:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        variables["tail"] = str(tail)
        variables["follow_flag"] = "-f" if follow else ""

        log_key = "system_logs" if system else "logs"
        logs_tmpl = commands.get(log_key, commands.get("logs", ""))
        if not logs_tmpl:
            console.print(f"[dim]No '{log_key}' command configured for {ctx.name}[/dim]")
            return

        host = self._resolve_host(commands, variables)
        cmd = interpolate(logs_tmpl, variables)

        if host:
            cmd = f"ssh -o BatchMode=yes {host} {cmd!r}"

        label = "📋 Logs" if not system else "⚙️  System logs"
        console.print(f"[bold]{label}: {ctx.name}[/bold]")

        if follow:
            console.print("[dim]Following logs... (Ctrl+C to stop)[/dim]\n")
            try:
                subprocess.run(cmd, shell=True)
            except KeyboardInterrupt:
                console.print("\n[dim]Log stream stopped.[/dim]")
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        console.print(line)

    def health(
        self, ctx: DeployContext, max_retries: int = 5, retry_delay: float = 6.0
    ) -> bool:
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)

        health_tmpl = commands.get("health", "")
        if not health_tmpl:
            console.print(f"[dim]No 'health' command configured — skipping[/dim]")
            return True  # No health check = assume healthy

        host = self._resolve_host(commands, variables)

        console.print(f"\n[yellow]🏥 Health check: {ctx.name}...[/yellow]")

        for attempt in range(1, max_retries + 1):
            result = run_template(
                health_tmpl, variables, verbose=ctx.verbose, host=host
            )
            if result.returncode == 0:
                console.print(f"  ✅ Healthy")
                return True

            if attempt < max_retries:
                console.print(
                    f"  [dim]Attempt {attempt}/{max_retries}: "
                    f"failed, retrying in {retry_delay}s...[/dim]"
                )
                time.sleep(retry_delay)

        console.print(f"  [red]❌ Health check failed after {max_retries} attempts[/red]")
        return False

    @staticmethod
    def _resolve_host(
        commands: dict, variables: dict[str, str]
    ) -> str | None:
        """Resolve whether commands should be run over SSH.

        If `remote: true` is in the commands config, or `host` is set
        and the command section has `ssh: true`, wrap in SSH.
        """
        if commands.get("ssh", False) or commands.get("remote", False):
            return variables.get("host", None)
        return None
