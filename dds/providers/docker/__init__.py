"""Docker/SSH provider — deploy to any Docker host via SSH."""

from __future__ import annotations

from dds.providers.docker.container import DockerContainerProvider
from dds.providers.docker.database import DockerDatabaseProvider
from dds.providers.docker.preflight import DockerPreflightProvider
from dds.providers.docker.secrets import DockerSecretProvider
from dds.providers.docker.static import DockerStaticProvider

_container = DockerContainerProvider()
_static = DockerStaticProvider()
_database = DockerDatabaseProvider()
_secret = DockerSecretProvider()
_preflight = DockerPreflightProvider()


def get_container_provider() -> DockerContainerProvider:
    return _container


def get_static_provider() -> DockerStaticProvider:
    return _static


def get_swa_provider():
    """Docker provider does not support SWA — use static-site instead."""
    from dds.console import console

    console.print(
        "[red]The 'docker' provider does not support 'swa' service type.[/red]\n"
        "  Use 'type: static-site' for static deployments to Docker hosts."
    )
    raise SystemExit(1)


def get_database_provider() -> DockerDatabaseProvider:
    return _database


def get_secret_provider() -> DockerSecretProvider:
    return _secret


def get_preflight_provider() -> DockerPreflightProvider:
    return _preflight
