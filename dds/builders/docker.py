"""Docker image build strategies — local Docker or ACR remote build."""

from __future__ import annotations

from typing import Any

from dds.console import console
from dds.utils.azure import az, run_cmd
from dds.utils.git import git_info


def build_and_push_local(
    image: str,
    dockerfile: str = "Dockerfile",
    context: str = ".",
    build_args: dict[str, str] | None = None,
    verbose: bool = False,
) -> None:
    """Build locally with Docker, then push to ACR."""
    args_str = _build_args_str(build_args)

    console.print(f"[yellow]🔨 Building locally: {image}[/yellow]")
    result = run_cmd(
        f"docker build -f {dockerfile} -t {image} {args_str} {context}",
        verbose=verbose,
    )
    if result.returncode != 0:
        console.print("[red]Docker build failed[/red]")
        if result.stderr:
            console.print(result.stderr[-500:])
        raise RuntimeError(f"Docker build failed for {image}")

    console.print(f"[yellow]📤 Pushing: {image}[/yellow]")
    result = run_cmd(f"docker push {image}", verbose=verbose)
    if result.returncode != 0:
        console.print("[red]Docker push failed[/red]")
        raise RuntimeError(f"Docker push failed for {image}")


def build_acr(
    registry: str,
    image_tag: str,
    dockerfile: str = "Dockerfile",
    context: str = ".",
    build_args: dict[str, str] | None = None,
    platform: str = "linux/amd64",
    verbose: bool = False,
) -> None:
    """Build remotely on Azure Container Registry."""
    registry_name = registry.split(".")[0]
    args_str = _build_args_str(build_args)

    console.print(f"[yellow]🔨 ACR build: {image_tag}[/yellow]")
    console.print(f"  Registry: {registry_name} | Dockerfile: {dockerfile} | Platform: {platform}")

    az(
        f"acr build --registry {registry_name} "
        f"--image {image_tag} --file {dockerfile} "
        f"--platform {platform} {args_str} {context}",
        verbose=verbose,
    )


def resolve_image_tag(
    name: str,
    project_cfg: dict[str, Any],
    svc_cfg: dict[str, Any],
) -> str:
    """Build the full image tag for a service (git hash or explicit)."""
    registry = project_cfg.get("registry", "")
    project = project_cfg.get("project", "")
    tag = svc_cfg.get("tag", None)

    if tag is None:
        info = git_info()
        tag = info["hash"] if info["hash"] != "unknown" else "latest"

    return f"{registry}/{project}-{name}:{tag}"


def _build_args_str(build_args: dict[str, str] | None) -> str:
    """Format build args dict into Docker --build-arg flags."""
    if not build_args:
        return ""
    return " ".join(f"--build-arg {k}={v}" for k, v in build_args.items())
