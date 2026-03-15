# DDS — Daedalus Deployment System

> "He who would learn to fly one day must first learn to stand and walk and run and climb and dance; one cannot fly into flying."

Cross-platform deployment tooling for Azure Container Apps, static sites, and managed services.

## Why

Shell scripts are not cross-platform. They're brittle, hard to test, and limit deployment to Unix-like systems. DDS replaces project-embedded bash scripts with a standalone, testable, cross-platform deployment tool.

## Features (Planned)

- **Container Apps** — Build, push, and deploy to Azure Container Apps
- **Static Sites** — Build SPAs and deploy to Azure Blob Storage static hosting
- **Managed Services** — Provision and configure databases, key vaults, secrets
- **Multi-environment** — dev / uat / prd with environment-specific configs
- **Cross-platform** — Python 3.10+, runs on macOS, Linux, Windows, CI
- **Project config** — `dds.yaml` in project root defines deployment targets
- **Dry run** — Preview what would happen without making changes
- **Preflight checks** — Validate prerequisites before deploying

## Installation

```bash
pip install dds-deploy  # (future)
# or
pipx install dds-deploy
```

## Usage

```bash
# Deploy everything to dev
dds deploy dev

# Deploy only the API container
dds deploy dev --service api

# Deploy static frontend to blob storage
dds deploy dev --service app

# Status check
dds status dev

# Dry run
dds deploy dev --dry-run
```

## Project Config (`dds.yaml`)

```yaml
project: tl4c
registry: tl4cregistry.azurecr.io
environments:
  dev:
    resource_group: tl4c-dev-rg
    services:
      api:
        type: container-app
        name: dev-api
        dockerfile: api/Dockerfile
        context: .
      app:
        type: static-site
        storage_account: tl4cdevstorage
        build_cmd: npm run build
        build_dir: app/dist
```

## Architecture

```
dds/
├── dds/
│   ├── __init__.py
│   ├── cli.py          # Click CLI entrypoint
│   ├── config.py       # dds.yaml loader
│   ├── deployers/
│   │   ├── container.py    # Azure Container Apps
│   │   ├── static.py       # Azure Blob static sites
│   │   └── database.py     # Managed Postgres
│   ├── builders/
│   │   ├── docker.py       # Docker image builds
│   │   └── vite.py         # Vite/npm builds
│   └── utils/
│       ├── azure.py        # Azure CLI wrappers
│       └── git.py          # Git info (hash, branch)
├── tests/
├── dds.yaml            # Example config
├── pyproject.toml
└── README.md
```

## Origin

DDS was born from the TL4C project's `deploy/scripts/dds` — a 764-line bash script that grew organically. This is the clean-room rewrite as a proper standalone tool.

## License

MIT — Digital Forge Studios (digitalforgeca)
