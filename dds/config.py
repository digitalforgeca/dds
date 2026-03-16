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
# key_vault: my-shared-keyvault  # Optional: project-wide Key Vault

environments:
  dev:
    resource_group: my-dev-rg
    container_env: my-dev-env
    # key_vault: my-dev-keyvault  # Optional: env-level Key Vault (overrides project)
    # env_file: .env.dev          # Optional: load env vars from file
    services:
      api:
        type: container-app
        name: dev-api
        dockerfile: api/Dockerfile
        context: .
        build_strategy: acr        # acr (default) or local
        port: 3000
        min_replicas: 1
        max_replicas: 3
        health_path: /health
        build_args:                 # Build-time args (CACHE_BUST + GIT_HASH auto-added)
          NODE_ENV: production
        env:                        # Runtime env vars
          PUBLIC_VAR: value
        # secrets:                  # Optional: Key Vault or env var references
        #   - name: DATABASE_URL
        #     vault_key: db-connection-string
        #   - name: API_KEY
        #     env: MY_LOCAL_API_KEY
      app:
        type: static-site
        storage_account: mydevstorage
        build_cmd: npm run build
        build_dir: app/dist
        env:                        # Build-time env (NEXT_PUBLIC_*, VITE_*, etc.)
          NEXT_PUBLIC_API_URL: https://api.example.com
      # db:
      #   type: database
      #   server: my-postgres-server
      #   database: mydb
"""
    with open(path, "w") as f:
        f.write(template)
