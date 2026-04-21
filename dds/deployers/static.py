"""Static site deployer — backward compatibility re-exports.

Logic has moved to dds.providers.azure.static.
"""

from __future__ import annotations

from dds.context import DeployContext


def deploy_static_site(ctx: DeployContext) -> None:
    """Deploy a static site (delegates to provider)."""
    from dds.providers import get_static_provider

    provider = get_static_provider(ctx.provider)
    provider.deploy(ctx)


def status_static_site(ctx: DeployContext) -> None:
    """Show status for a static site (delegates to provider)."""
    from dds.providers import get_static_provider

    provider = get_static_provider(ctx.provider)
    provider.status(ctx)
