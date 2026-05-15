"""Custom backup provider — config-driven command templates for backup/restore."""

from __future__ import annotations

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import BackupProvider
from dds.providers.custom.template import (
    build_variables,
    resolve_commands,
    run_template,
    run_template_checked,
)


class CustomBackupProvider(BackupProvider):
    """Backup provider driven by command templates.

    Reads backup/restore/list_backups commands from dds.yaml:

    ```yaml
    commands:
      backup:
        backup: "pg_dump -U {user} {database} | gzip > {output_dir}/{name}-{timestamp}.sql.gz"
        restore: "gunzip -c {backup_id} | psql -U {user} {database}"
        list_backups: "ls -la {output_dir}/{name}-*.sql.gz"
        ssh: true

      # Or per service-type:
      database:
        backup: "docker exec {container} pg_dump -U {user} {database} > {output_dir}/{name}.sql"
        restore: "cat {backup_id} | docker exec -i {container} psql -U {user} {database}"
        list_backups: "ls {output_dir}/{name}-*.sql"
      static-site:
        backup: "rsync -avz {host}:{remote_path}/ {output_dir}/{name}-snapshot/"
        restore: "rsync -avz {backup_id}/ {host}:{remote_path}/"
        list_backups: "ls -d {output_dir}/{name}-*/"
    ```
    """

    def backup(self, ctx: DeployContext, output_dir: str) -> str:
        """Run the configured backup command template."""
        commands = self._resolve_backup_commands(ctx)
        variables = build_variables(ctx)
        variables["output_dir"] = output_dir

        backup_tmpl = commands.get("backup", "")
        if not backup_tmpl:
            console.print(
                f"[red]❌ No 'backup' command configured for {ctx.name}[/red]\n"
                "  Add a 'backup' command under 'commands.backup' or "
                f"'commands.{ctx.service_type}.backup' in dds.yaml."
            )
            raise SystemExit(1)

        host = None
        if commands.get("ssh", False) or commands.get("remote", False):
            host = variables.get("host")

        console.print(f"\n[bold blue]💾 Backing up: {ctx.name}[/bold blue]")
        output = run_template_checked(
            backup_tmpl, variables, "Backup",
            verbose=ctx.verbose, capture=True, host=host,
        )

        backup_id = output.strip() if output else f"{output_dir}/{ctx.name}"
        console.print(f"[green]✅ Backup complete: {backup_id}[/green]")
        return backup_id

    def restore(self, ctx: DeployContext, backup_id: str) -> None:
        """Run the configured restore command template."""
        commands = self._resolve_backup_commands(ctx)
        variables = build_variables(ctx)
        variables["backup_id"] = backup_id

        restore_tmpl = commands.get("restore", "")
        if not restore_tmpl:
            console.print(
                f"[red]❌ No 'restore' command configured for {ctx.name}[/red]\n"
                "  Add a 'restore' command under 'commands.backup' or "
                f"'commands.{ctx.service_type}.restore' in dds.yaml."
            )
            raise SystemExit(1)

        host = None
        if commands.get("ssh", False) or commands.get("remote", False):
            host = variables.get("host")

        console.print(f"\n[bold blue]♻️  Restoring: {ctx.name}[/bold blue]")
        console.print(f"  From: {backup_id}")

        run_template_checked(
            restore_tmpl, variables, "Restore",
            verbose=ctx.verbose, host=host,
        )
        console.print(f"[green]✅ Restore complete[/green]")

    def list_backups(self, ctx: DeployContext) -> None:
        """Run the configured list_backups command template."""
        commands = self._resolve_backup_commands(ctx)
        variables = build_variables(ctx)
        variables["output_dir"] = ".dds-backups"

        list_tmpl = commands.get("list_backups", "")
        if not list_tmpl:
            console.print(
                f"  [bold]{ctx.name}[/bold]: [dim]no list_backups command configured[/dim]"
            )
            return

        host = None
        if commands.get("ssh", False) or commands.get("remote", False):
            host = variables.get("host")

        console.print(f"\n[bold]📋 Backups for {ctx.name}[/bold]")

        try:
            result = run_template(
                list_tmpl, variables, verbose=ctx.verbose, host=host,
            )
            if result.returncode == 0 and result.stdout.strip():
                console.print(result.stdout.strip())
            else:
                console.print("  [dim]No backups found.[/dim]")
        except Exception as e:
            console.print(f"  [red]Error listing backups: {e}[/red]")

    def _resolve_backup_commands(self, ctx: DeployContext) -> dict[str, str]:
        """Resolve backup commands — checks 'backup' section first, then service-type section."""
        # Try dedicated 'backup' command section
        commands = resolve_commands(ctx, "backup")
        if commands:
            return commands

        # Fall back to service-type section (may have backup/restore keys)
        commands = resolve_commands(ctx, ctx.service_type)
        backup_keys = {k: v for k, v in commands.items()
                       if k in ("backup", "restore", "list_backups", "ssh", "remote")}
        return backup_keys
