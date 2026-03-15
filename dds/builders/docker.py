"""Docker image build strategies — local Docker or ACR remote build."""

from __future__ import annotations

import subprocess
from typing import Any

from rich.console import Console

from dds.utils.azure import az
from dds.utils.git import git_info

console = Console()


def build_and_push_local(
    image: str,
    dockerfile: str = "Dockerfile",
    context: str = ".",
    build_args: dict[str, str] | None = None,
    verbose: bool = False,
) -> None:
    """Build locally with Docker, then push to ACR.

    Requires Docker daemon running locally. Good for fast iteration
    when you have a beefy machine.
    """
    args_str = ""
    if build_args:
        args_str = " ".join(f"--build-arg {k}={v}" for k, v in build_args.items())

    console.print(f"[yellow]🔨 Building locally: {image}[/yellow]")
    cmd = f"docker build -f {dockerfile} -t {image} {args_str} {context}"
    if verbose:
        console.print(f"[dim]$ {cmd}[/dim]")

    result = subprocess.run(cmd, shell=True, capture_output=not verbose, text=True)
    if result.returncode != 0:
        console.print(f"[red]Docker build failed[/red]")
        if result.stderr:
            console.print(result.stderr)
        raise RuntimeError(f"Docker build failed for {image}")

    console.print(f"[yellow]📤 Pushing: {image}[/yellow]")
    result = subprocess.run(
        f"docker push {image}", shell=True, capture_output=not verbose, text=True
    )
    if result.returncode != 0:
        console.print(f"[red]Docker push failed[/red]")
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
    """Build remotely on Azure Container Registry.

    No local Docker needed — ACR does the build. This is the preferred
    method for CI-less workflows (Dooley's law: immediate feedback or bust).
    """
    registry_name = registry.split(".")[0]

    args_str = ""
    if build_args:
        args_str = " ".join(f"--build-arg {k}={v}" for k, v in build_args.items())

    console.print(f"[yellow]🔨 ACR build: {image_tag}[/yellow]")
    console.print(f"  Registry: {registry_name}")
    console.print(f"  Dockerfile: {dockerfile}")
    console.print(f"  Platform: {platform}")

    az(
        f"acr build --registry {registry_name} "
        f"--image {image_tag} "
        f"--file {dockerfile} "
        f"--platform {platform} "
        f"{args_str} {context}",
        verbose=verbose,
    )


def resolve_image_tag(
    name: str,
    project_cfg: dict[str, Any],
    svc_cfg: dict[str, Any],
) -> str:
    """Build the full image tag for a service.

    Uses git hash for unique tags, falls back to 'latest'.
    """
    registry = project_cfg.get("registry", "")
    project = project_cfg.get("project", "")
    tag = svc_cfg.get("tag", None)

    if tag is None:
        info = git_info()
        tag = info["hash"] if info["hash"] != "unknown" else "latest"

    return f"{registry}/{project}-{name}:{tag}"
