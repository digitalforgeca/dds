"""Custom provider — config-driven command templates for any platform.

Configure commands in dds.yaml under a `commands:` key. DDS handles orchestration
(sequencing, retries, variable interpolation). You define the shell commands.

Example:
```yaml
provider: custom
host: my-server

commands:
  container-app:
    ssh: true                    # Wrap commands in SSH to {host}
    build: "docker compose build {service}"
    deploy: "docker compose up -d {service}"
    rollback: "docker compose restart {service}"
    logs: "docker compose logs --tail {tail} {follow_flag} {service}"
    health: "curl -sf http://localhost:{port}{health_path}"
    status: "docker compose ps {service}"
    revisions: "docker images --format '{{.Tag}} {{.CreatedAt}}'"
  static-site:
    build: "npm run build"
    deploy: "rsync -avz {build_dir}/ {host}:{remote_path}/"
    status: "curl -sf http://{host}/{health_path}"
  database:
    provision: "docker exec {container} createdb -U {user} {database}"
    check: "docker exec {container} psql -U {user} -tAc \"SELECT 1 FROM pg_database WHERE datname='{database}'\""
    status: "docker exec {container} psql -U {user} -tAc \"SELECT pg_size_pretty(pg_database_size('{database}'))\""
    ssh: true
  preflight:
    checks:
      - "ssh -o BatchMode=yes {host} echo ok"
      - "docker compose version"
  secrets:
    fetch: "cat {vault_name} | grep '^{secret_name}=' | cut -d= -f2-"
```

Available variables (auto-populated from config + git):
- {name}, {service}, {app_name} — service identifiers
- {host}, {port}, {registry} — connection info
- {compose_file}, {compose_service}, {project_dir} — Docker config
- {build_dir}, {build_cmd}, {remote_path} — static site config
- {container}, {database}, {user} — database config
- {health_path}, {health_url} — health check config
- {git_hash}, {git_branch}, {build_time} — git info
- {tail}, {follow_flag} — log command helpers
- {image}, {target_revision} — set during build/rollback
- {vault_name}, {secret_name} — set during secret fetch
- Any key from dds.yaml (service > env > project)
"""

from __future__ import annotations

from dds.providers.custom.container import CustomContainerProvider
from dds.providers.custom.database import CustomDatabaseProvider
from dds.providers.custom.preflight import CustomPreflightProvider
from dds.providers.custom.secrets import CustomSecretProvider
from dds.providers.custom.static import CustomStaticProvider

_container = CustomContainerProvider()
_static = CustomStaticProvider()
_database = CustomDatabaseProvider()
_preflight = CustomPreflightProvider()
# Secret provider is initialized without a template — it will be resolved per-call
# from the config. For now, defaults to .env file fallback.
_secret = CustomSecretProvider()


def get_container_provider() -> CustomContainerProvider:
    return _container


def get_static_provider() -> CustomStaticProvider:
    return _static


def get_swa_provider():
    """Custom provider does not support SWA — use static-site instead."""
    from dds.console import console

    console.print(
        "[red]The 'custom' provider does not support 'swa' service type.[/red]\n"
        "  Use 'type: static-site' with custom deploy commands instead."
    )
    raise SystemExit(1)


def get_database_provider() -> CustomDatabaseProvider:
    return _database


def get_secret_provider() -> CustomSecretProvider:
    return _secret


def get_preflight_provider() -> CustomPreflightProvider:
    return _preflight
