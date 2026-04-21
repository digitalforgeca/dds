"""Rollback support — backward compatibility re-exports.

Logic has moved to dds.providers.azure.container.AzureContainerProvider.
"""

from __future__ import annotations

from dds.context import DeployContext


def rollback_container_app(ctx: DeployContext, target_revision: str | None = None) -> bool:
    """Rollback a Container App to a previous revision (delegates to provider)."""
    from dds.providers import get_container_provider

    provider = get_container_provider(ctx.provider)
    return provider.rollback(ctx, target_revision=target_revision)


def show_revisions(ctx: DeployContext) -> None:
    """Display revision history (delegates to provider)."""
    from dds.providers import get_container_provider

    provider = get_container_provider(ctx.provider)
    provider.revisions(ctx)
