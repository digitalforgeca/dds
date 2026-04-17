# Changelog

All notable changes to DDS are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
