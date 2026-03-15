"""Container App deployer — build, push, and deploy to Azure Container Apps."""

from __future__ import annotations

from typing import Any

from rich.console import Console

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
    """Build, push, and deploy a container app."""
    registry = project_cfg.get("registry", "")
    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", name)
    dockerfile = svc_cfg.get("dockerfile", "Dockerfile")
    context = svc_cfg.get("context", ".")
    tag = svc_cfg.get("tag", "latest")
    image = f"{registry}/{project_cfg['project']}-{name}:{tag}"

    info = git_info()
    console.print(f"\n[bold blue]🚀 Deploying {name}[/bold blue] ({app_name})")
    console.print(f"  Image: {image}")
    console.print(f"  Git: {info['hash']} @ {info['branch']}")

    # Step 1: ACR Login
    registry_name = registry.split(".")[0]
    console.print("\n[yellow]📦 Logging into ACR...[/yellow]")
    az(f"acr login --name {registry_name}", verbose=verbose)

    # Step 2: Build
    console.print(f"\n[yellow]🔨 Building {name}...[/yellow]")
    build_args = svc_cfg.get("build_args", {})
    build_arg_str = " ".join(f"--build-arg {k}={v}" for k, v in build_args.items())
    az(
        f'docker build -f {dockerfile} -t {image} {build_arg_str} {context}',
        use_docker=True,
        verbose=verbose,
    )

    # Step 3: Push
    console.print(f"\n[yellow]📤 Pushing {name}...[/yellow]")
    az(f"docker push {image}", use_docker=True, verbose=verbose)

    # Step 4: Deploy
    console.print(f"\n[yellow]🚢 Deploying to Container App...[/yellow]")
    az(
        f"containerapp update --name {app_name} --resource-group {rg} "
        f"--image {image}",
        verbose=verbose,
    )

    # Step 5: Verify
    console.print(f"\n[green]✅ {name} deployed[/green]")


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
        status = props.get("runningStatus", "unknown")
        revision = props.get("latestRevisionName", "?")
        scale = props.get("template", {}).get("scale", {})
        console.print(
            f"  [bold]{name}[/bold] ({app_name}): "
            f"[green]{status}[/green] | "
            f"revision: {revision} | "
            f"scale: {scale.get('minReplicas', '?')}-{scale.get('maxReplicas', '?')}"
        )
    except Exception as e:
        console.print(f"  [bold]{name}[/bold] ({app_name}): [red]Error: {e}[/red]")
