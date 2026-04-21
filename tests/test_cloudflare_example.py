"""Tests for the Cloudflare example config — validates the custom provider
template engine produces correct Wrangler commands from the example config."""

import yaml

from dds.context import DeployContext
from dds.providers.custom.template import build_variables, interpolate, resolve_commands


def _load_example():
    with open("examples/cloudflare.yaml") as f:
        return yaml.safe_load(f)


class TestCloudflareWorkerCommands:
    """Validate custom provider generates correct Wrangler commands for Workers."""

    def _make_ctx(self, service_name: str, env_name: str = "prod"):
        cfg = _load_example()
        env_cfg = cfg["environments"][env_name]
        svc_cfg = env_cfg["services"][service_name]
        return DeployContext(
            name=service_name,
            svc_cfg=svc_cfg,
            env_cfg=env_cfg,
            project_cfg=cfg,
        )

    def test_deploy_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["deploy"], variables)
        assert cmd == "wrangler deploy --name api --env production"

    def test_build_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["build"], variables)
        assert cmd == "wrangler deploy --dry-run --outdir .dds-build/api"

    def test_rollback_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["rollback"], variables)
        assert cmd == "wrangler rollback --name api"

    def test_logs_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["logs"], variables)
        assert cmd == "wrangler tail api --format pretty"

    def test_health_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["health"], variables)
        assert cmd == "curl -sf https://api.your-subdomain.workers.dev/health"

    def test_status_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["status"], variables)
        assert cmd == "wrangler deployments list --name api | head -10"

    def test_revisions_command(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["revisions"], variables)
        assert cmd == "wrangler deployments list --name api"


class TestCloudflarePageCommands:
    """Validate custom provider generates correct Wrangler commands for Pages."""

    def _make_ctx(self, service_name: str, env_name: str = "prod"):
        cfg = _load_example()
        env_cfg = cfg["environments"][env_name]
        svc_cfg = env_cfg["services"][service_name]
        return DeployContext(
            name=service_name,
            svc_cfg=svc_cfg,
            env_cfg=env_cfg,
            project_cfg=cfg,
        )

    def test_build_command(self) -> None:
        ctx = self._make_ctx("web")
        commands = resolve_commands(ctx, "static-site")
        variables = build_variables(ctx)
        cmd = interpolate(commands["build"], variables)
        assert cmd == "npm run build"

    def test_deploy_command(self) -> None:
        ctx = self._make_ctx("web")
        commands = resolve_commands(ctx, "static-site")
        variables = build_variables(ctx)
        cmd = interpolate(commands["deploy"], variables)
        assert cmd == "wrangler pages deploy dist --project-name my-app-web --branch main"

    def test_status_command(self) -> None:
        ctx = self._make_ctx("web")
        commands = resolve_commands(ctx, "static-site")
        variables = build_variables(ctx)
        cmd = interpolate(commands["status"], variables)
        assert cmd == "wrangler pages project list | grep my-app-web"


class TestCloudflareD1Commands:
    """Validate custom provider generates correct Wrangler commands for D1."""

    def _make_ctx(self, service_name: str, env_name: str = "prod"):
        cfg = _load_example()
        env_cfg = cfg["environments"][env_name]
        svc_cfg = env_cfg["services"][service_name]
        return DeployContext(
            name=service_name,
            svc_cfg=svc_cfg,
            env_cfg=env_cfg,
            project_cfg=cfg,
        )

    def test_provision_command(self) -> None:
        ctx = self._make_ctx("db")
        commands = resolve_commands(ctx, "database")
        variables = build_variables(ctx)
        cmd = interpolate(commands["provision"], variables)
        assert cmd == "wrangler d1 create my-app-db"

    def test_check_command(self) -> None:
        ctx = self._make_ctx("db")
        commands = resolve_commands(ctx, "database")
        variables = build_variables(ctx)
        cmd = interpolate(commands["check"], variables)
        assert cmd == "wrangler d1 list | grep my-app-db"

    def test_status_command(self) -> None:
        ctx = self._make_ctx("db")
        commands = resolve_commands(ctx, "database")
        variables = build_variables(ctx)
        cmd = interpolate(commands["status"], variables)
        assert cmd == "wrangler d1 info my-app-db"


class TestCloudflarePreflightCommands:
    """Validate preflight check interpolation."""

    def test_preflight_checks(self) -> None:
        cfg = _load_example()
        checks = cfg["commands"]["preflight"]["checks"]
        assert "wrangler whoami" in checks
        assert "node --version" in checks


class TestCloudflareStagingOverrides:
    """Validate that staging environment produces different commands."""

    def _make_ctx(self, service_name: str):
        cfg = _load_example()
        env_cfg = cfg["environments"]["staging"]
        svc_cfg = env_cfg["services"][service_name]
        return DeployContext(
            name=service_name,
            svc_cfg=svc_cfg,
            env_cfg=env_cfg,
            project_cfg=cfg,
        )

    def test_staging_deploy_uses_staging_env(self) -> None:
        ctx = self._make_ctx("api")
        commands = resolve_commands(ctx, "container-app")
        variables = build_variables(ctx)
        cmd = interpolate(commands["deploy"], variables)
        assert cmd == "wrangler deploy --name api --env staging"

    def test_staging_pages_uses_staging_branch(self) -> None:
        ctx = self._make_ctx("web")
        commands = resolve_commands(ctx, "static-site")
        variables = build_variables(ctx)
        cmd = interpolate(commands["deploy"], variables)
        assert cmd == "wrangler pages deploy dist --project-name my-app-web --branch staging"

    def test_staging_db_uses_staging_name(self) -> None:
        ctx = self._make_ctx("db")
        commands = resolve_commands(ctx, "database")
        variables = build_variables(ctx)
        cmd = interpolate(commands["provision"], variables)
        assert cmd == "wrangler d1 create my-app-db-staging"
