"""DDS CLI — cross-platform deployment commands."""

from __future__ import annotations

import click

from dds import __version__
from dds.config import load_config
from dds.console import console
from dds.context import DeployContext


def _load_cfg(ctx: click.Context) -> dict:
    """Load config or exit."""
    cfg = load_config(ctx.obj["config_path"])
    if cfg is None:
        console.print("[red]Error:[/red] No dds.yaml found. Run 'dds init' to create one.")
        raise SystemExit(1)
    return cfg


def _load_env(ctx: click.Context, environment: str, *, require_access: bool = False) -> tuple[dict, dict]:
    """Load config and resolve environment. Returns (full_cfg, env_cfg).

    If require_access=True, checks the environment's 'access' setting:
      - "restricted": only allowed deployers (by git email) can deploy
      - "open" or absent: anyone can deploy
    """
    cfg = _load_cfg(ctx)
    env_cfg = cfg.get("environments", {}).get(environment)
    if env_cfg is None:
        console.print(f"[red]Error:[/red] Unknown environment '{environment}'.")
        console.print(f"Available: {', '.join(cfg.get('environments', {}).keys())}")
        raise SystemExit(1)

    if require_access:
        _check_access(environment, env_cfg)

    return cfg, env_cfg


def _check_access(environment: str, env_cfg: dict) -> None:
    """Enforce environment access restrictions."""
    access = env_cfg.get("access", "open")
    if access != "restricted":
        return

    allowed = env_cfg.get("allowed_deployers", [])
    if not allowed:
        return

    from dds.utils.git import git_info
    info = git_info()
    deployer_email = info.get("email", "")

    if deployer_email not in allowed:
        console.print(
            f"[red]❌ Access denied:[/red] Environment [bold]{environment}[/bold] "
            f"is restricted to: {', '.join(allowed)}"
        )
        console.print(
            f"  Your git email: [bold]{deployer_email or '(not configured)'}[/bold]"
        )
        console.print(
            "  Contact a project admin if you need production access."
        )
        raise SystemExit(1)

    if True:
        console.print(
            f"  [dim]Access check: {deployer_email} ✓ ({environment})[/dim]"
        )


def _make_ctx(click_ctx: click.Context, environment: str, service: str) -> DeployContext:
    """Build a DeployContext for a named service, or exit if not found."""
    cfg, env_cfg = _load_env(click_ctx, environment)
    services = env_cfg.get("services", {})
    if service not in services:
        console.print(f"[red]Error:[/red] Unknown service '{service}'.")
        console.print(f"Available: {', '.join(services.keys())}")
        raise SystemExit(1)
    return DeployContext(service, services[service], env_cfg, cfg, verbose=click_ctx.obj["verbose"])


def _require_container(ctx: DeployContext, action: str) -> None:
    """Guard: exit if service is not a container-app."""
    if ctx.service_type != "container-app":
        console.print(f"[red]{action} is only supported for container-app services.[/red]")
        raise SystemExit(1)


@click.group()
@click.version_option(version=__version__, prog_name="dds")
@click.option("--config", "-c", default="dds.yaml", help="Path to dds.yaml config file.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
@click.pass_context
def main(ctx: click.Context, config: str, verbose: bool) -> None:
    """Daedalus Deployment System — cross-platform deployments."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("environment")
@click.option("--service", "-s", multiple=True, help="Deploy only specific service(s).")
@click.option("--dry-run", is_flag=True, help="Preview actions without executing.")
@click.option("--skip-preflight", is_flag=True, help="Skip preflight checks.")
@click.option("--skip-health", is_flag=True, help="Skip post-deploy health verification.")
@click.pass_context
def deploy(
    ctx: click.Context,
    environment: str,
    service: tuple[str, ...],
    dry_run: bool,
    skip_preflight: bool,
    skip_health: bool,
) -> None:
    """Deploy services to an environment."""
    cfg, env_cfg = _load_env(ctx, environment, require_access=not dry_run)

    if not skip_preflight and not dry_run:
        from dds.preflight import print_preflight, run_preflight

        if not print_preflight(run_preflight(cfg)):
            console.print("[red]Aborting. Use --skip-preflight to override.[/red]")
            raise SystemExit(1)

    services = env_cfg.get("services", {})
    targets = {k: v for k, v in services.items() if k in service} if service else services
    if not targets:
        console.print("[yellow]No services matched.[/yellow]")
        if service:
            console.print(f"Available: {', '.join(services.keys())}")
        raise SystemExit(1)

    from dds.deployers import dispatch
    from dds.providers import get_container_provider

    failed: list[str] = []
    for svc_name, svc_cfg in targets.items():
        deploy_ctx = DeployContext(svc_name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"])

        if dry_run:
            strategy = (
                svc_cfg.get("build_strategy", "acr")
                if deploy_ctx.service_type == "container-app"
                else ""
            )
            console.print(
                f"[dim]DRY RUN:[/dim] Would deploy [bold]{svc_name}[/bold] "
                f"(type: {deploy_ctx.service_type}"
                f"{f', strategy: {strategy}' if strategy else ''}"
                f", provider: {deploy_ctx.provider})"
            )
            continue

        try:
            dispatch(deploy_ctx)

            if (
                not skip_health
                and deploy_ctx.service_type == "container-app"
                and svc_cfg.get("health_path")
            ):
                provider = get_container_provider(deploy_ctx.provider)
                if not provider.health(deploy_ctx):
                    console.print(
                        f"[yellow]⚠️  {svc_name} deployed but health check failed. "
                        f"Consider: dds rollback {environment} -s {svc_name}[/yellow]"
                    )
                    failed.append(svc_name)
        except Exception as e:
            console.print(f"[red]❌ Deploy failed for {svc_name}: {e}[/red]")
            failed.append(svc_name)

    if failed:
        console.print(f"\n[red]⚠️  Failed services: {', '.join(failed)}[/red]")
        raise SystemExit(1)


@main.command()
@click.argument("environment")
@click.pass_context
def status(ctx: click.Context, environment: str) -> None:
    """Show deployment status for an environment."""
    cfg, env_cfg = _load_env(ctx, environment)
    from dds.deployers import show_status

    console.print(f"\n[bold]📊 Status: {environment}[/bold]\n")
    show_status(env_cfg, cfg, verbose=ctx.obj["verbose"])


@main.command()
@click.pass_context
def preflight(ctx: click.Context) -> None:
    """Run preflight checks without deploying."""
    cfg = load_config(ctx.obj["config_path"])
    from dds.preflight import print_preflight, run_preflight

    if not print_preflight(run_preflight(cfg)):
        raise SystemExit(1)


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to roll back.")
@click.option("--revision", "-r", default=None, help="Target revision (default: previous).")
@click.pass_context
def rollback(ctx: click.Context, environment: str, service: str, revision: str | None) -> None:
    """Roll back a service to a previous revision."""
    _load_env(ctx, environment, require_access=True)
    deploy_ctx = _make_ctx(ctx, environment, service)
    _require_container(deploy_ctx, "Rollback")

    from dds.providers import get_container_provider

    provider = get_container_provider(deploy_ctx.provider)
    if not provider.rollback(deploy_ctx, target_revision=revision):
        raise SystemExit(1)


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to show revisions for.")
@click.pass_context
def revisions(ctx: click.Context, environment: str, service: str) -> None:
    """Show revision history for a container app service."""
    deploy_ctx = _make_ctx(ctx, environment, service)
    _require_container(deploy_ctx, "Revisions")

    from dds.providers import get_container_provider

    provider = get_container_provider(deploy_ctx.provider)
    provider.revisions(deploy_ctx)


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to show logs for.")
@click.option("--follow", "-f", is_flag=True, help="Follow/stream logs in real-time.")
@click.option("--tail", "-n", default=100, help="Number of recent log lines (default: 100).")
@click.option("--system", "show_system", is_flag=True, help="Show system/platform logs.")
@click.pass_context
def logs(
    ctx: click.Context, environment: str, service: str, follow: bool, tail: int, show_system: bool
) -> None:
    """Tail or stream logs from a container app service."""
    deploy_ctx = _make_ctx(ctx, environment, service)
    _require_container(deploy_ctx, "Logs")

    from dds.providers import get_container_provider

    provider = get_container_provider(deploy_ctx.provider)
    provider.logs(deploy_ctx, follow=follow, tail=tail, system=show_system)


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to check health for.")
@click.pass_context
def health(ctx: click.Context, environment: str, service: str) -> None:
    """Run health checks on a deployed service."""
    deploy_ctx = _make_ctx(ctx, environment, service)
    _require_container(deploy_ctx, "Health checks")

    from dds.providers import get_container_provider

    provider = get_container_provider(deploy_ctx.provider)
    if not provider.health(deploy_ctx):
        raise SystemExit(1)


@main.command()
def init() -> None:
    """Create a dds.yaml config file in the current directory."""
    import os

    if os.path.exists("dds.yaml"):
        console.print("[yellow]dds.yaml already exists.[/yellow]")
        raise SystemExit(1)
    from dds.config import write_template

    write_template("dds.yaml")
    console.print("[green]Created dds.yaml[/green] — edit it for your project.")
