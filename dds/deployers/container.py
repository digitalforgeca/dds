"""Container App deployer — backward compatibility re-exports.

Logic has moved to dds.providers.azure.container.
"""

from __future__ import annotations

from dds.context import DeployContext


def deploy_container_app(ctx: DeployContext) -> None:
    """Build, push, and deploy a container app (delegates to provider)."""
    from dds.providers import get_container_provider

    provider = get_container_provider(ctx.provider)
    image = provider.build(ctx)
    provider.deploy(ctx, image)


def status_container_app(ctx: DeployContext) -> None:
    """Show status for a container app (delegates to provider)."""
    from dds.providers import get_container_provider

    provider = get_container_provider(ctx.provider)
    provider.status(ctx)
