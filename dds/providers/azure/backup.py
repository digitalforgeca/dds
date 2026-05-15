"""Azure backup provider — Postgres Flex, Blob Storage snapshots, Container App manifests."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from dds.console import console
from dds.context import DeployContext
from dds.providers.azure.utils import az, az_json
from dds.providers.base import BackupProvider


class AzureBackupProvider(BackupProvider):
    """Azure backup/restore implementation.

    Routes by service type:
      - database → Postgres Flexible Server named backups
      - static-site → Blob storage snapshots
      - container-app → Revision + env var manifest export
    """

    def backup(self, ctx: DeployContext, output_dir: str) -> str:
        """Create a backup based on service type."""
        os.makedirs(output_dir, exist_ok=True)

        if ctx.service_type == "database":
            return self._backup_database(ctx, output_dir)
        elif ctx.service_type == "static-site":
            return self._backup_blobs(ctx, output_dir)
        elif ctx.service_type == "container-app":
            return self._backup_container_manifest(ctx, output_dir)
        else:
            console.print(
                f"[yellow]⚠️  Backup not supported for service type "
                f"'{ctx.service_type}' on Azure[/yellow]"
            )
            return ""

    def restore(self, ctx: DeployContext, backup_id: str) -> None:
        """Restore from a backup based on service type."""
        if ctx.service_type == "database":
            self._restore_database(ctx, backup_id)
        elif ctx.service_type == "static-site":
            self._restore_blobs(ctx, backup_id)
        elif ctx.service_type == "container-app":
            console.print(
                "[yellow]⚠️  Container App manifest restore is manual.[/yellow]\n"
                f"  Review the manifest at: {backup_id}\n"
                "  Use 'dds deploy' to redeploy with the saved configuration."
            )
        else:
            console.print(
                f"[red]❌ Restore not supported for service type "
                f"'{ctx.service_type}' on Azure[/red]"
            )

    def list_backups(self, ctx: DeployContext) -> None:
        """List available backups based on service type."""
        if ctx.service_type == "database":
            self._list_database_backups(ctx)
        elif ctx.service_type == "static-site":
            self._list_blob_snapshots(ctx)
        elif ctx.service_type == "container-app":
            self._list_container_manifests(ctx)
        else:
            console.print(
                f"[dim]  No backup listing for service type '{ctx.service_type}'[/dim]"
            )

    # ── Database (Postgres Flex) ──────────────────────────────────────

    def _backup_database(self, ctx: DeployContext, output_dir: str) -> str:
        """Create a named backup of a Postgres Flexible Server."""
        server = ctx.svc_cfg.get("server", "")
        rg = ctx.resource_group
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"{ctx.name}-{timestamp}"

        console.print(f"\n[bold blue]🗄️  Backing up database: {ctx.name}[/bold blue]")
        console.print(f"  Server: {server} | Backup: {backup_name}")

        az(
            f"postgres flexible-server backup create "
            f"--name {backup_name} --server-name {server} "
            f"--resource-group {rg}",
            verbose=ctx.verbose,
        )
        console.print(f"[green]✅ Database backup created: {backup_name}[/green]")
        return backup_name

    def _restore_database(self, ctx: DeployContext, backup_id: str) -> None:
        """Restore a Postgres Flexible Server from a named backup (point-in-time)."""
        server = ctx.svc_cfg.get("server", "")
        rg = ctx.resource_group
        restore_server = f"{server}-restored-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

        console.print(f"\n[bold blue]🗄️  Restoring database: {ctx.name}[/bold blue]")
        console.print(f"  From: {backup_id} → New server: {restore_server}")

        az(
            f"postgres flexible-server restore "
            f"--source-server {server} --resource-group {rg} "
            f"--name {restore_server} "
            f"--restore-time {backup_id}",
            verbose=ctx.verbose,
        )
        console.print(
            f"[green]✅ Database restored to new server: {restore_server}[/green]\n"
            f"  [dim]Update your config to point to the new server if needed.[/dim]"
        )

    def _list_database_backups(self, ctx: DeployContext) -> None:
        """List available backups for a Postgres Flexible Server."""
        server = ctx.svc_cfg.get("server", "")
        rg = ctx.resource_group

        console.print(f"\n[bold]📋 Backups for {ctx.name}[/bold] (server: {server})")

        try:
            backups = az_json(
                f"postgres flexible-server backup list "
                f"--server-name {server} --resource-group {rg}"
            )
            if not backups:
                console.print("  [dim]No backups found.[/dim]")
                return
            for b in backups:
                name = b.get("name", "?")
                completed = b.get("completedTime", "?")
                btype = b.get("backupType", "?")
                console.print(f"  {name} | {completed} | type: {btype}")
        except Exception as e:
            console.print(f"  [red]Error listing backups: {e}[/red]")

    # ── Blob Storage (static-site) ───────────────────────────────────

    def _backup_blobs(self, ctx: DeployContext, output_dir: str) -> str:
        """Snapshot all blobs in a storage container."""
        account = ctx.svc_cfg.get("storage_account", "")
        container = ctx.svc_cfg.get("container", "$web")
        rg = ctx.resource_group
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        console.print(f"\n[bold blue]📦 Snapshotting blobs: {ctx.name}[/bold blue]")
        console.print(f"  Account: {account} | Container: {container}")

        # Get account key for blob operations
        key = az(
            f"storage account keys list --account-name {account} "
            f"--resource-group {rg} --query '[0].value' -o tsv",
            verbose=ctx.verbose,
            capture=True,
        )

        # List blobs and snapshot each
        blobs_json = az(
            f"storage blob list --account-name {account} "
            f"--container-name {container} --account-key {key} "
            f"--query '[].name' -o json",
            verbose=ctx.verbose,
            capture=True,
        )
        blob_names = json.loads(blobs_json) if blobs_json else []

        if not blob_names:
            console.print("  [dim]No blobs to snapshot.[/dim]")
            return ""

        for blob_name in blob_names:
            az(
                f"storage blob snapshot --account-name {account} "
                f"--container-name {container} --name {blob_name!r} "
                f"--account-key {key}",
                verbose=ctx.verbose,
            )

        snapshot_id = f"{account}/{container}@{timestamp}"
        console.print(
            f"[green]✅ Snapshotted {len(blob_names)} blobs: {snapshot_id}[/green]"
        )
        return snapshot_id

    def _restore_blobs(self, ctx: DeployContext, backup_id: str) -> None:
        """Restore blobs from a snapshot timestamp."""
        account = ctx.svc_cfg.get("storage_account", "")
        container = ctx.svc_cfg.get("container", "$web")
        rg = ctx.resource_group

        console.print(f"\n[bold blue]📦 Restoring blobs: {ctx.name}[/bold blue]")
        console.print(f"  From snapshot: {backup_id}")

        key = az(
            f"storage account keys list --account-name {account} "
            f"--resource-group {rg} --query '[0].value' -o tsv",
            verbose=ctx.verbose,
            capture=True,
        )

        # List blob snapshots and copy from the matching snapshot
        blobs = az(
            f"storage blob list --account-name {account} "
            f"--container-name {container} --account-key {key} "
            f"--include s --query \"[?snapshot=='{backup_id}']\" -o json",
            verbose=ctx.verbose,
            capture=True,
        )
        snapshot_blobs = json.loads(blobs) if blobs else []

        if not snapshot_blobs:
            console.print(f"[red]❌ No snapshots found matching: {backup_id}[/red]")
            return

        for blob in snapshot_blobs:
            blob_name = blob.get("name", "")
            snapshot = blob.get("snapshot", "")
            source = (
                f"https://{account}.blob.core.windows.net/"
                f"{container}/{blob_name}?snapshot={snapshot}"
            )
            az(
                f"storage blob copy start --account-name {account} "
                f"--destination-container {container} "
                f"--destination-blob {blob_name!r} "
                f"--source-uri {source!r} --account-key {key}",
                verbose=ctx.verbose,
            )

        console.print(
            f"[green]✅ Restored {len(snapshot_blobs)} blobs from snapshot[/green]"
        )

    def _list_blob_snapshots(self, ctx: DeployContext) -> None:
        """List blob snapshots in a storage container."""
        account = ctx.svc_cfg.get("storage_account", "")
        container = ctx.svc_cfg.get("container", "$web")
        rg = ctx.resource_group

        console.print(f"\n[bold]📋 Blob snapshots for {ctx.name}[/bold] ({account}/{container})")

        try:
            key = az(
                f"storage account keys list --account-name {account} "
                f"--resource-group {rg} --query '[0].value' -o tsv",
                capture=True,
            )
            blobs = az(
                f"storage blob list --account-name {account} "
                f"--container-name {container} --account-key {key} "
                f"--include s --query \"[?snapshot != null]\" -o json",
                capture=True,
            )
            snapshots = json.loads(blobs) if blobs else []

            if not snapshots:
                console.print("  [dim]No snapshots found.[/dim]")
                return

            # Group by snapshot timestamp
            seen: set[str] = set()
            for s in snapshots:
                ts = s.get("snapshot", "?")
                if ts not in seen:
                    seen.add(ts)
                    console.print(f"  {ts} | blobs in snapshot batch")
        except Exception as e:
            console.print(f"  [red]Error listing snapshots: {e}[/red]")

    # ── Container App (manifest export) ──────────────────────────────

    def _backup_container_manifest(self, ctx: DeployContext, output_dir: str) -> str:
        """Export Container App revision info + env vars as a JSON manifest."""
        app_name = ctx.app_name
        rg = ctx.resource_group
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest_file = os.path.join(output_dir, f"{ctx.name}-manifest-{timestamp}.json")

        console.print(f"\n[bold blue]📋 Exporting manifest: {ctx.name}[/bold blue]")
        console.print(f"  App: {app_name} ({rg})")

        try:
            app_data = az_json(
                f"containerapp show --name {app_name} --resource-group {rg}"
            )
        except Exception as e:
            console.print(f"[red]❌ Failed to fetch app info: {e}[/red]")
            return ""

        manifest = {
            "service": ctx.name,
            "app_name": app_name,
            "resource_group": rg,
            "timestamp": timestamp,
            "revision": app_data.get("properties", {}).get("latestRevisionName", ""),
            "image": (
                app_data.get("properties", {})
                .get("template", {})
                .get("containers", [{}])[0]
                .get("image", "")
            ),
            "env_vars": (
                app_data.get("properties", {})
                .get("template", {})
                .get("containers", [{}])[0]
                .get("env", [])
            ),
            "scale": app_data.get("properties", {}).get("template", {}).get("scale", {}),
            "ingress": app_data.get("properties", {}).get("configuration", {}).get("ingress", {}),
        }

        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        console.print(f"[green]✅ Manifest exported: {manifest_file}[/green]")
        return manifest_file

    def _list_container_manifests(self, ctx: DeployContext) -> None:
        """List locally saved manifests for a container app."""
        output_dir = ".dds-backups"
        prefix = f"{ctx.name}-manifest-"

        console.print(f"\n[bold]📋 Saved manifests for {ctx.name}[/bold]")

        if not os.path.isdir(output_dir):
            console.print("  [dim]No backup directory found.[/dim]")
            return

        manifests = sorted(
            f for f in os.listdir(output_dir) if f.startswith(prefix) and f.endswith(".json")
        )
        if not manifests:
            console.print("  [dim]No manifests found.[/dim]")
            return

        for m in manifests:
            console.print(f"  {os.path.join(output_dir, m)}")
