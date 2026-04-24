"""Kubernetes secret provider — fetches from K8s secrets or Azure Key Vault via CSI."""

from __future__ import annotations

from dds.console import console
from dds.providers.base import SecretProvider
from dds.providers.kubernetes.utils import kubectl


class KubernetesSecretProvider(SecretProvider):
    """Fetches secrets from Kubernetes secrets or delegates to Azure Key Vault."""

    def fetch(self, vault_name: str, secret_name: str, verbose: bool = False) -> str | None:
        """Fetch a secret value.

        First tries Azure Key Vault (if az CLI available), falls back to
        kubectl get secret. vault_name can be a K8s secret name or a Key Vault name.
        """
        # Try Azure Key Vault first (same behavior as Azure provider)
        try:
            from dds.providers.azure.secrets import AzureSecretProvider

            result = AzureSecretProvider().fetch(vault_name, secret_name, verbose=verbose)
            if result is not None:
                return result
        except Exception:
            pass

        # Fall back to K8s secret
        try:
            import json

            output = kubectl(
                f"get secret {vault_name} -o jsonpath='{{.data.{secret_name}}}'",
                capture=True,
                verbose=verbose,
            )
            if output:
                import base64

                return base64.b64decode(output.strip("'")).decode("utf-8")
        except Exception as e:
            if verbose:
                console.print(f"[dim]Secret fetch failed: {e}[/dim]")

        return None
