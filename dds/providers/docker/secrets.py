"""Docker/SSH secret provider — secrets from .env files and environment variables.

For self-hosted Docker deployments, secrets typically live in .env files on the
host or are passed as environment variables. There's no cloud vault — the host
filesystem IS the vault.
"""

from __future__ import annotations

from dds.console import console
from dds.providers.base import SecretProvider


class DockerSecretProvider(SecretProvider):
    """Docker secret provider — reads from env files or environment variables.

    The 'vault_name' is interpreted as a path to a .env file on the local machine.
    The 'secret_name' is the key within that file.
    """

    def fetch(self, vault_name: str, secret_name: str, verbose: bool = False) -> str | None:
        """Fetch a secret from a local .env file.

        vault_name: path to the .env file (e.g., '/path/to/.env' or '.env.production')
        secret_name: the key to look up
        """
        from dds.secrets import load_env_file

        if verbose:
            console.print(f"  [dim]Loading secret '{secret_name}' from {vault_name}[/dim]")

        env_data = load_env_file(vault_name, verbose=verbose)
        return env_data.get(secret_name)
