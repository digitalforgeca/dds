"""Azure Container Apps provider — build, deploy, rollback, logs, health."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request

from dds.console import console
from dds.context import DeployContext
from dds.providers.azure.utils import az, az_json
from dds.providers.base import ContainerProvider
from dds.utils.shell import build_args_str, run_cmd


class AzureContainerProvider(ContainerProvider):
    """Azure Container Apps implementation."""

    def build(self, ctx: DeployContext) -> str:
        """Build a container image via ACR remote build or local Docker."""
        from dds.utils.git import git_info

        dockerfile = ctx.svc_cfg.get("dockerfile", "Dockerfile")
        context = ctx.svc_cfg.get("context", ".")
        strategy = ctx.svc_cfg.get("build_strategy", "acr")

        image = self._resolve_image_tag(ctx)
        image_tag = image.split("/", 1)[1] if "/" in image else image
        info = git_info()

        console.print(f"\n[bold blue]🚀 Deploying {ctx.name}[/bold blue] → {ctx.app_name}")
        console.print(
            f"  Image: {image} | Strategy: {strategy} | Git: {info['hash']} @ {info['branch']}"
        )

        build_args = dict(ctx.svc_cfg.get("build_args", {}))
        build_args.setdefault("CACHE_BUST", info["build_time"])
        build_args.setdefault("GIT_HASH", info["hash"])

        if strategy == "local":
            console.print(f"\n[yellow]📦 Logging into ACR ({ctx.registry_name})...[/yellow]")
            az(f"acr login --name {ctx.registry_name}", verbose=ctx.verbose)
            self._build_and_push_local(image, dockerfile, context, build_args, ctx.verbose)
        else:
            self._build_acr(ctx.registry, image_tag, dockerfile, context, build_args, ctx.verbose)

        return image

    def deploy(self, ctx: DeployContext, image: str) -> None:
        """Update a Container App with the new image."""
        from dds.secrets import resolve_secrets

        all_env = resolve_secrets(ctx.svc_cfg, ctx.env_cfg, ctx.project_cfg, verbose=ctx.verbose)

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

    def status(self, ctx: DeployContext) -> None:
        """Show status for a Container App."""
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

    def rollback(self, ctx: DeployContext, target_revision: str | None = None) -> bool:
        """Rollback a Container App to a previous revision."""
        console.print(f"\n[bold yellow]⏪ Rolling back: {ctx.app_name}[/bold yellow]")

        revisions = self._list_revisions(ctx.app_name, ctx.resource_group, ctx.verbose)
        if len(revisions) < 2 and target_revision is None:
            console.print("[red]No previous revision to roll back to.[/red]")
            return False

        current = next(
            (r.get("name", "") for r in revisions if r.get("properties", {}).get("active")),
            None,
        )

        if target_revision is None:
            target_revision = next(
                (
                    r.get("name", "")
                    for r in revisions
                    if r.get("name", "") != current
                    and r.get("properties", {}).get("trafficWeight", 0) == 0
                ),
                None,
            )
            if target_revision is None:
                console.print("[red]No suitable previous revision found.[/red]")
                return False

        console.print(f"  Current: {current}\n  Target:  {target_revision}")

        az(
            f"containerapp revision activate --name {ctx.app_name} "
            f"--resource-group {ctx.resource_group} --revision {target_revision}",
            verbose=ctx.verbose,
        )
        az(
            f"containerapp ingress traffic set --name {ctx.app_name} "
            f"--resource-group {ctx.resource_group} --revision-weight {target_revision}=100",
            verbose=ctx.verbose,
        )
        if current and current != target_revision:
            az(
                f"containerapp revision deactivate --name {ctx.app_name} "
                f"--resource-group {ctx.resource_group} --revision {current}",
                verbose=ctx.verbose,
            )

        console.print(f"\n[green]✅ Rolled back {ctx.app_name} → {target_revision}[/green]")
        return True

    def revisions(self, ctx: DeployContext) -> None:
        """Display revision history for a Container App."""
        revs = self._list_revisions(ctx.app_name, ctx.resource_group, ctx.verbose)

        if not revs:
            console.print(f"[yellow]No revisions found for {ctx.app_name}.[/yellow]")
            return

        console.print(f"\n[bold]📜 Revisions: {ctx.app_name}[/bold]\n")
        for rev in revs:
            props = rev.get("properties", {})
            active = props.get("active", False)
            weight = props.get("trafficWeight", 0)
            containers = props.get("template", {}).get("containers", [{}])
            image = containers[0].get("image", "?") if containers else "?"

            icon = "🟢" if active else "⚪"
            traffic = f" ({weight}%)" if weight > 0 else ""

            console.print(
                f"  {icon} {rev.get('name', '?')}{traffic}\n"
                f"     Image: {image}\n"
                f"     Created: {props.get('createdTime', '?')} | "
                f"Health: {props.get('healthState', '?')}"
            )
        console.print()

    def logs(
        self,
        ctx: DeployContext,
        follow: bool = False,
        tail: int = 100,
        system: bool = False,
    ) -> None:
        """Tail or stream logs from a Container App."""
        log_type = "system" if system else "console"
        cmd_parts = [
            "az", "containerapp", "logs", "show",
            "--name", ctx.app_name,
            "--resource-group", ctx.resource_group,
            "--type", log_type,
            "--tail", str(tail),
        ]
        if follow and not system:
            cmd_parts.append("--follow")

        if ctx.verbose:
            console.print(f"[dim]$ {' '.join(cmd_parts)}[/dim]")

        label = "⚙️  System logs" if system else "📋 Logs"
        console.print(f"[bold]{label}: {ctx.app_name}[/bold]")
        if follow and not system:
            console.print("[dim]Following logs... (Ctrl+C to stop)[/dim]\n")

        try:
            proc = subprocess.run(cmd_parts, text=True, capture_output=not (follow and not system))

            if (system or not follow) and proc.stdout:
                for line in proc.stdout.strip().split("\n"):
                    if line.strip():
                        console.print(line)

            if proc.returncode != 0 and proc.stderr:
                errors = [
                    line for line in proc.stderr.split("\n")
                    if line.strip() and not line.startswith("WARNING:")
                ]
                if errors:
                    console.print(f"[red]{''.join(errors)}[/red]")

        except KeyboardInterrupt:
            console.print("\n[dim]Log stream stopped.[/dim]")

    def health(self, ctx: DeployContext, max_retries: int = 5, retry_delay: float = 6.0) -> bool:
        """Verify a Container App is healthy after deployment."""
        health_path = ctx.svc_cfg.get("health_path", "")
        console.print(f"\n[yellow]🏥 Verifying health: {ctx.app_name}...[/yellow]")

        for attempt in range(1, max_retries + 1):
            try:
                data = az_json(
                    f"containerapp show --name {ctx.app_name} "
                    f"--resource-group {ctx.resource_group}"
                )
                props = data.get("properties", {})
                running = props.get("runningStatus", "unknown")

                if running.lower() not in ("running", "runningstate"):
                    if attempt < max_retries:
                        self._retry_msg(attempt, max_retries, f"status={running}", retry_delay)
                        time.sleep(retry_delay)
                        continue
                    console.print(f"  [red]❌ Container not running (status: {running})[/red]")
                    return False

                revision = props.get("latestRevisionName", "unknown")
                fqdn = props.get("configuration", {}).get("ingress", {}).get("fqdn", "")
                console.print(f"  ✅ Running | Revision: {revision}")

                if health_path and fqdn:
                    url = f"https://{fqdn}{health_path}"
                    if self._http_check(url, verbose=ctx.verbose):
                        console.print(f"  ✅ Health endpoint OK: {url}")
                        return True
                    elif attempt < max_retries:
                        self._retry_msg(attempt, max_retries, "health check failed", retry_delay)
                        time.sleep(retry_delay)
                        continue
                    else:
                        console.print(f"  [red]❌ Health endpoint failed: {url}[/red]")
                        return False

                return True

            except Exception as e:
                if attempt < max_retries:
                    self._retry_msg(attempt, max_retries, str(e), retry_delay)
                    time.sleep(retry_delay)
                else:
                    console.print(f"  [red]❌ Health check failed: {e}[/red]")
                    return False

        return False

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_image_tag(ctx: DeployContext) -> str:
        """Build the full image tag for a service."""
        from dds.utils.git import git_info

        registry = ctx.project_cfg.get("registry", "")
        project = ctx.project_cfg.get("project", "")
        tag = ctx.svc_cfg.get("tag", None)

        if tag is None:
            info = git_info()
            tag = info["hash"] if info["hash"] != "unknown" else "latest"

        return f"{registry}/{project}-{ctx.name}:{tag}"

    @staticmethod
    def _build_and_push_local(
        image: str, dockerfile: str, context: str,
        build_args: dict[str, str], verbose: bool,
    ) -> None:
        args_str = build_args_str(build_args)
        console.print(f"[yellow]🔨 Building locally: {image}[/yellow]")
        result = run_cmd(f"docker build -f {dockerfile} -t {image} {args_str} {context}", verbose=verbose)
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

    @staticmethod
    def _build_acr(
        registry: str, image_tag: str, dockerfile: str, context: str,
        build_args: dict[str, str], verbose: bool, platform: str = "linux/amd64",
    ) -> None:
        registry_name = registry.split(".")[0]
        args_str = build_args_str(build_args)
        console.print(f"[yellow]🔨 ACR build: {image_tag}[/yellow]")
        console.print(f"  Registry: {registry_name} | Dockerfile: {dockerfile} | Platform: {platform}")
        az(
            f"acr build --registry {registry_name} "
            f"--image {image_tag} --file {dockerfile} "
            f"--platform {platform} {args_str} {context}",
            verbose=verbose,
        )

    @staticmethod
    def _list_revisions(app_name: str, rg: str, verbose: bool = False) -> list[dict]:
        output = az(
            f"containerapp revision list --name {app_name} --resource-group {rg} -o json",
            verbose=verbose,
            capture=True,
        )
        revisions = json.loads(output) if output else []
        revisions.sort(
            key=lambda r: r.get("properties", {}).get("createdTime", ""),
            reverse=True,
        )
        return revisions

    @staticmethod
    def _retry_msg(attempt: int, max_retries: int, reason: str, delay: float) -> None:
        console.print(
            f"  [dim]Attempt {attempt}/{max_retries}: {reason}, retrying in {delay}s...[/dim]"
        )

    @staticmethod
    def _http_check(url: str, timeout: float = 10.0, verbose: bool = False) -> bool:
        if verbose:
            console.print(f"  [dim]GET {url}[/dim]")
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "dds-health-check/0.3")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False


# _build_args_str has moved to dds.utils.shell.build_args_str.
# Kept as a module-level alias for any callers that imported it directly.
_build_args_str = build_args_str
