"""Secrets management — resolve secrets from Azure Key Vault, env vars, or .env files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from rich.console import Console

from dds.utils.azure import az

console = Console()


def resolve_secrets(
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> dict[str, str]:
    """Resolve all secrets for a service into a flat key=value dict.

    Secret sources (in priority order):
    1. Azure Key Vault references (fetched at deploy time)
    2. Environment-level env_file (.env path)
    3. Service-level env vars (inline in dds.yaml)
    4. Process environment variables

    Config example in dds.yaml:
        environments:
          dev:
            key_vault: my-keyvault
            env_file: .env.dev
            services:
              api:
                env:
                  PUBLIC_VAR: "value"
                secrets:
                  - name: DATABASE_URL
                    vault_key: db-connection-string
                  - name: API_KEY
                    vault_key: api-key
                  - name: FROM_ENV
                    env: MY_LOCAL_ENV_VAR
    """
    resolved: dict[str, str] = {}

    # Layer 1: env_file (environment-level)
    env_file = env_cfg.get("env_file", "")
    if env_file:
        resolved.update(_load_env_file(env_file, verbose=verbose))

    # Layer 2: inline env vars (service-level)
    inline_env = svc_cfg.get("env", {})
    if isinstance(inline_env, dict):
        resolved.update({k: str(v) for k, v in inline_env.items()})

    # Layer 3: secrets (Key Vault or env var references)
    secrets = svc_cfg.get("secrets", [])
    vault_name = env_cfg.get("key_vault", project_cfg.get("key_vault", ""))

    for secret in secrets:
        name = secret.get("name", "")
        if not name:
            continue

        vault_key = secret.get("vault_key", "")
        env_key = secret.get("env", "")

        if vault_key and vault_name:
            # Fetch from Azure Key Vault
            value = _fetch_vault_secret(vault_name, vault_key, verbose=verbose)
            if value is not None:
                resolved[name] = value
            else:
                console.print(
                    f"[yellow]⚠️  Secret '{name}' not found in vault "
                    f"'{vault_name}' (key: {vault_key})[/yellow]"
                )
        elif env_key:
            # Read from local environment
            value = os.environ.get(env_key, "")
            if value:
                resolved[name] = value
            else:
                console.print(
                    f"[yellow]⚠️  Secret '{name}' references env var "
                    f"'{env_key}' which is not set[/yellow]"
                )
        else:
            console.print(
                f"[yellow]⚠️  Secret '{name}' has no vault_key or env source[/yellow]"
            )

    return resolved


def _fetch_vault_secret(
    vault_name: str, secret_name: str, verbose: bool = False
) -> str | None:
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


def _load_env_file(path: str, verbose: bool = False) -> dict[str, str]:
    """Load a .env file into a dict. Supports KEY=VALUE and comments."""
    env_path = Path(path)
    if not env_path.exists():
        if verbose:
            console.print(f"[dim]env_file '{path}' not found, skipping[/dim]")
        return {}

    result: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value

    if verbose:
        console.print(f"[dim]Loaded {len(result)} vars from {path}[/dim]")

    return result


def list_vault_secrets(vault_name: str, verbose: bool = False) -> list[str]:
    """List all secret names in an Azure Key Vault."""
    try:
        import json

        output = az(
            f"keyvault secret list --vault-name {vault_name} "
            f"--query [].name -o json",
            verbose=verbose,
            capture=True,
        )
        return json.loads(output) if output else []
    except (RuntimeError, ValueError):
        return []
