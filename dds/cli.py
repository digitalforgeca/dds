"""DDS CLI — cross-platform deployment commands."""

import click
from rich.console import Console

from dds import __version__
from dds.config import load_config

console = Console()


def _load_and_validate(ctx: click.Context, environment: str) -> tuple[dict, dict]:
    """Load config and validate environment exists. Returns (full_cfg, env_cfg)."""
    cfg = load_config(ctx.obj["config_path"])
    if cfg is None:
        console.print("[red]Error:[/red] No dds.yaml found. Run 'dds init' to create one.")
        raise SystemExit(1)

    env_cfg = cfg.get("environments", {}).get(environment)
    if env_cfg is None:
        console.print(f"[red]Error:[/red] Unknown environment '{environment}'.")
        console.print(f"Available: {', '.join(cfg.get('environments', {}).keys())}")
        raise SystemExit(1)

    return cfg, env_cfg


def _get_service(env_cfg: dict, cfg: dict, service_name: str) -> tuple[str, dict]:
    """Get a single service config by name."""
    services = env_cfg.get("services", {})
    if service_name not in services:
        console.print(f"[red]Error:[/red] Unknown service '{service_name}'.")
        console.print(f"Available: {', '.join(services.keys())}")
        raise SystemExit(1)
    return service_name, services[service_name]


@click.group()
@click.version_option(version=__version__, prog_name="dds")
@click.option("--config", "-c", default="dds.yaml", help="Path to dds.yaml config file.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
@click.pass_context
def main(ctx: click.Context, config: str, verbose: bool) -> None:
    """Daedalus Deployment System — cross-platform Azure deployments."""
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
    cfg, env_cfg = _load_and_validate(ctx, environment)

    # Preflight checks
    if not skip_preflight and not dry_run:
        from dds.preflight import print_preflight, run_preflight

        results = run_preflight(cfg)
        if not print_preflight(results):
            console.print("[red]Aborting deploy due to failed preflight checks.[/red]")
            console.print("Use --skip-preflight to override.")
            raise SystemExit(1)

    services = env_cfg.get("services", {})
    targets = {k: v for k, v in services.items() if k in service} if service else services

    if not targets:
        console.print("[yellow]No services matched.[/yellow]")
        if service:
            console.print(f"Available services: {', '.join(services.keys())}")
        raise SystemExit(1)

    from dds.deployers import dispatch

    failed: list[str] = []
    for svc_name, svc_cfg in targets.items():
        if dry_run:
            svc_type = svc_cfg.get("type", "?")
            strategy = svc_cfg.get("build_strategy", "acr") if svc_type == "container-app" else ""
            console.print(
                f"[dim]DRY RUN:[/dim] Would deploy [bold]{svc_name}[/bold] "
                f"(type: {svc_type}{f', strategy: {strategy}' if strategy else ''})"
            )
            continue

        try:
            dispatch(svc_name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"])

            # Post-deploy health check for container apps
            if (
                not skip_health
                and svc_cfg.get("type") == "container-app"
                and svc_cfg.get("health_path")
            ):
                from dds.health import verify_container_health

                healthy = verify_container_health(
                    svc_name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"]
                )
                if not healthy:
                    console.print(
                        f"[yellow]⚠️  {svc_name} deployed but health check failed. "
                        f"Consider rolling back with 'dds rollback {environment} -s {svc_name}'[/yellow]"
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
    cfg, env_cfg = _load_and_validate(ctx, environment)

    from dds.deployers import show_status

    console.print(f"\n[bold]📊 Status: {environment}[/bold]\n")
    show_status(env_cfg, cfg, verbose=ctx.obj["verbose"])


@main.command()
@click.pass_context
def preflight(ctx: click.Context) -> None:
    """Run preflight checks without deploying."""
    cfg = load_config(ctx.obj["config_path"])

    from dds.preflight import print_preflight, run_preflight

    results = run_preflight(cfg)
    passed = print_preflight(results)
    if not passed:
        raise SystemExit(1)


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to roll back.")
@click.option("--revision", "-r", default=None, help="Target revision (default: previous).")
@click.pass_context
def rollback(
    ctx: click.Context,
    environment: str,
    service: str,
    revision: str | None,
) -> None:
    """Roll back a service to a previous revision."""
    cfg, env_cfg = _load_and_validate(ctx, environment)
    svc_name, svc_cfg = _get_service(env_cfg, cfg, service)

    if svc_cfg.get("type") != "container-app":
        console.print("[red]Rollback is only supported for container-app services.[/red]")
        raise SystemExit(1)

    from dds.rollback import rollback_container_app

    success = rollback_container_app(
        svc_name, svc_cfg, env_cfg, cfg,
        target_revision=revision,
        verbose=ctx.obj["verbose"],
    )
    if not success:
        raise SystemExit(1)


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to show revisions for.")
@click.pass_context
def revisions(ctx: click.Context, environment: str, service: str) -> None:
    """Show revision history for a container app service."""
    cfg, env_cfg = _load_and_validate(ctx, environment)
    svc_name, svc_cfg = _get_service(env_cfg, cfg, service)

    if svc_cfg.get("type") != "container-app":
        console.print("[red]Revisions are only available for container-app services.[/red]")
        raise SystemExit(1)

    from dds.rollback import show_revisions

    show_revisions(svc_name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"])


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to show logs for.")
@click.option("--follow", "-f", is_flag=True, help="Follow/stream logs in real-time.")
@click.option("--tail", "-n", default=100, help="Number of recent log lines (default: 100).")
@click.option("--system", "show_system", is_flag=True, help="Show system/platform logs.")
@click.pass_context
def logs(
    ctx: click.Context,
    environment: str,
    service: str,
    follow: bool,
    tail: int,
    show_system: bool,
) -> None:
    """Tail or stream logs from a container app service."""
    cfg, env_cfg = _load_and_validate(ctx, environment)
    svc_name, svc_cfg = _get_service(env_cfg, cfg, service)

    if svc_cfg.get("type") != "container-app":
        console.print("[red]Logs are only available for container-app services.[/red]")
        raise SystemExit(1)

    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", svc_name)

    from dds.logs import system_logs, tail_logs

    if show_system:
        system_logs(app_name, rg, tail=tail, verbose=ctx.obj["verbose"])
    else:
        tail_logs(app_name, rg, follow=follow, tail=tail, verbose=ctx.obj["verbose"])


@main.command()
@click.argument("environment")
@click.option("--service", "-s", required=True, help="Service to check health for.")
@click.pass_context
def health(ctx: click.Context, environment: str, service: str) -> None:
    """Run health checks on a deployed service."""
    cfg, env_cfg = _load_and_validate(ctx, environment)
    svc_name, svc_cfg = _get_service(env_cfg, cfg, service)

    if svc_cfg.get("type") != "container-app":
        console.print("[red]Health checks are only available for container-app services.[/red]")
        raise SystemExit(1)

    from dds.health import verify_container_health

    healthy = verify_container_health(
        svc_name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"]
    )
    if not healthy:
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
