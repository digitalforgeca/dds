"""Docker image build strategies — local Docker build/push.

ACR-specific remote builds have moved to dds.providers.azure.container.
This module retains the generic local Docker build and image tag resolution.
"""

from __future__ import annotations

from typing import Any

from dds.console import console
from dds.utils.git import git_info
from dds.utils.shell import run_cmd


def build_and_push_local(
    image: str,
    dockerfile: str = "Dockerfile",
    context: str = ".",
    build_args: dict[str, str] | None = None,
    verbose: bool = False,
) -> None:
    """Build locally with Docker, then push to a registry."""
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
    """Format build args dict into Docker --build-arg flags.

    Values containing spaces or shell-special characters are quoted to prevent
    word-splitting when the command string is passed to the shell.
    """
    if not build_args:
        return ""
    import shlex

    return " ".join(
        f"--build-arg {k}={shlex.quote(str(v))}" for k, v in build_args.items()
    )
