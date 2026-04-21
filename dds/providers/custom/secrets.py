"""Custom secret provider — config-driven secret fetching."""

from __future__ import annotations

import subprocess

from dds.console import console
from dds.providers.base import SecretProvider
from dds.providers.custom.template import interpolate


class CustomSecretProvider(SecretProvider):
    """Secret provider driven by a command template.

    The `fetch` command template receives {vault_name} and {secret_name}
    as interpolation variables. Its stdout is the secret value.

    Configure in dds.yaml:
    ```yaml
    commands:
      secrets:
        fetch: "cat {vault_name} | grep '^{secret_name}=' | cut -d= -f2-"
    ```

    Falls back to reading from a local .env file if no command is configured.
    """

    def __init__(self, fetch_template: str = ""):
        self._fetch_template = fetch_template

    def fetch(
        self, vault_name: str, secret_name: str, verbose: bool = False
    ) -> str | None:
        if not self._fetch_template:
            # Fall back to .env file reading (same as Docker provider)
            from dds.secrets import load_env_file

            if verbose:
                console.print(
                    f"  [dim]Loading secret '{secret_name}' from {vault_name}[/dim]"
                )
            env_data = load_env_file(vault_name, verbose=verbose)
            return env_data.get(secret_name)

        variables = {"vault_name": vault_name, "secret_name": secret_name}
        cmd = interpolate(self._fetch_template, variables)

        if verbose:
            console.print(f"  [dim]$ {cmd}[/dim]")

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            if verbose:
                console.print(
                    f"  [dim]Secret fetch failed for '{secret_name}': "
                    f"{result.stderr.strip()[:200]}[/dim]"
                )
            return None

        value = result.stdout.strip()
        return value if value else None
