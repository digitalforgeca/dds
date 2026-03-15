"""Container App deployer — build, push, and deploy to Azure Container Apps."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from dds.builders.docker import build_acr, build_and_push_local, resolve_image_tag
from dds.utils.azure import az, az_json
from dds.utils.git import git_info

console = Console()


def deploy_container_app(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Build, push, and deploy a container app.

    Supports two build strategies:
    - 'acr' (default): Remote build on Azure Container Registry
    - 'local': Local Docker build + push

    Config keys:
        type: container-app
        name: <container-app-name>
        dockerfile: <path-to-Dockerfile>
        context: <build-context>
        build_strategy: acr | local (default: acr)
        build_args: {KEY: VALUE, ...}
        env: {KEY: VALUE, ...}  # runtime env vars
        tag: <image-tag>  # default: git short hash
        port: <int>
        min_replicas: <int>
        max_replicas: <int>
        health_path: <string>
        secrets: [{name: ..., value: ...}]
    """
    registry = project_cfg.get("registry", "")
    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", name)
    dockerfile = svc_cfg.get("dockerfile", "Dockerfile")
    context = svc_cfg.get("context", ".")
    strategy = svc_cfg.get("build_strategy", "acr")

    image = resolve_image_tag(name, project_cfg, svc_cfg)
    # For ACR builds, the image_tag is relative (no registry prefix)
    image_tag = image.split("/", 1)[1] if "/" in image else image

    info = git_info()
    console.print(f"\n[bold blue]🚀 Deploying {name}[/bold blue] → {app_name}")
    console.print(f"  Image: {image}")
    console.print(f"  Strategy: {strategy}")
    console.print(f"  Git: {info['hash']} @ {info['branch']}")

    # Merge build args — always inject CACHE_BUST for cache-busting
    build_args = dict(svc_cfg.get("build_args", {}))
    build_args.setdefault("CACHE_BUST", info["build_time"])
    build_args.setdefault("GIT_HASH", info["hash"])

    # Step 1: Build
    if strategy == "local":
        registry_name = registry.split(".")[0]
        console.print(f"\n[yellow]📦 Logging into ACR ({registry_name})...[/yellow]")
        az(f"acr login --name {registry_name}", verbose=verbose)
        build_and_push_local(
            image=image,
            dockerfile=dockerfile,
            context=context,
            build_args=build_args,
            verbose=verbose,
        )
    else:
        # ACR remote build (default)
        build_acr(
            registry=registry,
            image_tag=image_tag,
            dockerfile=dockerfile,
            context=context,
            build_args=build_args,
            verbose=verbose,
        )

    # Step 2: Deploy to Container App
    console.print(f"\n[yellow]🚢 Updating Container App: {app_name}...[/yellow]")
    update_cmd = (
        f"containerapp update --name {app_name} --resource-group {rg} "
        f"--image {image}"
    )

    # Set runtime environment variables if specified
    env_vars = svc_cfg.get("env", {})
    if env_vars:
        env_str = " ".join(f"{k}={v}" for k, v in env_vars.items())
        update_cmd += f" --set-env-vars {env_str}"

    az(update_cmd, verbose=verbose)

    # Step 3: Verify
    console.print(f"\n[green]✅ {name} deployed → {app_name}[/green]")


def status_container_app(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Show status for a container app."""
    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", name)

    try:
        data = az_json(f"containerapp show --name {app_name} --resource-group {rg}")
        props = data.get("properties", {})
        running = props.get("runningStatus", "unknown")
        revision = props.get("latestRevisionName", "?")
        template = props.get("template", {})
        scale = template.get("scale", {})
        containers = template.get("containers", [{}])
        current_image = containers[0].get("image", "?") if containers else "?"

        console.print(
            f"  [bold]{name}[/bold] ({app_name}): "
            f"[green]{running}[/green] | "
            f"image: {current_image} | "
            f"revision: {revision} | "
            f"scale: {scale.get('minReplicas', '?')}-{scale.get('maxReplicas', '?')}"
        )
    except Exception as e:
        console.print(f"  [bold]{name}[/bold] ({app_name}): [red]Error: {e}[/red]")
