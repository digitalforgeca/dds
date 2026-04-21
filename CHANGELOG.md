# Changelog

All notable changes to DDS are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] — 2026-04-21

### Added
- **Custom provider** — config-driven command templates for any platform. Define shell commands in `dds.yaml` under `commands:`, DDS handles orchestration:
  - **Template engine** — `SafeFormatter` with safe interpolation (unresolved `{vars}` left intact, no KeyError). Variables auto-populated from config hierarchy + git info.
  - **Variable resolution** — service config > env config > project config > computed (git_hash, git_branch, build_time, etc.). Any key in `dds.yaml` is available as `{key}` in commands.
  - **Command resolution** — commands merge across config layers (project < env < service). Override specific commands at any level.
  - **SSH wrapping** — set `ssh: true` or `remote: true` in command section to wrap commands in `ssh {host}`.
  - **All lifecycle methods** — `container-app` (build, deploy, rollback, revisions, logs, system_logs, health, status), `static-site` (build, deploy, status), `database` (provision, check, status), `preflight` (checks list), `secrets` (fetch command or .env fallback).
  - **Health retries** — health command retried with configurable delay, same as built-in providers.
- **Template engine tests** — SafeFormatter, interpolation, build_variables, resolve_commands with full config hierarchy coverage.

## [0.5.0] — 2026-04-21

### Added
- **Docker/SSH provider** — deploy to any Docker host over SSH. Full provider implementation:
  - `container-app` → `docker compose build/up` on remote host. Three build strategies: `remote` (build on host), `local` (build+push+pull), `registry` (pull pre-built image).
  - `static-site` → build locally, `rsync` or `scp` to remote web root.
  - `database` → `docker exec` into Postgres container to create databases. Checks for existence before creating.
  - `secrets` → reads from local `.env` files (vault_name = file path, secret_name = key).
  - `preflight` → SSH connectivity check + remote `docker compose version` check.
  - `rollback` → pull specific image tag and restart, or restart from compose definition.
  - `logs` → `docker compose logs` with follow support.
  - `health` → `docker inspect` for container state + optional HTTP health endpoint.
- **SWA guard for Docker provider** — `get_swa_provider("docker")` exits with clear message directing to `static-site`.
- **SSH utilities** — `dds/providers/docker/utils.py` with `ssh()`, `resolve_host()`, `resolve_compose_file()`, `resolve_compose_project_dir()`.
- **Docker provider tests** — provider instantiation, SWA rejection.

## [0.4.0] — 2026-04-21

### Added
- **Provider abstraction layer** — `dds/providers/base.py` defines abstract base classes: `ContainerProvider`, `StaticProvider`, `SwaProvider`, `DatabaseProvider`, `SecretProvider`, `PreflightProvider`. New clouds implement these interfaces without touching core.
- **Provider registry** — `dds/providers/__init__.py` with lazy-loaded provider modules. `resolve_provider()` reads `provider` field from service → environment → project config (default: `"azure"`).
- **`provider` config field** — optional at project, environment, or service level. Environment overrides project; service overrides environment. Omitting defaults to `"azure"` for full backward compatibility.
- **`dds/providers/azure/`** — all Azure-specific logic extracted into a self-contained provider package: `container.py` (Container Apps build/deploy/rollback/logs/health), `static.py` (Blob Storage), `swa.py` (Static Web Apps), `database.py` (Postgres Flex), `secrets.py` (Key Vault), `preflight.py` (az login/ACR access), `utils.py` (az/az_json wrappers).
- **`dds/utils/shell.py`** — generic `run_cmd()` subprocess wrapper, decoupled from Azure.
- **Provider resolution in DeployContext** — `ctx.provider` property resolves from config hierarchy.
- **New deployer tests** — provider instantiation, `resolve_provider()` hierarchy, dispatch callability.

### Changed
- **Dispatch is now provider-aware** — `dds.deployers.dispatch()` resolves the provider from `DeployContext` and routes to the correct provider implementation.
- **CLI commands route through providers** — `rollback`, `revisions`, `logs`, `health` resolve the provider dynamically instead of importing Azure modules directly.
- **Secrets resolution uses SecretProvider** — vault lookups delegate to the resolved provider's `SecretProvider.fetch()` instead of hardcoded Azure Key Vault calls.
- **Preflight checks are provider-aware** — generic checks (git, docker) run always; provider-specific checks (az login, ACR access) delegate to `PreflightProvider.checks()`.
- **`builders/frontend.py`** now imports from `utils.shell` (not `utils.azure`), breaking a circular import.
- **`builders/docker.py`** retains generic local Docker build/push; ACR-specific `build_acr()` moved to Azure container provider.
- Old top-level modules (`health.py`, `rollback.py`, `logs.py`) and deployer modules (`deployers/container.py`, etc.) kept as thin backward-compat shims that delegate to providers.

## [0.3.0] — 2026-04-17

### Added
- **SWA deployer** — `type: swa` for Azure Static Web Apps. Fetches deployment token via `az staticwebapp secrets`, deploys via `npx @azure/static-web-apps-cli`. Includes CIFS mount workaround (runs `swa deploy` from `/tmp` to avoid .NET `ZipArchive` failures on Azure Files mounts).
- **Build env verification** — `verify_env` config block with `must_contain` and `must_not_contain` patterns. Greps built JS bundles post-build to catch environment mismatches (e.g., dev build with prod KC realm). Fails the deploy with a clear error.
- **Vite `.env.production` handling** — SWA deployer writes the target env file to `.env.production` (Vite's highest-priority file during builds) and restores the original after build. Prevents the silent override bug where `.env.production` trumps `.env`.
- **Environment access controls** — `access: restricted` + `allowed_deployers` list per environment. Checks deployer's git email against the allowlist before any deploy or rollback. Prevents unauthorized production deployments.
- **Git email in `git_info()`** — now returns `email` from `git config user.email` for access control checks.

### Changed
- Deploy and rollback commands now enforce access controls when `access: restricted` is set.
- Deployer registry now includes `swa` type alongside `container-app`, `static-site`, and `database`.

## [0.2.0] — 2026-03-16

### Added
- **Secrets management** — resolve from Azure Key Vault, `.env` files, environment variables, or inline config. Three-layer priority system.
- **Post-deploy health verification** — retry loop with HTTP endpoint checks. Auto-runs after container deploys, suggests rollback on failure. `--skip-health` flag to bypass.
- **Rollback support** — `dds rollback` reverts Container Apps to a previous revision. Activates target, redirects traffic, deactivates old revision.
- **Revision history** — `dds revisions` shows all revisions with images, traffic weights, health state, and creation times.
- **Log streaming** — `dds logs` tails or streams container app logs. Supports `--follow`, `--tail`, and `--system` (platform logs).
- **Health command** — `dds health` for standalone health checks without deploying.
- **CLI tests** — comprehensive Click CLI test suite.
- **Secrets tests** — `.env` file parsing, layered resolution, env var references.

### Changed
- Container deployer now uses `resolve_secrets()` for all environment variable injection.
- Deploy command now auto-verifies health post-deploy for container apps with `health_path`.
- Config template expanded with full documentation of all config keys.
- `dds --help` now shows 8 commands (was 4).

## [0.1.0] — 2026-03-15

### Added
- **Initial scaffold** — Click CLI with `deploy`, `status`, `preflight`, and `init` commands.
- **Container App deployer** — dual build strategy: ACR remote build (default) and local Docker build/push. Auto-injects `CACHE_BUST` and `GIT_HASH` build args.
- **Static site deployer** — frontend builder with package manager auto-detection (npm, pnpm, yarn, bun). Build-time env var injection. Upload to Azure Blob Storage `$web` container.
- **Database deployer** — Postgres Flexible Server database provisioning with status support.
- **Dynamic deployer registry** — plug-and-play service type dispatch.
- **Preflight checks** — validates Azure CLI, Git, Docker, Azure login, and ACR access.
- **Frontend builder** — lockfile-based package manager detection, dependency install, configurable build commands.
- **Docker builder** — local and ACR remote build paths with image tag resolution (git hash or explicit).
- **Config loader** — `dds.yaml` loading with validation and template generation.
- **17 tests** — config, deployers, builders, preflight.
- **Hatchling build** — `pyproject.toml` with Click, Rich, PyYAML dependencies.

## [0.0.0] — 2026-03-15

### Added
- Repository created with MIT license.
- Initial project structure (Icarus scaffold).

---

[0.2.0]: https://github.com/digitalforgeca/dds/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/digitalforgeca/dds/compare/v0.0.0...v0.1.0
[0.0.0]: https://github.com/digitalforgeca/dds/releases/tag/v0.0.0
