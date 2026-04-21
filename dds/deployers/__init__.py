"""Deployment dispatchers — routes to provider implementations."""

from __future__ import annotations

from typing import Any

from dds.console import console
from dds.context import DeployContext
from dds.providers import (
    get_container_provider,
    get_database_provider,
    get_static_provider,
    get_swa_provider,
)

# Service types that DDS knows about
_KNOWN_TYPES = {"container-app", "static-site", "swa", "database"}


def dispatch(ctx: DeployContext) -> None:
    """Route a service deployment to the correct provider."""
    svc_type = ctx.service_type
    if svc_type not in _KNOWN_TYPES:
        console.print(f"[red]Unknown service type:[/red] {svc_type}")
        console.print(f"Available types: {', '.join(sorted(_KNOWN_TYPES))}")
        raise SystemExit(1)

    provider_name = ctx.provider

    if svc_type == "container-app":
        provider = get_container_provider(provider_name)
        image = provider.build(ctx)
        provider.deploy(ctx, image)
    elif svc_type == "static-site":
        provider = get_static_provider(provider_name)
        provider.deploy(ctx)
    elif svc_type == "swa":
        provider = get_swa_provider(provider_name)
        provider.deploy(ctx)
    elif svc_type == "database":
        provider = get_database_provider(provider_name)
        provider.provision(ctx)


def show_status(
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for all services in an environment."""
    services = env_cfg.get("services", {})
    for name, svc_cfg in services.items():
        ctx = DeployContext(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)
        svc_type = ctx.service_type

        if svc_type not in _KNOWN_TYPES:
            console.print(f"[yellow]{name}:[/yellow] Unknown type '{svc_type}'")
            continue

        provider_name = ctx.provider
        try:
            if svc_type == "container-app":
                get_container_provider(provider_name).status(ctx)
            elif svc_type == "static-site":
                get_static_provider(provider_name).status(ctx)
            elif svc_type == "swa":
                get_swa_provider(provider_name).status(ctx)
            elif svc_type == "database":
                get_database_provider(provider_name).status(ctx)
        except Exception as e:
            console.print(f"[yellow]{name}:[/yellow] Status check failed ({e})")
