"""DDS CLI — cross-platform deployment commands."""

import click
from rich.console import Console

from dds import __version__
from dds.config import load_config

console = Console()


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
@click.pass_context
def deploy(
    ctx: click.Context,
    environment: str,
    service: tuple[str, ...],
    dry_run: bool,
    skip_preflight: bool,
) -> None:
    """Deploy services to an environment."""
    cfg = load_config(ctx.obj["config_path"])
    if cfg is None:
        console.print("[red]Error:[/red] No dds.yaml found. Run 'dds init' to create one.")
        raise SystemExit(1)

    env_cfg = cfg.get("environments", {}).get(environment)
    if env_cfg is None:
        console.print(f"[red]Error:[/red] Unknown environment '{environment}'.")
        console.print(f"Available: {', '.join(cfg.get('environments', {}).keys())}")
        raise SystemExit(1)

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

    for svc_name, svc_cfg in targets.items():
        if dry_run:
            svc_type = svc_cfg.get("type", "?")
            strategy = svc_cfg.get("build_strategy", "acr") if svc_type == "container-app" else ""
            console.print(
                f"[dim]DRY RUN:[/dim] Would deploy [bold]{svc_name}[/bold] "
                f"(type: {svc_type}{f', strategy: {strategy}' if strategy else ''})"
            )
        else:
            dispatch(svc_name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"])


@main.command()
@click.argument("environment")
@click.pass_context
def status(ctx: click.Context, environment: str) -> None:
    """Show deployment status for an environment."""
    cfg = load_config(ctx.obj["config_path"])
    if cfg is None:
        console.print("[red]Error:[/red] No dds.yaml found.")
        raise SystemExit(1)

    env_cfg = cfg.get("environments", {}).get(environment)
    if env_cfg is None:
        console.print(f"[red]Error:[/red] Unknown environment '{environment}'.")
        raise SystemExit(1)

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
def init() -> None:
    """Create a dds.yaml config file in the current directory."""
    import os

    if os.path.exists("dds.yaml"):
        console.print("[yellow]dds.yaml already exists.[/yellow]")
        raise SystemExit(1)

    from dds.config import write_template

    write_template("dds.yaml")
    console.print("[green]Created dds.yaml[/green] — edit it for your project.")
