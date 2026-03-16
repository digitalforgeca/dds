"""Tests for dds.config module."""

import os
from pathlib import Path

import pytest
import yaml

from dds.config import load_config, write_template


class TestLoadConfig:
    """Tests for load_config()."""

    def test_missing_file_returns_none(self) -> None:
        result = load_config("/nonexistent/dds.yaml")
        assert result is None

    def test_valid_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "dds.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "project": "test-project",
                    "registry": "test.azurecr.io",
                    "environments": {
                        "dev": {
                            "resource_group": "test-rg",
                            "services": {"api": {"type": "container-app", "name": "dev-api"}},
                        }
                    },
                }
            )
        )
        result = load_config(str(cfg_file))
        assert result is not None
        assert result["project"] == "test-project"
        assert "dev" in result["environments"]

    def test_missing_project_raises(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "dds.yaml"
        cfg_file.write_text(yaml.dump({"environments": {"dev": {}}}))
        with pytest.raises(ValueError, match="project"):
            load_config(str(cfg_file))

    def test_missing_environments_raises(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "dds.yaml"
        cfg_file.write_text(yaml.dump({"project": "test"}))
        with pytest.raises(ValueError, match="environments"):
            load_config(str(cfg_file))

    def test_empty_yaml_returns_none(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "dds.yaml"
        cfg_file.write_text("")
        result = load_config(str(cfg_file))
        assert result is None


class TestWriteTemplate:
    """Tests for write_template()."""

    def test_creates_valid_yaml(self, tmp_path: Path) -> None:
        os.chdir(tmp_path)
        cfg_path = str(tmp_path / "dds.yaml")
        write_template(cfg_path)

        result = load_config(cfg_path)
        assert result is not None
        assert "project" in result
        assert "environments" in result
