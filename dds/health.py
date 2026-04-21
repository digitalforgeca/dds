"""Post-deploy health verification — backward compatibility re-exports.

Logic has moved to dds.providers.azure.container.AzureContainerProvider.health().
"""

from __future__ import annotations

from dds.context import DeployContext


def verify_container_health(
    ctx: DeployContext,
    max_retries: int = 5,
    retry_delay: float = 6.0,
) -> bool:
    """Verify a Container App is healthy after deployment (delegates to provider)."""
    from dds.providers import get_container_provider

    provider = get_container_provider(ctx.provider)
    return provider.health(ctx, max_retries=max_retries, retry_delay=retry_delay)
