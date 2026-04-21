"""Provider registry — resolves (provider_name, service_type) to handler instances."""

from __future__ import annotations

from typing import Any

from dds.providers.base import (
    ContainerProvider,
    DatabaseProvider,
    PreflightProvider,
    SecretProvider,
    StaticProvider,
    SwaProvider,
)

# Lazy-loaded provider registry: provider_name → module path
_PROVIDER_MODULES: dict[str, str] = {
    "azure": "dds.providers.azure",
    "docker": "dds.providers.docker",
    "custom": "dds.providers.custom",
}

# Cache of instantiated provider modules
_loaded: dict[str, Any] = {}


def _load_provider_module(provider_name: str) -> Any:
    """Lazy-import a provider module."""
    if provider_name not in _loaded:
        module_path = _PROVIDER_MODULES.get(provider_name)
        if module_path is None:
            from dds.console import console

            console.print(f"[red]Unknown provider:[/red] {provider_name}")
            console.print(f"Available providers: {', '.join(_PROVIDER_MODULES.keys())}")
            raise SystemExit(1)
        import importlib

        _loaded[provider_name] = importlib.import_module(module_path)
    return _loaded[provider_name]


def get_container_provider(provider_name: str) -> ContainerProvider:
    """Get the ContainerProvider for a given cloud provider."""
    mod = _load_provider_module(provider_name)
    return mod.get_container_provider()


def get_static_provider(provider_name: str) -> StaticProvider:
    """Get the StaticProvider for a given cloud provider."""
    mod = _load_provider_module(provider_name)
    return mod.get_static_provider()


def get_swa_provider(provider_name: str) -> SwaProvider:
    """Get the SwaProvider for a given cloud provider."""
    mod = _load_provider_module(provider_name)
    return mod.get_swa_provider()


def get_database_provider(provider_name: str) -> DatabaseProvider:
    """Get the DatabaseProvider for a given cloud provider."""
    mod = _load_provider_module(provider_name)
    return mod.get_database_provider()


def get_secret_provider(provider_name: str) -> SecretProvider:
    """Get the SecretProvider for a given cloud provider."""
    mod = _load_provider_module(provider_name)
    return mod.get_secret_provider()


def get_preflight_provider(provider_name: str) -> PreflightProvider:
    """Get the PreflightProvider for a given cloud provider."""
    mod = _load_provider_module(provider_name)
    return mod.get_preflight_provider()


def resolve_provider(
    svc_cfg: dict[str, Any] | None = None,
    env_cfg: dict[str, Any] | None = None,
    project_cfg: dict[str, Any] | None = None,
) -> str:
    """Resolve the provider name from config hierarchy. Default: 'azure'."""
    if svc_cfg and "provider" in svc_cfg:
        return svc_cfg["provider"]
    if env_cfg and "provider" in env_cfg:
        return env_cfg["provider"]
    if project_cfg and "provider" in project_cfg:
        return project_cfg["provider"]
    return "azure"
