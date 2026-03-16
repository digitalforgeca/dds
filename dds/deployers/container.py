"""Container App deployer — build, push, and deploy to Azure Container Apps."""

from __future__ import annotations

from dds.builders.docker import build_acr, build_and_push_local, resolve_image_tag
from dds.console import console
from dds.context import DeployContext
from dds.secrets import resolve_secrets
from dds.utils.azure import az, az_json
from dds.utils.git import git_info


def deploy_container_app(ctx: DeployContext) -> None:
    """Build, push, and deploy a container app."""
    dockerfile = ctx.svc_cfg.get("dockerfile", "Dockerfile")
    context = ctx.svc_cfg.get("context", ".")
    strategy = ctx.svc_cfg.get("build_strategy", "acr")

    image = resolve_image_tag(ctx.name, ctx.project_cfg, ctx.svc_cfg)
    image_tag = image.split("/", 1)[1] if "/" in image else image

    info = git_info()
    console.print(f"\n[bold blue]🚀 Deploying {ctx.name}[/bold blue] → {ctx.app_name}")
    console.print(
        f"  Image: {image} | Strategy: {strategy} | Git: {info['hash']} @ {info['branch']}"
    )

    # Build args — always inject CACHE_BUST + GIT_HASH
    build_args = dict(ctx.svc_cfg.get("build_args", {}))
    build_args.setdefault("CACHE_BUST", info["build_time"])
    build_args.setdefault("GIT_HASH", info["hash"])

    # Step 1: Build
    if strategy == "local":
        console.print(f"\n[yellow]📦 Logging into ACR ({ctx.registry_name})...[/yellow]")
        az(f"acr login --name {ctx.registry_name}", verbose=ctx.verbose)
        build_and_push_local(
            image=image,
            dockerfile=dockerfile,
            context=context,
            build_args=build_args,
            verbose=ctx.verbose,
        )
    else:
        build_acr(
            registry=ctx.registry,
            image_tag=image_tag,
            dockerfile=dockerfile,
            context=context,
            build_args=build_args,
            verbose=ctx.verbose,
        )

    # Step 2: Resolve secrets + env vars
    all_env = resolve_secrets(ctx.svc_cfg, ctx.env_cfg, ctx.project_cfg, verbose=ctx.verbose)

    # Step 3: Update Container App
    console.print(f"\n[yellow]🚢 Updating Container App: {ctx.app_name}...[/yellow]")
    update_cmd = (
        f"containerapp update --name {ctx.app_name} "
        f"--resource-group {ctx.resource_group} --image {image}"
    )
    if all_env:
        env_str = " ".join(f"{k}={v}" for k, v in all_env.items())
        update_cmd += f" --set-env-vars {env_str}"
    az(update_cmd, verbose=ctx.verbose)

    console.print(f"\n[green]✅ {ctx.name} deployed → {ctx.app_name}[/green]")


def status_container_app(ctx: DeployContext) -> None:
    """Show status for a container app."""
    try:
        data = az_json(
            f"containerapp show --name {ctx.app_name} --resource-group {ctx.resource_group}"
        )
        props = data.get("properties", {})
        template = props.get("template", {})
        scale = template.get("scale", {})
        containers = template.get("containers", [{}])
        current_image = containers[0].get("image", "?") if containers else "?"

        console.print(
            f"  [bold]{ctx.name}[/bold] ({ctx.app_name}): "
            f"[green]{props.get('runningStatus', '?')}[/green] | "
            f"image: {current_image} | "
            f"revision: {props.get('latestRevisionName', '?')} | "
            f"scale: {scale.get('minReplicas', '?')}-{scale.get('maxReplicas', '?')}"
        )
    except Exception as e:
        console.print(f"  [bold]{ctx.name}[/bold] ({ctx.app_name}): [red]Error: {e}[/red]")
