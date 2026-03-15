"""Configuration loading and validation for DDS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str = "dds.yaml") -> dict[str, Any] | None:
    """Load and validate a dds.yaml config file."""
    config_path = Path(path)
    if not config_path.exists():
        return None

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        return None

    # Validate required fields
    if "project" not in cfg:
        raise ValueError("dds.yaml must have a 'project' field.")
    if "environments" not in cfg:
        raise ValueError("dds.yaml must have an 'environments' section.")

    return cfg


def write_template(path: str = "dds.yaml") -> None:
    """Write a template dds.yaml."""
    template = """\
# DDS — Daedalus Deployment System
# Project configuration

project: my-project
registry: myregistry.azurecr.io

environments:
  dev:
    resource_group: my-dev-rg
    container_env: my-dev-env
    services:
      api:
        type: container-app
        name: dev-api
        dockerfile: api/Dockerfile
        context: .
        port: 3000
        min_replicas: 1
        max_replicas: 3
        health_path: /health
      app:
        type: static-site
        storage_account: mydevstorage
        build_cmd: npm run build
        build_dir: app/dist
        custom_domain: dev.example.com
"""
    with open(path, "w") as f:
        f.write(template)
