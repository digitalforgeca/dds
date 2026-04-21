"""Database deployer — backward compatibility re-exports.

Logic has moved to dds.providers.azure.database.
"""

from __future__ import annotations

from dds.context import DeployContext


def provision_database(ctx: DeployContext) -> None:
    """Provision a database (delegates to provider)."""
    from dds.providers import get_database_provider

    provider = get_database_provider(ctx.provider)
    provider.provision(ctx)


def status_database(ctx: DeployContext) -> None:
    """Show status for a database (delegates to provider)."""
    from dds.providers import get_database_provider

    provider = get_database_provider(ctx.provider)
    provider.status(ctx)
