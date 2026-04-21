"""SWA deployer — backward compatibility re-exports.

Logic has moved to dds.providers.azure.swa.
"""

from __future__ import annotations

from dds.context import DeployContext


def deploy_swa(ctx: DeployContext) -> None:
    """Deploy to a Static Web App (delegates to provider)."""
    from dds.providers import get_swa_provider

    provider = get_swa_provider(ctx.provider)
    provider.deploy(ctx)


def status_swa(ctx: DeployContext) -> None:
    """Show status for a Static Web App (delegates to provider)."""
    from dds.providers import get_swa_provider

    provider = get_swa_provider(ctx.provider)
    provider.status(ctx)
