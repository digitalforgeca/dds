"""Azure provider — Container Apps, Blob Storage, SWA, Postgres Flex, Key Vault."""

from __future__ import annotations

from dds.providers.azure.container import AzureContainerProvider
from dds.providers.azure.database import AzureDatabaseProvider
from dds.providers.azure.preflight import AzurePreflightProvider
from dds.providers.azure.secrets import AzureSecretProvider
from dds.providers.azure.static import AzureStaticProvider
from dds.providers.azure.swa import AzureSwaProvider

# Singleton instances (stateless, safe to reuse)
_container = AzureContainerProvider()
_static = AzureStaticProvider()
_swa = AzureSwaProvider()
_database = AzureDatabaseProvider()
_secret = AzureSecretProvider()
_preflight = AzurePreflightProvider()


def get_container_provider() -> AzureContainerProvider:
    return _container


def get_static_provider() -> AzureStaticProvider:
    return _static


def get_swa_provider() -> AzureSwaProvider:
    return _swa


def get_database_provider() -> AzureDatabaseProvider:
    return _database


def get_secret_provider() -> AzureSecretProvider:
    return _secret


def get_preflight_provider() -> AzurePreflightProvider:
    return _preflight
