"""Deployment dispatchers."""

from __future__ import annotations

from typing import Any

from rich.console import Console

console = Console()


def dispatch(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Route a service deployment to the correct deployer."""
    svc_type = svc_cfg.get("type", "")

    if svc_type == "container-app":
        from dds.deployers.container import deploy_container_app
        deploy_container_app(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)
    elif svc_type == "static-site":
        from dds.deployers.static import deploy_static_site
        deploy_static_site(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)
    else:
        console.print(f"[red]Unknown service type:[/red] {svc_type}")
        raise SystemExit(1)


def show_status(
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for all services in an environment."""
    from dds.deployers.container import status_container_app
    from dds.deployers.static import status_static_site

    services = env_cfg.get("services", {})
    for name, svc_cfg in services.items():
        svc_type = svc_cfg.get("type", "")
        if svc_type == "container-app":
            status_container_app(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)
        elif svc_type == "static-site":
            status_static_site(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)
        else:
            console.print(f"[yellow]{name}:[/yellow] Unknown type '{svc_type}'")
