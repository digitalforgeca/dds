"""Kubernetes backup provider — stub implementation."""

from __future__ import annotations

from dds.console import console
from dds.context import DeployContext
from dds.providers.base import BackupProvider


class KubernetesBackupProvider(BackupProvider):
    """Kubernetes backup/restore — not yet implemented.

    Placeholder that satisfies the BackupProvider ABC.
    Future implementation may use Velero, kubectl snapshots, or PVC backups.
    """

    def backup(self, ctx: DeployContext, output_dir: str) -> str:
        """Create a backup — not yet implemented."""
        console.print(
            f"[yellow]⚠️  Kubernetes backup not yet implemented for {ctx.name}[/yellow]\n"
            "  Consider using Velero or cluster-native backup solutions."
        )
        return ""

    def restore(self, ctx: DeployContext, backup_id: str) -> None:
        """Restore from a backup — not yet implemented."""
        console.print(
            f"[yellow]⚠️  Kubernetes restore not yet implemented for {ctx.name}[/yellow]\n"
            "  Consider using Velero or cluster-native backup solutions."
        )

    def list_backups(self, ctx: DeployContext) -> None:
        """List available backups — not yet implemented."""
        console.print(
            f"[yellow]⚠️  Kubernetes backup listing not yet implemented for {ctx.name}[/yellow]"
        )
