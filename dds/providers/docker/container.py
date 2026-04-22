"""Docker/SSH container provider — deploy via docker compose over SSH."""

from __future__ import annotations

import subprocess

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import ContainerProvider
from dds.providers.docker.utils import (
    resolve_compose_file,
    resolve_compose_project_dir,
    resolve_host,
    ssh,
)
from dds.utils.shell import run_cmd


class DockerContainerProvider(ContainerProvider):
    """Deploy containers to a Docker host via SSH + docker compose."""

    def build(self, ctx: DeployContext) -> str:
        """Build a container image.

        For Docker provider, supports three strategies:
        - 'remote' (default): build on the remote host via `docker compose build`
        - 'local': build locally, push to registry, pull on remote
        - 'registry': skip build, just pull a pre-built image on remote
        """
        strategy = ctx.svc_cfg.get("build_strategy", "remote")
        host = resolve_host(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)

        if strategy == "local":
            # Build locally, push to registry, return image tag
            image = self._resolve_image(ctx)
            from dds.builders.docker import build_and_push_local
            from dds.utils.git import git_info

            info = git_info()
            build_args = dict(ctx.svc_cfg.get("build_args", {}))
            build_args.setdefault("CACHE_BUST", info["build_time"])
            build_args.setdefault("GIT_HASH", info["hash"])

            dockerfile = ctx.svc_cfg.get("dockerfile", "Dockerfile")
            context = ctx.svc_cfg.get("context", ".")

            console.print(f"\n[bold blue]🚀 Building {ctx.name}[/bold blue] (local → push → pull)")
            build_and_push_local(image, dockerfile, context, build_args, ctx.verbose)
            return image

        elif strategy == "registry":
            # No build — just return the image tag for pull
            image = self._resolve_image(ctx)
            console.print(
                f"\n[bold blue]🚀 Deploying {ctx.name}[/bold blue] (pull from registry)"
            )
            return image

        else:
            # Remote build via docker compose build on the host
            compose_file = resolve_compose_file(ctx)
            project_dir = resolve_compose_project_dir(ctx)

            console.print(
                f"\n[bold blue]🚀 Building {ctx.name}[/bold blue] (remote on {host})"
            )

            cd_prefix = f"cd {project_dir} && " if project_dir else ""
            ssh(
                host,
                f"{cd_prefix}docker compose -f {compose_file} build {service_name}",
                verbose=ctx.verbose,
            )
            return f"compose:{service_name}"  # Sentinel — compose manages the image

    def deploy(self, ctx: DeployContext, image: str) -> None:
        """Deploy a container to the Docker host."""
        host = resolve_host(ctx)
        compose_file = resolve_compose_file(ctx)
        project_dir = resolve_compose_project_dir(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)
        cd_prefix = f"cd {project_dir} && " if project_dir else ""

        strategy = ctx.svc_cfg.get("build_strategy", "remote")

        if strategy in ("local", "registry"):
            # Pull the image on the remote host first
            registry = ctx.project_cfg.get("registry", "")
            if registry:
                console.print(f"[yellow]📦 Logging into registry on {host}...[/yellow]")
                ssh(host, f"docker login {registry}", verbose=ctx.verbose)

            console.print(f"[yellow]📥 Pulling {image} on {host}...[/yellow]")
            ssh(host, f"docker pull {image}", verbose=ctx.verbose)

        console.print(f"[yellow]🚢 Starting {service_name} on {host}...[/yellow]")
        ssh(
            host,
            f"{cd_prefix}docker compose -f {compose_file} up -d {service_name}",
            verbose=ctx.verbose,
        )

        console.print(f"\n[green]✅ {ctx.name} deployed on {host}[/green]")

    def status(self, ctx: DeployContext) -> None:
        """Show status for a container on the Docker host."""
        host = resolve_host(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)
        compose_file = resolve_compose_file(ctx)
        project_dir = resolve_compose_project_dir(ctx)
        cd_prefix = f"cd {project_dir} && " if project_dir else ""

        try:
            output = ssh(
                host,
                f"{cd_prefix}docker compose -f {compose_file} ps {service_name} --format json",
                verbose=ctx.verbose,
                capture=True,
            )
            if output:
                import json

                # docker compose ps --format json may return one object per line
                lines = [line for line in output.strip().split("\n") if line.strip()]
                for line in lines:
                    data = json.loads(line)
                    state = data.get("State", "unknown")
                    status_str = data.get("Status", "")
                    image = data.get("Image", "?")
                    color = "green" if state == "running" else "red"
                    console.print(
                        f"  [bold]{ctx.name}[/bold] ({service_name}): "
                        f"[{color}]{state}[/{color}] | {status_str} | image: {image}"
                    )
            else:
                console.print(
                    f"  [bold]{ctx.name}[/bold] ({service_name}): [dim]not found[/dim]"
                )
        except Exception as e:
            console.print(
                f"  [bold]{ctx.name}[/bold] ({service_name}): [red]Error: {e}[/red]"
            )

    def rollback(self, ctx: DeployContext, target_revision: str | None = None) -> bool:
        """Rollback a container to its previous image.

        Docker Compose doesn't have built-in revision tracking like Azure Container Apps.
        Strategy: if a previous image tag is specified, pull and restart with it.
        Otherwise, `docker compose down && docker compose up -d` to restart from the
        last-known image in the compose file.
        """
        host = resolve_host(ctx)
        compose_file = resolve_compose_file(ctx)
        project_dir = resolve_compose_project_dir(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)
        cd_prefix = f"cd {project_dir} && " if project_dir else ""

        console.print(f"\n[bold yellow]⏪ Rolling back: {service_name} on {host}[/bold yellow]")

        if target_revision:
            # Pull specific image and restart
            console.print(f"  Target image: {target_revision}")
            ssh(host, f"docker pull {target_revision}", verbose=ctx.verbose)
            # Stop the service, then start with the new image
            ssh(
                host,
                f"{cd_prefix}docker compose -f {compose_file} stop {service_name}",
                verbose=ctx.verbose,
            )
            ssh(
                host,
                f"{cd_prefix}docker compose -f {compose_file} up -d {service_name}",
                verbose=ctx.verbose,
            )
        else:
            # No target — restart the service (pulls whatever compose file defines)
            console.print("  No target revision — restarting service from compose definition")
            ssh(
                host,
                f"{cd_prefix}docker compose -f {compose_file} down {service_name} && "
                f"{cd_prefix}docker compose -f {compose_file} up -d {service_name}",
                verbose=ctx.verbose,
            )

        console.print(f"\n[green]✅ Rolled back {service_name} on {host}[/green]")
        return True

    def revisions(self, ctx: DeployContext) -> None:
        """Show image history for a container on the Docker host."""
        host = resolve_host(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)

        console.print(f"\n[bold]📜 Image history: {service_name} on {host}[/bold]\n")

        try:
            # Show local images for this service's image name
            output = ssh(
                host,
                f"docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}}  {{{{.CreatedAt}}}}  {{{{.Size}}}}' "
                f"| head -20",
                verbose=ctx.verbose,
                capture=True,
            )
            if output:
                for line in output.strip().split("\n"):
                    console.print(f"  {line}")
            else:
                console.print("  [dim]No images found[/dim]")
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

        console.print()

    def logs(
        self,
        ctx: DeployContext,
        follow: bool = False,
        tail: int = 100,
        system: bool = False,
    ) -> None:
        """Tail logs from a container on the Docker host."""
        host = resolve_host(ctx)
        compose_file = resolve_compose_file(ctx)
        project_dir = resolve_compose_project_dir(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)
        cd_prefix = f"cd {project_dir} && " if project_dir else ""

        label = "📋 Logs" if not system else "⚙️  System events"
        console.print(f"[bold]{label}: {service_name} on {host}[/bold]")

        if system:
            # Docker events for the container
            try:
                output = ssh(
                    host,
                    f"docker events --filter container={service_name} --since 1h --until now "
                    f"2>/dev/null | tail -{tail}",
                    verbose=ctx.verbose,
                    capture=True,
                )
                if output:
                    for line in output.strip().split("\n"):
                        if line.strip():
                            console.print(line)
                else:
                    console.print("[dim]No recent events[/dim]")
            except Exception:
                console.print("[dim]No events available[/dim]")
            return

        follow_flag = "-f" if follow else ""
        cmd = (
            f"{cd_prefix}docker compose -f {compose_file} logs "
            f"--tail {tail} {follow_flag} {service_name}"
        )

        if follow:
            console.print("[dim]Following logs... (Ctrl+C to stop)[/dim]\n")
            try:
                full_cmd = f"ssh -o BatchMode=yes {host} {cmd!r}"
                subprocess.run(full_cmd, shell=True)
            except KeyboardInterrupt:
                console.print("\n[dim]Log stream stopped.[/dim]")
        else:
            try:
                output = ssh(host, cmd, verbose=ctx.verbose, capture=True)
                if output:
                    for line in output.strip().split("\n"):
                        if line.strip():
                            console.print(line)
            except Exception as e:
                console.print(f"[red]Failed to fetch logs: {e}[/red]")

    def health(self, ctx: DeployContext, max_retries: int = 5, retry_delay: float = 6.0) -> bool:
        """Verify a container is healthy on the Docker host."""
        import time
        import urllib.error
        import urllib.request

        host = resolve_host(ctx)
        service_name = ctx.svc_cfg.get("compose_service", ctx.name)
        health_path = ctx.svc_cfg.get("health_path", "")
        health_url = ctx.svc_cfg.get("health_url", "")  # Full URL override

        console.print(f"\n[yellow]🏥 Verifying health: {service_name} on {host}...[/yellow]")

        for attempt in range(1, max_retries + 1):
            try:
                # Check container is running
                output = ssh(
                    host,
                    f"docker inspect --format '{{{{.State.Status}}}}' {service_name} 2>/dev/null || echo unknown",
                    verbose=ctx.verbose,
                    capture=True,
                )
                state = output.strip().strip("'\"")

                if state != "running":
                    if attempt < max_retries:
                        console.print(
                            f"  [dim]Attempt {attempt}/{max_retries}: "
                            f"state={state}, retrying in {retry_delay}s...[/dim]"
                        )
                        time.sleep(retry_delay)
                        continue
                    console.print(f"  [red]❌ Container not running (state: {state})[/red]")
                    return False

                console.print(f"  ✅ Running")

                # HTTP health check if configured
                url = health_url
                if not url and health_path:
                    # Try to determine the URL from port mapping
                    port = ctx.svc_cfg.get("port", "")
                    if port:
                        url = f"http://{host}:{port}{health_path}"

                if url:
                    try:
                        req = urllib.request.Request(url, method="GET")
                        req.add_header("User-Agent", "dds-health-check/0.4")
                        with urllib.request.urlopen(req, timeout=10.0) as resp:
                            if 200 <= resp.status < 300:
                                console.print(f"  ✅ Health endpoint OK: {url}")
                                return True
                    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                        pass

                    if attempt < max_retries:
                        console.print(
                            f"  [dim]Attempt {attempt}/{max_retries}: "
                            f"health check failed, retrying in {retry_delay}s...[/dim]"
                        )
                        time.sleep(retry_delay)
                        continue

                    console.print(f"  [red]❌ Health endpoint failed: {url}[/red]")
                    return False

                return True  # Running + no health URL = good enough

            except Exception as e:
                if attempt < max_retries:
                    console.print(
                        f"  [dim]Attempt {attempt}/{max_retries}: "
                        f"{e}, retrying in {retry_delay}s...[/dim]"
                    )
                    time.sleep(retry_delay)
                else:
                    console.print(f"  [red]❌ Health check failed: {e}[/red]")
                    return False

        return False

    @staticmethod
    def _resolve_image(ctx: DeployContext) -> str:
        """Build the full image tag for a service."""
        from dds.builders.docker import resolve_image_tag

        return resolve_image_tag(ctx.name, ctx.project_cfg, ctx.svc_cfg)
