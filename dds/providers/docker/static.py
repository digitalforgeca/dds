"""Docker/SSH static site provider — build locally, rsync to host."""

from __future__ import annotations

from dds.builders.frontend import build_frontend, install_deps
from dds.console import console
from dds.context import DeployContext
from dds.providers.base import StaticProvider
from dds.providers.docker.utils import resolve_host, ssh
from dds.utils.shell import run_cmd


class DockerStaticProvider(StaticProvider):
    """Deploy static sites to a Docker/SSH host via rsync or scp."""

    def deploy(self, ctx: DeployContext) -> None:
        """Build a static site locally and upload to the remote host."""
        host = resolve_host(ctx)
        build_cmd = ctx.svc_cfg.get("build_cmd", "npm run build")
        build_dir = ctx.svc_cfg.get("build_dir", "dist")
        project_dir = ctx.svc_cfg.get("project_dir", ".")
        remote_path = ctx.svc_cfg.get("remote_path", "")

        if not remote_path:
            console.print(
                "[red]No 'remote_path' configured.[/red] "
                "Docker static-site requires a remote directory to deploy to.\n"
                "  Example: remote_path: /var/www/mysite"
            )
            raise SystemExit(1)

        console.print(f"\n[bold blue]🌐 Deploying static site: {ctx.name}[/bold blue] → {host}:{remote_path}")

        # Install deps
        if ctx.svc_cfg.get("install_deps", True):
            install_deps(project_dir=project_dir, verbose=ctx.verbose)

        # Build
        build_env = dict(ctx.svc_cfg.get("env", {}))
        build_frontend(
            build_cmd=build_cmd,
            project_dir=project_dir,
            env=build_env if build_env else None,
            verbose=ctx.verbose,
        )

        # Ensure remote dir exists
        ssh(host, f"mkdir -p {remote_path}", verbose=ctx.verbose)

        # Upload via rsync (preferred) or scp
        import shutil
        import os

        source_path = os.path.join(project_dir, build_dir)
        if not source_path.endswith("/"):
            source_path += "/"

        if shutil.which("rsync"):
            console.print(f"[yellow]📤 Syncing {build_dir} → {host}:{remote_path}[/yellow]")
            result = run_cmd(
                f"rsync -avz --delete {source_path} {host}:{remote_path}/",
                verbose=ctx.verbose,
            )
            if result.returncode != 0:
                console.print("[red]rsync failed[/red]")
                if result.stderr:
                    console.print(result.stderr[-500:])
                raise RuntimeError(f"rsync failed for {ctx.name}")
        else:
            console.print(f"[yellow]📤 Copying {build_dir} → {host}:{remote_path}[/yellow]")
            result = run_cmd(
                f"scp -r {source_path}* {host}:{remote_path}/",
                verbose=ctx.verbose,
            )
            if result.returncode != 0:
                console.print("[red]scp failed[/red]")
                raise RuntimeError(f"scp failed for {ctx.name}")

        console.print(f"\n[green]✅ {ctx.name} deployed to {host}:{remote_path}[/green]")

    def status(self, ctx: DeployContext) -> None:
        """Show status for a static site on the Docker host."""
        host = resolve_host(ctx)
        remote_path = ctx.svc_cfg.get("remote_path", "")

        if not remote_path:
            console.print(f"  [bold]{ctx.name}[/bold]: [dim]no remote_path configured[/dim]")
            return

        try:
            output = ssh(
                host,
                f"ls -la {remote_path}/index.html 2>/dev/null && echo EXISTS || echo MISSING",
                verbose=ctx.verbose,
                capture=True,
            )
            if "EXISTS" in output:
                # Get file count and total size
                info = ssh(
                    host,
                    f"du -sh {remote_path} 2>/dev/null | cut -f1",
                    verbose=ctx.verbose,
                    capture=True,
                )
                console.print(
                    f"  [bold]{ctx.name}[/bold] (static → {host}:{remote_path}): "
                    f"[green]deployed[/green] | size: {info or '?'}"
                )
            else:
                console.print(
                    f"  [bold]{ctx.name}[/bold] (static → {host}:{remote_path}): "
                    f"[yellow]no index.html found[/yellow]"
                )
        except Exception as e:
            console.print(
                f"  [bold]{ctx.name}[/bold] (static → {host}:{remote_path}): "
                f"[red]Error: {e}[/red]"
            )
