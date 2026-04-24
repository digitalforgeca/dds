"""Kubernetes container provider — ACR build + Kustomize deploy to AKS."""

from __future__ import annotations

import json
import time

from dds.console import console
from dds.context import DeployContext
from dds.providers.azure.utils import az
from dds.providers.base import ContainerProvider
from dds.providers.kubernetes.utils import kubectl, kubectl_json


class KubernetesContainerProvider(ContainerProvider):
    """Kubernetes (AKS) implementation using Kustomize overlays and ACR remote builds."""

    def build(self, ctx: DeployContext) -> str:
        """Build a container image via ACR remote build."""
        from dds.utils.git import git_info

        dockerfile = ctx.svc_cfg.get("dockerfile", "Dockerfile")
        context_dir = ctx.svc_cfg.get("context", ".")
        strategy = ctx.svc_cfg.get("build_strategy", "acr")

        image = self._resolve_image_tag(ctx)
        image_tag = image.split("/", 1)[1] if "/" in image else image
        info = git_info()

        console.print(f"\n[bold blue]🚀 Building {ctx.name}[/bold blue]")
        console.print(
            f"  Image: {image} | Strategy: {strategy} | Git: {info['hash']} @ {info['branch']}"
        )

        build_args = dict(ctx.svc_cfg.get("build_args", {}))
        build_args.setdefault("CACHE_BUST", info["build_time"])
        build_args.setdefault("GIT_HASH", info["hash"])

        if strategy == "local":
            from dds.builders.docker import build_and_push_local

            console.print(f"\n[yellow]📦 Logging into ACR ({ctx.registry_name})...[/yellow]")
            az(f"acr login --name {ctx.registry_name}", verbose=ctx.verbose)
            build_and_push_local(image, dockerfile, context_dir, build_args, ctx.verbose)
        else:
            self._build_acr(ctx.registry_name, image_tag, dockerfile, context_dir, build_args, ctx.verbose)

        return image

    def deploy(self, ctx: DeployContext, image: str) -> None:
        """Deploy to AKS via Kustomize overlay."""
        k8s_cfg = ctx.svc_cfg.get("k8s", {})
        kustomize_dir = ctx.env_cfg.get("kubernetes", {}).get("kustomize_dir", "")
        namespace = k8s_cfg.get("namespace", ctx.env_cfg.get("kubernetes", {}).get("namespace", "default"))
        deployment_name = k8s_cfg.get("deployment", ctx.app_name)
        container_name = k8s_cfg.get("image_container", ctx.name)
        rollout_timeout = k8s_cfg.get("rollout_timeout", "120s")

        console.print(f"\n[yellow]🚢 Deploying to AKS: {deployment_name} → {namespace}[/yellow]")

        # Ensure namespace exists
        self._ensure_namespace(namespace, ctx.verbose)

        if kustomize_dir:
            # Apply Kustomize overlay
            console.print(f"  Applying Kustomize overlay: {kustomize_dir}")
            kubectl(f"apply -k {kustomize_dir}", verbose=ctx.verbose)
        else:
            # Direct image update (no Kustomize)
            console.print(f"  Setting image: {container_name}={image}")
            kubectl(
                f"set image deployment/{deployment_name} {container_name}={image}",
                verbose=ctx.verbose,
                namespace=namespace,
            )

        # Wait for rollout
        console.print(f"  ⏳ Waiting for rollout (timeout: {rollout_timeout})...")
        try:
            kubectl(
                f"rollout status deployment/{deployment_name} --timeout={rollout_timeout}",
                verbose=ctx.verbose,
                namespace=namespace,
            )
            console.print(f"\n[green]✅ {ctx.name} deployed → {namespace}/{deployment_name}[/green]")
        except RuntimeError:
            console.print(f"\n[red]❌ Rollout failed for {deployment_name}[/red]")
            console.print(f"  Run: dds rollback {ctx.env_cfg.get('name', '?')} -s {ctx.name}")
            raise

    def status(self, ctx: DeployContext) -> None:
        """Print status for a K8s deployment."""
        k8s_cfg = ctx.svc_cfg.get("k8s", {})
        namespace = k8s_cfg.get("namespace", ctx.env_cfg.get("kubernetes", {}).get("namespace", "default"))
        deployment_name = k8s_cfg.get("deployment", ctx.app_name)

        try:
            data = kubectl_json(
                f"get deployment {deployment_name}",
                verbose=ctx.verbose,
                namespace=namespace,
            )
            status = data.get("status", {})
            spec = data.get("spec", {})
            containers = spec.get("template", {}).get("spec", {}).get("containers", [{}])
            current_image = containers[0].get("image", "?") if containers else "?"

            ready = status.get("readyReplicas", 0)
            desired = spec.get("replicas", 0)
            updated = status.get("updatedReplicas", 0)

            color = "green" if ready == desired else "yellow"
            console.print(
                f"  [bold]{ctx.name}[/bold] ({deployment_name}): "
                f"[{color}]{ready}/{desired} ready[/{color}] | "
                f"updated: {updated} | "
                f"image: {current_image}"
            )
        except Exception as e:
            console.print(f"  [bold]{ctx.name}[/bold] ({deployment_name}): [red]Error: {e}[/red]")

    def rollback(self, ctx: DeployContext, target_revision: str | None = None) -> bool:
        """Rollback a K8s deployment."""
        k8s_cfg = ctx.svc_cfg.get("k8s", {})
        namespace = k8s_cfg.get("namespace", ctx.env_cfg.get("kubernetes", {}).get("namespace", "default"))
        deployment_name = k8s_cfg.get("deployment", ctx.app_name)

        console.print(f"\n[bold yellow]⏪ Rolling back: {deployment_name}[/bold yellow]")

        try:
            if target_revision:
                kubectl(
                    f"rollout undo deployment/{deployment_name} --to-revision={target_revision}",
                    verbose=ctx.verbose,
                    namespace=namespace,
                )
            else:
                kubectl(
                    f"rollout undo deployment/{deployment_name}",
                    verbose=ctx.verbose,
                    namespace=namespace,
                )

            kubectl(
                f"rollout status deployment/{deployment_name} --timeout=120s",
                verbose=ctx.verbose,
                namespace=namespace,
            )
            console.print(f"\n[green]✅ Rolled back {deployment_name}[/green]")
            return True
        except RuntimeError as e:
            console.print(f"\n[red]❌ Rollback failed: {e}[/red]")
            return False

    def revisions(self, ctx: DeployContext) -> None:
        """Show rollout history for a K8s deployment."""
        k8s_cfg = ctx.svc_cfg.get("k8s", {})
        namespace = k8s_cfg.get("namespace", ctx.env_cfg.get("kubernetes", {}).get("namespace", "default"))
        deployment_name = k8s_cfg.get("deployment", ctx.app_name)

        console.print(f"\n[bold]📜 Rollout History: {deployment_name}[/bold]\n")
        output = kubectl(
            f"rollout history deployment/{deployment_name}",
            verbose=ctx.verbose,
            namespace=namespace,
            capture=True,
        )
        if output:
            console.print(output)
        else:
            console.print("[yellow]No revision history found.[/yellow]")

    def logs(
        self,
        ctx: DeployContext,
        follow: bool = False,
        tail: int = 100,
        system: bool = False,
    ) -> None:
        """Tail or stream logs from a K8s deployment."""
        import subprocess as sp

        k8s_cfg = ctx.svc_cfg.get("k8s", {})
        namespace = k8s_cfg.get("namespace", ctx.env_cfg.get("kubernetes", {}).get("namespace", "default"))
        deployment_name = k8s_cfg.get("deployment", ctx.app_name)

        selector = f"app.kubernetes.io/name={deployment_name}"
        cmd_parts = [
            "kubectl", "-n", namespace, "logs",
            f"-l{selector}",
            f"--tail={tail}",
        ]
        if follow:
            cmd_parts.append("-f")

        if system:
            # For system-level events instead of pod logs
            console.print(f"[bold]⚙️  Events: {namespace}/{deployment_name}[/bold]\n")
            kubectl(
                f"get events --sort-by=.lastTimestamp --field-selector involvedObject.name={deployment_name}",
                verbose=True,
                namespace=namespace,
            )
            return

        label = "📋 Logs"
        console.print(f"[bold]{label}: {deployment_name} ({namespace})[/bold]")
        if follow:
            console.print("[dim]Following logs... (Ctrl+C to stop)[/dim]\n")

        if ctx.verbose:
            console.print(f"[dim]$ {' '.join(cmd_parts)}[/dim]")

        try:
            proc = sp.run(cmd_parts, text=True, capture_output=not follow)
            if not follow and proc.stdout:
                for line in proc.stdout.strip().split("\n"):
                    if line.strip():
                        console.print(line)
        except KeyboardInterrupt:
            console.print("\n[dim]Log stream stopped.[/dim]")

    def health(self, ctx: DeployContext, max_retries: int = 5, retry_delay: float = 6.0) -> bool:
        """Verify a K8s deployment is healthy."""
        k8s_cfg = ctx.svc_cfg.get("k8s", {})
        namespace = k8s_cfg.get("namespace", ctx.env_cfg.get("kubernetes", {}).get("namespace", "default"))
        deployment_name = k8s_cfg.get("deployment", ctx.app_name)
        health_path = ctx.svc_cfg.get("health_path", "")
        port = ctx.svc_cfg.get("port", 8080)

        console.print(f"\n[yellow]🏥 Verifying health: {deployment_name} ({namespace})[/yellow]")

        for attempt in range(1, max_retries + 1):
            try:
                data = kubectl_json(
                    f"get deployment {deployment_name}",
                    verbose=ctx.verbose,
                    namespace=namespace,
                )
                status = data.get("status", {})
                spec = data.get("spec", {})
                ready = status.get("readyReplicas", 0)
                desired = spec.get("replicas", 1)

                if ready < desired:
                    if attempt < max_retries:
                        console.print(
                            f"  [dim]Attempt {attempt}/{max_retries}: "
                            f"{ready}/{desired} ready, retrying in {retry_delay}s...[/dim]"
                        )
                        time.sleep(retry_delay)
                        continue
                    console.print(f"  [red]❌ Only {ready}/{desired} replicas ready[/red]")
                    return False

                console.print(f"  ✅ {ready}/{desired} replicas ready")

                # If there's a health path, port-forward and check
                if health_path:
                    if self._port_forward_health_check(
                        namespace, deployment_name, port, health_path, ctx.verbose
                    ):
                        console.print(f"  ✅ Health endpoint OK: {health_path}")
                        return True
                    elif attempt < max_retries:
                        console.print(
                            f"  [dim]Attempt {attempt}/{max_retries}: "
                            f"health check failed, retrying in {retry_delay}s...[/dim]"
                        )
                        time.sleep(retry_delay)
                        continue
                    else:
                        console.print(f"  [red]❌ Health endpoint failed: {health_path}[/red]")
                        return False

                return True

            except Exception as e:
                if attempt < max_retries:
                    console.print(
                        f"  [dim]Attempt {attempt}/{max_retries}: {e}, "
                        f"retrying in {retry_delay}s...[/dim]"
                    )
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
        name = ctx.svc_cfg.get("name", ctx.name)
        tag = ctx.svc_cfg.get("tag", None)

        if tag is None:
            info = git_info()
            tag = info["hash"] if info["hash"] != "unknown" else "latest"

        return f"{registry}/{name}:{tag}"

    @staticmethod
    def _ensure_namespace(namespace: str, verbose: bool = False) -> None:
        """Create namespace if it doesn't exist."""
        import subprocess as sp

        result = sp.run(
            f"kubectl get namespace {namespace}",
            shell=True, capture_output=True, text=True,
        )
        if result.returncode != 0:
            console.print(f"  Creating namespace: {namespace}")
            kubectl(f"create namespace {namespace}", verbose=verbose)

    @staticmethod
    def _build_acr(
        registry_name: str, image_tag: str, dockerfile: str, context_dir: str,
        build_args: dict[str, str], verbose: bool,
    ) -> None:
        """Build via ACR Tasks (remote build)."""
        args_str = ""
        if build_args:
            args_str = " ".join(f"--build-arg {k}={v}" for k, v in build_args.items())

        console.print(f"[yellow]🔨 ACR build: {image_tag}[/yellow]")
        console.print(f"  Registry: {registry_name} | Dockerfile: {dockerfile}")
        az(
            f"acr build --registry {registry_name} "
            f"--image {image_tag} --file {dockerfile} "
            f"--platform linux/amd64 {args_str} {context_dir}",
            verbose=verbose,
        )

    @staticmethod
    def _port_forward_health_check(
        namespace: str, deployment: str, port: int, health_path: str, verbose: bool
    ) -> bool:
        """Port-forward briefly and hit the health endpoint."""
        import subprocess as sp
        import urllib.error
        import urllib.request

        local_port = 18400  # Ephemeral local port for health check

        # Start port-forward in background
        pf_proc = sp.Popen(
            f"kubectl -n {namespace} port-forward deployment/{deployment} {local_port}:{port}",
            shell=True, stdout=sp.PIPE, stderr=sp.PIPE,
        )

        try:
            # Give port-forward a moment to establish
            time.sleep(2)

            url = f"http://localhost:{local_port}{health_path}"
            if verbose:
                console.print(f"  [dim]GET {url}[/dim]")

            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "dds-health-check/0.3")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300

        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False
        finally:
            pf_proc.terminate()
            pf_proc.wait(timeout=5)
