"""Tests for backup/restore providers and CLI commands."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from dds.cli import main
from dds.providers import get_backup_provider
from dds.providers.base import BackupProvider


class TestBackupProviderABC:
    """Tests for the BackupProvider abstract base class."""

    def test_importable(self) -> None:
        """BackupProvider should be importable from base."""
        from dds.providers.base import BackupProvider as BP

        assert BP is not None

    def test_is_abstract(self) -> None:
        """BackupProvider should not be directly instantiable."""
        with pytest.raises(TypeError):
            BackupProvider()  # type: ignore[abstract]


class TestBackupProviderRegistry:
    """Tests for backup provider instantiation via the registry."""

    def test_azure_backup_provider(self) -> None:
        """Azure provider should return a BackupProvider instance."""
        provider = get_backup_provider("azure")
        assert isinstance(provider, BackupProvider)

    def test_docker_backup_provider(self) -> None:
        """Docker provider should return a BackupProvider instance."""
        provider = get_backup_provider("docker")
        assert isinstance(provider, BackupProvider)

    def test_custom_backup_provider(self) -> None:
        """Custom provider should return a BackupProvider instance."""
        provider = get_backup_provider("custom")
        assert isinstance(provider, BackupProvider)

    def test_kubernetes_backup_provider(self) -> None:
        """Kubernetes provider should return a BackupProvider instance."""
        provider = get_backup_provider("kubernetes")
        assert isinstance(provider, BackupProvider)

    def test_unknown_provider_exits(self) -> None:
        """Unknown provider name should raise SystemExit."""
        with pytest.raises(SystemExit):
            get_backup_provider("nonexistent")


class TestBackupCLI:
    """Tests for the backup/restore/backups CLI commands."""

    def test_backup_command_registered(self) -> None:
        """The 'backup' command should be registered on the CLI."""
        assert "backup" in main.commands

    def test_restore_command_registered(self) -> None:
        """The 'restore' command should be registered on the CLI."""
        assert "restore" in main.commands

    def test_backups_command_registered(self) -> None:
        """The 'backups' command should be registered on the CLI."""
        assert "backups" in main.commands

    def test_backup_help(self) -> None:
        """'dds backup --help' should succeed."""
        runner = CliRunner()
        result = runner.invoke(main, ["backup", "--help"])
        assert result.exit_code == 0
        assert "Create backups" in result.output

    def test_restore_help(self) -> None:
        """'dds restore --help' should succeed."""
        runner = CliRunner()
        result = runner.invoke(main, ["restore", "--help"])
        assert result.exit_code == 0
        assert "Restore a service" in result.output

    def test_backups_help(self) -> None:
        """'dds backups --help' should succeed."""
        runner = CliRunner()
        result = runner.invoke(main, ["backups", "--help"])
        assert result.exit_code == 0
        assert "List available backups" in result.output

    def test_restore_requires_service(self) -> None:
        """'dds restore' should require --service."""
        runner = CliRunner()
        result = runner.invoke(main, ["restore", "production"])
        assert result.exit_code != 0

    def test_restore_requires_from(self) -> None:
        """'dds restore' should require --from."""
        runner = CliRunner()
        result = runner.invoke(main, ["restore", "production", "-s", "db"])
        assert result.exit_code != 0
