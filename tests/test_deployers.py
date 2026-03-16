"""Tests for dds.deployers dispatch module."""

from dds.deployers import _DEPLOYER_REGISTRY, _import_func


class TestDeployerRegistry:
    """Tests for the deployer registry."""

    def test_known_types(self) -> None:
        assert "container-app" in _DEPLOYER_REGISTRY
        assert "static-site" in _DEPLOYER_REGISTRY
        assert "database" in _DEPLOYER_REGISTRY

    def test_all_deployers_importable(self) -> None:
        """Every registered deployer should be importable."""
        for svc_type, (module, deploy_fn, status_fn) in _DEPLOYER_REGISTRY.items():
            func = _import_func(module, deploy_fn)
            assert callable(func), f"{svc_type} deploy function not callable"
            func = _import_func(module, status_fn)
            assert callable(func), f"{svc_type} status function not callable"
