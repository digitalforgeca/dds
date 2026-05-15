"""Docker/SSH backup provider — pg_dump and rsync snapshots."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import BackupProvider
from dds.providers.docker.utils import resolve_host, ssh


class DockerBackupProvider(BackupProvider):
    """Docker backup/restore via SSH.

    Routes by service type:
      - database → pg_dump piped to gzipped SQL file
      - static-site → rsync snapshot from remote
    """

    def backup(self, ctx: DeployContext, output_dir: str) -> str:
        """Create a backup based on service type."""
        os.makedirs(output_dir, exist_ok=True)

        if ctx.service_type == "database":
            return self._backup_database(ctx, output_dir)
        elif ctx.service_type == "static-site":
            return self._backup_static(ctx, output_dir)
        else:
            console.print(
                f"[yellow]⚠️  Backup not supported for service type "
                f"'{ctx.service_type}' on Docker provider[/yellow]"
            )
            return ""

    def restore(self, ctx: DeployContext, backup_id: str) -> None:
        """Restore from a backup based on service type."""
        if ctx.service_type == "database":
            self._restore_database(ctx, backup_id)
        elif ctx.service_type == "static-site":
            self._restore_static(ctx, backup_id)
        else:
            console.print(
                f"[red]❌ Restore not supported for service type "
                f"'{ctx.service_type}' on Docker provider[/red]"
            )

    def list_backups(self, ctx: DeployContext) -> None:
        """List locally saved backups for a service."""
        output_dir = ".dds-backups"

        console.print(f"\n[bold]📋 Backups for {ctx.name}[/bold]")

        if not os.path.isdir(output_dir):
            console.print("  [dim]No backup directory found.[/dim]")
            return

        prefix = f"{ctx.name}-"
        entries = sorted(
            f for f in os.listdir(output_dir) if f.startswith(prefix)
        )
        if not entries:
            console.print("  [dim]No backups found.[/dim]")
            return

        for entry in entries:
            full_path = os.path.join(output_dir, entry)
            size = ""
            if os.path.isfile(full_path):
                bytes_size = os.path.getsize(full_path)
                if bytes_size > 1_048_576:
                    size = f" ({bytes_size / 1_048_576:.1f} MB)"
                elif bytes_size > 1024:
                    size = f" ({bytes_size / 1024:.1f} KB)"
                else:
                    size = f" ({bytes_size} B)"
            elif os.path.isdir(full_path):
                size = " (directory)"
            console.print(f"  {full_path}{size}")

    # ── Database (pg_dump) ────────────────────────────────────────────

    def _backup_database(self, ctx: DeployContext, output_dir: str) -> str:
        """Dump a Postgres database from a Docker container via SSH."""
        host = resolve_host(ctx)
        container = ctx.svc_cfg.get("container", ctx.svc_cfg.get("server", ""))
        db_name = ctx.svc_cfg.get("database", ctx.name)
        db_user = ctx.svc_cfg.get("user", "postgres")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_file = os.path.join(output_dir, f"{ctx.name}-{timestamp}.sql.gz")

        if not container:
            console.print(
                "[red]No 'container' or 'server' configured.[/red] "
                "Docker backup needs the Postgres container name."
            )
            raise SystemExit(1)

        console.print(f"\n[bold blue]🗄️  Backing up database: {ctx.name}[/bold blue]")
        console.print(f"  Host: {host} | Container: {container} | DB: {db_name}")

        dump_cmd = (
            f"docker exec {container} pg_dump -U {db_user} {db_name} | gzip"
        )

        import subprocess

        full_cmd = (
            f"ssh -o BatchMode=yes -o ConnectTimeout=10 {host} "
            f"{dump_cmd!r} > {backup_file}"
        )

        if ctx.verbose:
            console.print(f"[dim]$ {full_cmd}[/dim]")

        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"[red]❌ Database backup failed:[/red] {result.stderr.strip()}")
            raise RuntimeError(f"Database backup failed for {ctx.name}")

        size = os.path.getsize(backup_file)
        size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
        console.print(f"[green]✅ Database backup saved: {backup_file} ({size_str})[/green]")
        return backup_file

    def _restore_database(self, ctx: DeployContext, backup_id: str) -> None:
        """Restore a Postgres database from a gzipped SQL dump."""
        host = resolve_host(ctx)
        container = ctx.svc_cfg.get("container", ctx.svc_cfg.get("server", ""))
        db_name = ctx.svc_cfg.get("database", ctx.name)
        db_user = ctx.svc_cfg.get("user", "postgres")

        if not container:
            console.print("[red]No 'container' configured for restore.[/red]")
            raise SystemExit(1)

        if not os.path.isfile(backup_id):
            console.print(f"[red]❌ Backup file not found: {backup_id}[/red]")
            raise SystemExit(1)

        console.print(f"\n[bold blue]🗄️  Restoring database: {ctx.name}[/bold blue]")
        console.print(f"  From: {backup_id} → {db_name} on {container}")

        import subprocess

        restore_cmd = (
            f"gunzip -c {backup_id} | ssh -o BatchMode=yes -o ConnectTimeout=10 {host} "
            f"'docker exec -i {container} psql -U {db_user} {db_name}'"
        )

        if ctx.verbose:
            console.print(f"[dim]$ {restore_cmd}[/dim]")

        result = subprocess.run(restore_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"[red]❌ Database restore failed:[/red] {result.stderr.strip()}")
            raise RuntimeError(f"Database restore failed for {ctx.name}")

        console.print(f"[green]✅ Database restored from {backup_id}[/green]")

    # ── Static site (rsync snapshot) ─────────────────────────────────

    def _backup_static(self, ctx: DeployContext, output_dir: str) -> str:
        """Rsync a static site from remote to local snapshot directory."""
        host = resolve_host(ctx)
        remote_path = ctx.svc_cfg.get("remote_path", "")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = os.path.join(output_dir, f"{ctx.name}-{timestamp}")

        if not remote_path:
            console.print(
                "[red]No 'remote_path' configured.[/red] "
                "Docker static-site backup needs a remote path."
            )
            raise SystemExit(1)

        console.print(f"\n[bold blue]📦 Backing up static site: {ctx.name}[/bold blue]")
        console.print(f"  Host: {host} | Remote: {remote_path}")

        os.makedirs(snapshot_dir, exist_ok=True)

        import subprocess

        rsync_cmd = f"rsync -avz {host}:{remote_path}/ {snapshot_dir}/"

        if ctx.verbose:
            console.print(f"[dim]$ {rsync_cmd}[/dim]")

        result = subprocess.run(rsync_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"[red]❌ Static site backup failed:[/red] {result.stderr.strip()}")
            raise RuntimeError(f"Static site backup failed for {ctx.name}")

        console.print(f"[green]✅ Static site snapshot saved: {snapshot_dir}[/green]")
        return snapshot_dir

    def _restore_static(self, ctx: DeployContext, backup_id: str) -> None:
        """Rsync a local snapshot back to the remote host."""
        host = resolve_host(ctx)
        remote_path = ctx.svc_cfg.get("remote_path", "")

        if not remote_path:
            console.print("[red]No 'remote_path' configured for restore.[/red]")
            raise SystemExit(1)

        if not os.path.isdir(backup_id):
            console.print(f"[red]❌ Snapshot directory not found: {backup_id}[/red]")
            raise SystemExit(1)

        console.print(f"\n[bold blue]📦 Restoring static site: {ctx.name}[/bold blue]")
        console.print(f"  From: {backup_id} → {host}:{remote_path}")

        import subprocess

        rsync_cmd = f"rsync -avz {backup_id}/ {host}:{remote_path}/"

        if ctx.verbose:
            console.print(f"[dim]$ {rsync_cmd}[/dim]")

        result = subprocess.run(rsync_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"[red]❌ Static site restore failed:[/red] {result.stderr.strip()}")
            raise RuntimeError(f"Static site restore failed for {ctx.name}")

        console.print(f"[green]✅ Static site restored from {backup_id}[/green]")
