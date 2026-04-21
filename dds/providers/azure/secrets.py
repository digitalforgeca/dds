"""Azure Key Vault secret provider."""

from __future__ import annotations

from dds.providers.azure.utils import az
from dds.providers.base import SecretProvider


class AzureSecretProvider(SecretProvider):
    """Azure Key Vault implementation."""

    def fetch(self, vault_name: str, secret_name: str, verbose: bool = False) -> str | None:
        """Fetch a secret value from Azure Key Vault."""
        try:
            value = az(
                f"keyvault secret show --vault-name {vault_name} "
                f"--name {secret_name} --query value -o tsv",
                verbose=verbose,
                capture=True,
            )
            return value if value else None
        except RuntimeError:
            return None
