"""Azure Static Web Apps provider."""

from __future__ import annotations

import os

from dds.builders.frontend import build_frontend, install_deps
from dds.console import console
from dds.context import DeployContext
from dds.providers.azure.utils import az
from dds.providers.base import SwaProvider
from dds.utils.shell import run_cmd


class AzureSwaProvider(SwaProvider):
    """Azure Static Web Apps implementation."""

    def deploy(self, ctx: DeployContext) -> None:
        """Build and deploy to an Azure Static Web App."""
        swa_name = ctx.svc_cfg.get("swa_name", ctx.app_name)
        project_dir = ctx.svc_cfg.get("project_dir", ".")
        build_cmd = ctx.svc_cfg.get("build_cmd", "npm run build")
        build_dir = ctx.svc_cfg.get("build_dir", "dist")
        env_file = ctx.svc_cfg.get("env_file")

        console.print(f"\n[bold blue]🌐 Deploying SWA: {ctx.name}[/bold blue] → {swa_name}")

        env_production_path = os.path.join(project_dir, ".env.production")
        env_production_backup = None
        env_prod_local_backup: str | None = None

        if env_file:
            env_file_path = os.path.join(project_dir, env_file)
            if not os.path.exists(env_file_path):
                console.print(f"[red]❌ Env file not found: {env_file_path}[/red]")
                raise RuntimeError(f"Missing env file: {env_file_path}")

            if os.path.exists(env_production_path):
                with open(env_production_path) as f:
                    env_production_backup = f.read()

            console.print(f"  Setting build env: {env_file} → .env.production")
            with open(env_file_path) as src:
                content = src.read()
            with open(env_production_path, "w") as dst:
                dst.write(content)

            env_prod_local = os.path.join(project_dir, ".env.production.local")
            if os.path.exists(env_prod_local):
                with open(env_prod_local) as f:
                    env_prod_local_backup = f.read()
                os.remove(env_prod_local)

        try:
            if ctx.svc_cfg.get("install_deps", True):
                install_deps(project_dir=project_dir, verbose=ctx.verbose)

            build_env = dict(ctx.svc_cfg.get("env", {}))
            build_frontend(
                build_cmd=build_cmd,
                project_dir=project_dir,
                env=build_env if build_env else None,
                verbose=ctx.verbose,
            )

            self._verify_baked_env(ctx, project_dir, build_dir)

            swa_config = ctx.svc_cfg.get("swa_config")
            if swa_config is None:
                swa_config = os.path.join(project_dir, "staticwebapp.config.json")
            if os.path.exists(swa_config):
                dist_path = os.path.join(project_dir, build_dir)
                import shutil

                shutil.copy2(swa_config, os.path.join(dist_path, "staticwebapp.config.json"))
                if ctx.verbose:
                    console.print("  Copied staticwebapp.config.json to dist/")

            console.print(f"  Fetching deployment token for {swa_name}...")
            deploy_token = az(
                f"staticwebapp secrets list --name {swa_name} "
                f"--resource-group {ctx.resource_group} "
                f"--query properties.apiKey -o tsv",
                verbose=ctx.verbose,
                capture=True,
            )
            if not deploy_token:
                console.print("[red]❌ Failed to retrieve SWA deployment token[/red]")
                raise RuntimeError(f"No deployment token for SWA: {swa_name}")

            dist_abs = os.path.abspath(os.path.join(project_dir, build_dir))
            console.print(f"  Deploying {dist_abs} to SWA...")
            result = run_cmd(
                f"npx @azure/static-web-apps-cli deploy '{dist_abs}' "
                f"--deployment-token '{deploy_token}' --env production",
                verbose=ctx.verbose,
                cwd="/tmp",
            )
            if result.returncode != 0:
                console.print("[red]❌ SWA deploy failed[/red]")
                if result.stderr:
                    console.print(result.stderr[-500:])
                raise RuntimeError(f"SWA deploy failed for {swa_name}")

            console.print(f"\n[green]✅ {ctx.name} deployed → {swa_name}[/green]")

        finally:
            if env_production_backup is not None:
                with open(env_production_path, "w") as f:
                    f.write(env_production_backup)
                if ctx.verbose:
                    console.print("  Restored original .env.production")
            elif env_file and os.path.exists(env_production_path):
                # We created .env.production from scratch — remove it
                os.remove(env_production_path)
                if ctx.verbose:
                    console.print("  Removed temporary .env.production")

            env_prod_local_path = os.path.join(project_dir, ".env.production.local")
            if env_prod_local_backup is not None:
                with open(env_prod_local_path, "w") as f:
                    f.write(env_prod_local_backup)
                if ctx.verbose:
                    console.print("  Restored original .env.production.local")

    def status(self, ctx: DeployContext) -> None:
        """Show status for a Static Web App."""
        swa_name = ctx.svc_cfg.get("swa_name", ctx.app_name)
        try:
            url = az(
                f"staticwebapp show --name {swa_name} --resource-group {ctx.resource_group} "
                f"--query defaultHostname -o tsv",
                verbose=ctx.verbose,
                capture=True,
            )
            console.print(
                f"  [bold]{ctx.name}[/bold] (SWA → {swa_name}): "
                f"https://{url}" if url else
                f"  [bold]{ctx.name}[/bold] (SWA): [dim]check manually[/dim]"
            )
        except Exception:
            console.print(
                f"  [bold]{ctx.name}[/bold] (SWA → {swa_name}): [dim]check manually[/dim]"
            )

    @staticmethod
    def _verify_baked_env(ctx: DeployContext, project_dir: str, build_dir: str) -> None:
        """Verify the built JS bundle contains expected environment markers."""
        verify = ctx.svc_cfg.get("verify_env")
        if not verify:
            return

        import glob

        dist_path = os.path.join(project_dir, build_dir, "assets")
        js_files = glob.glob(os.path.join(dist_path, "index-*.js"))
        if not js_files:
            console.print("[yellow]⚠️  No index-*.js found for env verification[/yellow]")
            return

        with open(js_files[0]) as f:
            content = f.read()

        for pattern in verify.get("must_contain", []):
            if pattern not in content:
                console.print(
                    f"[red]❌ FATAL: Built JS missing expected pattern: {pattern}[/red]"
                )
                raise RuntimeError(f"Env verification failed: missing '{pattern}'")

        for pattern in verify.get("must_not_contain", []):
            if pattern in content:
                console.print(
                    f"[red]❌ FATAL: Built JS contains forbidden pattern: {pattern}[/red]"
                )
                raise RuntimeError(f"Env verification failed: found '{pattern}'")

        console.print("  ✅ Build env verification passed")
