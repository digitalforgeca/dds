"""Tests for dds.builders modules."""

from pathlib import Path

from dds.builders.docker import resolve_image_tag
from dds.builders.frontend import detect_package_manager


class TestResolveImageTag:
    """Tests for resolve_image_tag()."""

    def test_explicit_tag(self) -> None:
        tag = resolve_image_tag(
            "api",
            {"registry": "myregistry.azurecr.io", "project": "myproject"},
            {"tag": "v1.2.3"},
        )
        assert tag == "myregistry.azurecr.io/myproject-api:v1.2.3"

    def test_default_uses_git_hash(self) -> None:
        tag = resolve_image_tag(
            "api",
            {"registry": "myregistry.azurecr.io", "project": "myproject"},
            {},
        )
        # Should be registry/project-name:something
        assert tag.startswith("myregistry.azurecr.io/myproject-api:")
        assert ":" in tag


class TestDetectPackageManager:
    """Tests for detect_package_manager()."""

    def test_default_is_npm(self, tmp_path: Path) -> None:
        assert detect_package_manager(str(tmp_path)) == "npm"

    def test_detects_pnpm(self, tmp_path: Path) -> None:
        (tmp_path / "pnpm-lock.yaml").touch()
        assert detect_package_manager(str(tmp_path)) == "pnpm"

    def test_detects_yarn(self, tmp_path: Path) -> None:
        (tmp_path / "yarn.lock").touch()
        assert detect_package_manager(str(tmp_path)) == "yarn"

    def test_detects_bun(self, tmp_path: Path) -> None:
        (tmp_path / "bun.lockb").touch()
        assert detect_package_manager(str(tmp_path)) == "bun"
