"""Secrets management — resolve secrets from provider vaults, env vars, or .env files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dds.console import console


def resolve_secrets(
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> dict[str, str]:
    """Resolve all secrets for a service into a flat key=value dict.

    Priority layers (later overrides earlier):
    1. env_file (.env path, environment-level)
    2. Inline env vars (service-level)
    3. Secrets (provider vault or env var references)
    """
    resolved: dict[str, str] = {}

    # Layer 1: env_file
    env_file = env_cfg.get("env_file", "")
    if env_file:
        resolved.update(load_env_file(env_file, verbose=verbose))

    # Layer 2: inline env vars
    inline_env = svc_cfg.get("env", {})
    if isinstance(inline_env, dict):
        resolved.update({k: str(v) for k, v in inline_env.items()})

    # Layer 3: secrets (provider vault or env vars)
    vault_name = env_cfg.get("key_vault", project_cfg.get("key_vault", ""))
    secrets_list = svc_cfg.get("secrets", [])

    if secrets_list:
        # Lazy-load secret provider only when vault secrets are needed
        secret_provider = None
        for secret in secrets_list:
            name = secret.get("name", "")
            if not name:
                continue

            vault_key = secret.get("vault_key", "")
            env_key = secret.get("env", "")

            if vault_key and vault_name:
                if secret_provider is None:
                    from dds.providers import get_secret_provider, resolve_provider

                    provider_name = resolve_provider(svc_cfg, env_cfg, project_cfg)
                    secret_provider = get_secret_provider(provider_name)

                value = secret_provider.fetch(vault_name, vault_key, verbose=verbose)
                if value is not None:
                    resolved[name] = value
                else:
                    console.print(
                        f"[yellow]⚠️  Secret '{name}' not found in vault "
                        f"'{vault_name}'[/yellow]"
                    )
            elif env_key:
                value = os.environ.get(env_key, "")
                if value:
                    resolved[name] = value
                else:
                    console.print(
                        f"[yellow]⚠️  Secret '{name}': env var '{env_key}' not set[/yellow]"
                    )
            else:
                console.print(
                    f"[yellow]⚠️  Secret '{name}' has no vault_key or env source[/yellow]"
                )

    return resolved


def load_env_file(path: str, verbose: bool = False) -> dict[str, str]:
    """Load a .env file into a dict. Supports KEY=VALUE and comments."""
    env_path = Path(path)
    if not env_path.exists():
        if verbose:
            console.print(f"[dim]env_file '{path}' not found, skipping[/dim]")
        return {}

    result: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        # Strip matching surrounding quotes (double or single).
        # Quoted values may contain inline comments that are part of the value;
        # unquoted values have inline comments stripped.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        else:
            # Remove inline comment: anything after un-quoted " #" or "\t#"
            for sep in (" #", "\t#"):
                if sep in value:
                    value = value[: value.index(sep)].rstrip()
                    break
        result[key] = value

    if verbose:
        console.print(f"[dim]Loaded {len(result)} vars from {path}[/dim]")
    return result
