"""Tests for dds.deployers dispatch module."""

from dds.deployers import _KNOWN_TYPES, dispatch, show_status
from dds.providers import (
    get_container_provider,
    get_database_provider,
    get_static_provider,
    get_swa_provider,
    resolve_provider,
)
from dds.providers.base import (
    ContainerProvider,
    DatabaseProvider,
    StaticProvider,
    SwaProvider,
)


class TestDeployerRegistry:
    """Tests for the deployer registry."""

    def test_known_types(self) -> None:
        assert "container-app" in _KNOWN_TYPES
        assert "static-site" in _KNOWN_TYPES
        assert "database" in _KNOWN_TYPES
        assert "swa" in _KNOWN_TYPES

    def test_azure_providers_importable(self) -> None:
        """Azure provider should return proper provider instances."""
        assert isinstance(get_container_provider("azure"), ContainerProvider)
        assert isinstance(get_static_provider("azure"), StaticProvider)
        assert isinstance(get_swa_provider("azure"), SwaProvider)
        assert isinstance(get_database_provider("azure"), DatabaseProvider)

    def test_resolve_provider_default(self) -> None:
        """Default provider should be 'azure'."""
        assert resolve_provider() == "azure"
        assert resolve_provider(project_cfg={"project": "test"}) == "azure"

    def test_resolve_provider_project_level(self) -> None:
        assert resolve_provider(project_cfg={"provider": "aws"}) == "aws"

    def test_resolve_provider_env_overrides_project(self) -> None:
        assert resolve_provider(
            env_cfg={"provider": "gcp"},
            project_cfg={"provider": "aws"},
        ) == "gcp"

    def test_resolve_provider_svc_overrides_all(self) -> None:
        assert resolve_provider(
            svc_cfg={"provider": "docker"},
            env_cfg={"provider": "gcp"},
            project_cfg={"provider": "aws"},
        ) == "docker"

    def test_dispatch_is_callable(self) -> None:
        assert callable(dispatch)

    def test_show_status_is_callable(self) -> None:
        assert callable(show_status)
