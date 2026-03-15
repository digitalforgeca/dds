"""Deployment dispatchers."""

from __future__ import annotations

from typing import Any

from rich.console import Console

console = Console()

# Service type → (deploy_func, status_func)
_DEPLOYER_REGISTRY: dict[str, tuple[str, str, str]] = {
    "container-app": ("dds.deployers.container", "deploy_container_app", "status_container_app"),
    "static-site": ("dds.deployers.static", "deploy_static_site", "status_static_site"),
    "database": ("dds.deployers.database", "provision_database", "status_database"),
}


def _import_func(module_path: str, func_name: str) -> Any:
    """Lazy-import a deployer function."""
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)


def dispatch(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Route a service deployment to the correct deployer."""
    svc_type = svc_cfg.get("type", "")

    entry = _DEPLOYER_REGISTRY.get(svc_type)
    if entry is None:
        console.print(f"[red]Unknown service type:[/red] {svc_type}")
        console.print(f"Available types: {', '.join(_DEPLOYER_REGISTRY.keys())}")
        raise SystemExit(1)

    module_path, deploy_func_name, _ = entry
    deploy_func = _import_func(module_path, deploy_func_name)
    deploy_func(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)


def show_status(
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for all services in an environment."""
    services = env_cfg.get("services", {})
    for name, svc_cfg in services.items():
        svc_type = svc_cfg.get("type", "")
        entry = _DEPLOYER_REGISTRY.get(svc_type)
        if entry is None:
            console.print(f"[yellow]{name}:[/yellow] Unknown type '{svc_type}'")
            continue

        module_path, _, status_func_name = entry
        try:
            status_func = _import_func(module_path, status_func_name)
            status_func(name, svc_cfg, env_cfg, project_cfg, verbose=verbose)
        except Exception as e:
            console.print(f"[yellow]{name}:[/yellow] Status check failed ({e})")
