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
@click.pass_context
def deploy(ctx: click.Context, environment: str, service: tuple[str, ...], dry_run: bool) -> None:
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

    services = env_cfg.get("services", {})
    targets = {k: v for k, v in services.items() if k in service} if service else services

    if not targets:
        console.print("[yellow]No services matched.[/yellow]")
        raise SystemExit(1)

    from dds.deployers import dispatch

    for name, svc_cfg in targets.items():
        if dry_run:
            console.print(f"[dim]DRY RUN:[/dim] Would deploy [bold]{name}[/bold] ({svc_cfg.get('type', '?')})")
        else:
            dispatch(name, svc_cfg, env_cfg, cfg, verbose=ctx.obj["verbose"])


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

    show_status(env_cfg, cfg, verbose=ctx.obj["verbose"])


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
