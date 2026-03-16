# DDS — Daedalus Deployment System

> *"He who would learn to fly one day must first learn to stand and walk and run and climb and dance; one cannot fly into flying."*

**Version:** 0.2.0 · **License:** MIT · **Python:** 3.10+

Cross-platform deployment tooling for Azure Container Apps, static sites, and managed services. One config file, one CLI, every environment.

---

## Why DDS?

Shell scripts aren't cross-platform, testable, or maintainable at scale. DDS replaces project-embedded bash deploy scripts with a proper standalone tool:

- **One `dds.yaml`** per project — declares all services, environments, and secrets
- **Preflight checks** before every deploy — catches auth, tooling, and access issues early
- **Health verification** after every deploy — auto-checks endpoints, suggests rollback on failure
- **Rollback in one command** — revert to any previous Container App revision instantly
- **Secrets from anywhere** — Azure Key Vault, `.env` files, environment variables, inline config
- **No CI required** — designed for direct deploys with immediate feedback (ACR remote builds, no local Docker needed)

---

## Installation

```bash
# From source (recommended during alpha)
pip install -e ".[dev]"

# Future: PyPI
pip install dds-deploy
pipx install dds-deploy
```

### Prerequisites

| Tool | Required | Notes |
|------|----------|-------|
| Python 3.10+ | ✅ | Runtime |
| Azure CLI (`az`) | ✅ | Must be logged in (`az login`) |
| Git | ✅ | Used for image tagging |
| Docker | ❌ | Only needed for `build_strategy: local` |

Run `dds preflight` to verify everything is ready.

---

## Quick Start

```bash
# 1. Initialize a config file
dds init

# 2. Edit dds.yaml for your project (see Configuration below)

# 3. Check prerequisites
dds preflight

# 4. Deploy everything to dev
dds deploy dev

# 5. Deploy a specific service
dds deploy dev -s api

# 6. Preview without executing
dds deploy dev --dry-run
```

---

## Commands

### `dds deploy <environment>`

Build, push, and deploy services. Runs preflight checks before and health verification after.

```bash
dds deploy dev                    # Deploy all services
dds deploy dev -s api             # Deploy only 'api'
dds deploy dev -s api -s worker   # Deploy multiple services
dds deploy dev --dry-run          # Preview actions
dds deploy dev --skip-preflight   # Skip pre-deploy checks
dds deploy dev --skip-health      # Skip post-deploy verification
```

### `dds status <environment>`

Show current deployment status for all services in an environment.

```bash
dds status dev
```

### `dds preflight`

Validate prerequisites without deploying. Checks Azure CLI, Git, Docker, login status, and ACR access.

```bash
dds preflight
```

### `dds rollback <environment> -s <service>`

Revert a Container App to a previous revision. Activates the target revision, redirects 100% traffic, and deactivates the old one.

```bash
dds rollback dev -s api              # Roll back to previous revision
dds rollback dev -s api -r rev-abc   # Roll back to a specific revision
```

### `dds revisions <environment> -s <service>`

Show revision history for a Container App — images, traffic weights, health state, creation times.

```bash
dds revisions dev -s api
```

### `dds logs <environment> -s <service>`

Tail or stream logs from a Container App.

```bash
dds logs dev -s api              # Last 100 lines
dds logs dev -s api -f           # Follow/stream in real-time
dds logs dev -s api -n 50        # Last 50 lines
dds logs dev -s api --system     # Platform/system logs
```

### `dds health <environment> -s <service>`

Run health checks on a deployed service. Verifies running state and hits the configured `health_path` endpoint.

```bash
dds health dev -s api
```

### `dds init`

Create a `dds.yaml` template in the current directory.

```bash
dds init
```

### Global Options

```bash
dds --version              # Show version
dds -c path/to/dds.yaml   # Use a custom config path
dds -v deploy dev          # Verbose output
```

---

## Configuration

DDS is configured via a `dds.yaml` file in your project root.

```yaml
# DDS — Daedalus Deployment System
project: my-project
registry: myregistry.azurecr.io
# key_vault: my-shared-keyvault        # Optional: project-wide Key Vault

environments:
  dev:
    resource_group: my-dev-rg
    container_env: my-dev-env
    # key_vault: my-dev-keyvault        # Optional: env-level Key Vault
    # env_file: .env.dev                # Optional: load vars from .env file

    services:
      api:
        type: container-app
        name: dev-api
        dockerfile: api/Dockerfile
        context: .
        build_strategy: acr             # acr (default) or local
        port: 3000
        min_replicas: 1
        max_replicas: 3
        health_path: /health
        build_args:                     # Build-time args (CACHE_BUST + GIT_HASH auto-added)
          NODE_ENV: production
        env:                            # Runtime environment variables
          PUBLIC_URL: https://api.example.com
        secrets:                        # Secrets from Key Vault or env vars
          - name: DATABASE_URL
            vault_key: db-connection-string
          - name: API_KEY
            env: MY_LOCAL_API_KEY

      app:
        type: static-site
        storage_account: mydevstorage
        build_cmd: npm run build
        build_dir: app/dist
        # install_deps: true            # Auto-install node deps (default: true)
        env:                            # Build-time env (NEXT_PUBLIC_*, VITE_*, etc.)
          NEXT_PUBLIC_API_URL: https://api.example.com

      db:
        type: database
        server: my-postgres-server
        database: mydb
        # charset: UTF8                 # Default
        # collation: en_US.utf8         # Default
```

### Service Types

| Type | Description | Deployer |
|------|-------------|----------|
| `container-app` | Azure Container Apps | Build → Push → Update → Health Check |
| `static-site` | Azure Blob Storage `$web` | Install → Build → Upload |
| `database` | Azure Postgres Flexible Server | Provision database |

### Build Strategies (Container Apps)

| Strategy | Docker Required | Description |
|----------|-----------------|-------------|
| `acr` (default) | No | Remote build on Azure Container Registry |
| `local` | Yes | Local Docker build, then push to ACR |

### Secrets Resolution

Secrets resolve in priority layers (later layers override earlier):

1. **`env_file`** — Load from a `.env` file (environment-level)
2. **`env`** — Inline key-value pairs (service-level)
3. **`secrets`** — Azure Key Vault (`vault_key`) or local environment variables (`env`)

---

## Architecture

```
dds/
├── dds/
│   ├── __init__.py         # Version (0.2.0)
│   ├── cli.py              # Click CLI — 8 commands
│   ├── config.py           # dds.yaml loader + template generator
│   ├── preflight.py        # Pre-deploy validation (az, git, docker, auth, ACR)
│   ├── secrets.py          # Secret resolution (Key Vault, .env, env vars)
│   ├── health.py           # Post-deploy health verification (retry + HTTP)
│   ├── rollback.py         # Revision rollback + history
│   ├── logs.py             # Container App log streaming (console + system)
│   ├── deployers/
│   │   ├── __init__.py     # Dynamic dispatch registry
│   │   ├── container.py    # Azure Container Apps (ACR + local Docker)
│   │   ├── static.py       # Azure Blob Storage static sites
│   │   └── database.py     # Managed Postgres provisioning
│   ├── builders/
│   │   ├── __init__.py
│   │   ├── docker.py       # Docker builds (local + ACR remote)
│   │   └── frontend.py     # Frontend builds (npm/pnpm/yarn/bun auto-detect)
│   └── utils/
│       ├── __init__.py
│       ├── azure.py        # Azure CLI wrappers (az, az_json)
│       └── git.py          # Git info (hash, branch, build time)
├── tests/                  # 34 tests
│   ├── test_builders.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_deployers.py
│   ├── test_preflight.py
│   └── test_secrets.py
├── pyproject.toml          # Hatchling build, Click + Rich + PyYAML deps
├── LICENSE                 # MIT
└── README.md
```

### Design Principles

- **No CI dependency** — deploys work from any terminal with `az` and `git`
- **ACR-first builds** — remote builds by default, no local Docker daemon required
- **Preflight before, health after** — catch problems on both ends of a deploy
- **Plugin architecture** — deployer registry is a dict; new service types are plug-and-play
- **Auto-injection** — `CACHE_BUST` and `GIT_HASH` build args added automatically
- **Package manager detection** — lockfile-based (`pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, or npm default)

---

## Development

```bash
# Clone
git clone git@github.com:digitalforgeca/dds.git
cd dds

# Install with dev deps
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check dds/ tests/
```

---

## Origin

DDS was born from the [TL4C](https://github.com/digitalforgeca/tl4c) project's `deploy/scripts/dds` — a 764-line bash script that grew organically. This is a clean-room rewrite as a standalone, testable, cross-platform tool.

The TL4C embedded DDS continues to work independently. This project does not modify or replace it.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT — [Digital Forge Studios](https://github.com/digitalforgeca) · 2026
