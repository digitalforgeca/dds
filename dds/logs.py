"""Container App log streaming — backward compatibility re-exports.

Logic has moved to dds.providers.azure.container.AzureContainerProvider.logs().
"""

from __future__ import annotations

from dds.context import DeployContext


def tail_logs(
    app_name: str,
    rg: str,
    follow: bool = False,
    tail: int = 100,
    container: str | None = None,
    verbose: bool = False,
) -> None:
    """Stream or tail logs (delegates to provider via DeployContext).

    This function signature is kept for backward compat. New code should use
    the provider directly via get_container_provider().logs().
    """
    from dds.providers.azure.container import AzureContainerProvider

    # Build a minimal context for the legacy call signature
    ctx = DeployContext(
        name="legacy",
        svc_cfg={"type": "container-app", "name": app_name},
        env_cfg={"resource_group": rg},
        project_cfg={},
        verbose=verbose,
    )
    provider = AzureContainerProvider()
    provider.logs(ctx, follow=follow, tail=tail, system=False)


def system_logs(
    app_name: str,
    rg: str,
    tail: int = 50,
    verbose: bool = False,
) -> None:
    """Show system logs (delegates to provider)."""
    ctx = DeployContext(
        name="legacy",
        svc_cfg={"type": "container-app", "name": app_name},
        env_cfg={"resource_group": rg},
        project_cfg={},
        verbose=verbose,
    )
    provider = AzureContainerProvider()
    provider.logs(ctx, follow=False, tail=tail, system=True)
