"""Tests for the custom provider template engine."""

from dds.context import DeployContext
from dds.providers.custom.template import (
    SafeFormatter,
    build_variables,
    interpolate,
    resolve_commands,
)


class TestSafeFormatter:
    """Tests for SafeFormatter — unresolved placeholders stay intact."""

    def test_resolved_variables(self) -> None:
        f = SafeFormatter()
        result = f.format("deploy {service} to {host}", service="api", host="mybox")
        assert result == "deploy api to mybox"

    def test_unresolved_left_intact(self) -> None:
        f = SafeFormatter()
        result = f.format("deploy {service} to {host}", service="api")
        assert result == "deploy api to {host}"

    def test_all_unresolved(self) -> None:
        f = SafeFormatter()
        result = f.format("{a} {b} {c}")
        assert result == "{a} {b} {c}"

    def test_empty_template(self) -> None:
        f = SafeFormatter()
        result = f.format("")
        assert result == ""


class TestInterpolate:
    """Tests for the interpolate() function."""

    def test_basic_interpolation(self) -> None:
        result = interpolate(
            "docker compose up -d {service}",
            {"service": "api"},
        )
        assert result == "docker compose up -d api"

    def test_multiple_variables(self) -> None:
        result = interpolate(
            "ssh {host} docker compose -f {compose_file} up -d {service}",
            {"host": "mybox", "compose_file": "docker-compose.yml", "service": "api"},
        )
        assert result == "ssh mybox docker compose -f docker-compose.yml up -d api"

    def test_missing_variable_safe(self) -> None:
        result = interpolate(
            "curl -sf http://{host}:{port}/health",
            {"host": "mybox"},
        )
        assert result == "curl -sf http://mybox:{port}/health"


class TestBuildVariables:
    """Tests for build_variables()."""

    def test_basic_variables(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app", "port": "3000"},
            env_cfg={"resource_group": "prod-rg"},
            project_cfg={"project": "myproject", "host": "mybox"},
        )
        variables = build_variables(ctx)
        assert variables["name"] == "api"
        assert variables["service"] == "api"
        assert variables["port"] == "3000"
        assert variables["host"] == "mybox"
        assert variables["resource_group"] == "prod-rg"
        assert "git_hash" in variables

    def test_service_overrides_project(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app", "host": "override-host"},
            env_cfg={},
            project_cfg={"host": "project-host"},
        )
        variables = build_variables(ctx)
        # Service-level comes last so it overrides
        assert variables["host"] == "override-host"


class TestResolveCommands:
    """Tests for resolve_commands()."""

    def test_project_level_commands(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app"},
            env_cfg={},
            project_cfg={
                "commands": {
                    "container-app": {
                        "build": "docker build .",
                        "deploy": "docker compose up -d",
                    }
                }
            },
        )
        cmds = resolve_commands(ctx, "container-app")
        assert cmds["build"] == "docker build ."
        assert cmds["deploy"] == "docker compose up -d"

    def test_env_overrides_project(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app"},
            env_cfg={
                "commands": {
                    "container-app": {
                        "deploy": "kubectl apply -f deploy.yaml",
                    }
                }
            },
            project_cfg={
                "commands": {
                    "container-app": {
                        "build": "docker build .",
                        "deploy": "docker compose up -d",
                    }
                }
            },
        )
        cmds = resolve_commands(ctx, "container-app")
        assert cmds["build"] == "docker build ."  # Inherited from project
        assert cmds["deploy"] == "kubectl apply -f deploy.yaml"  # Overridden by env

    def test_service_overrides_all(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={
                "type": "container-app",
                "commands": {
                    "container-app": {
                        "build": "custom build",
                    }
                },
            },
            env_cfg={
                "commands": {
                    "container-app": {
                        "build": "env build",
                        "deploy": "env deploy",
                    }
                }
            },
            project_cfg={
                "commands": {
                    "container-app": {
                        "build": "project build",
                        "deploy": "project deploy",
                        "health": "project health",
                    }
                }
            },
        )
        cmds = resolve_commands(ctx, "container-app")
        assert cmds["build"] == "custom build"  # Service wins
        assert cmds["deploy"] == "env deploy"  # Env wins over project
        assert cmds["health"] == "project health"  # Inherited from project

    def test_no_commands_returns_empty(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app"},
            env_cfg={},
            project_cfg={},
        )
        cmds = resolve_commands(ctx, "container-app")
        assert cmds == {}

    def test_wrong_service_type_returns_empty(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app"},
            env_cfg={},
            project_cfg={
                "commands": {
                    "static-site": {
                        "deploy": "rsync something",
                    }
                }
            },
        )
        cmds = resolve_commands(ctx, "container-app")
        assert cmds == {}

    def test_preflight_checks_list(self) -> None:
        ctx = DeployContext(
            name="api",
            svc_cfg={"type": "container-app"},
            env_cfg={},
            project_cfg={
                "commands": {
                    "preflight": {
                        "checks": [
                            "ssh -o BatchMode=yes {host} echo ok",
                            "docker compose version",
                        ]
                    }
                }
            },
        )
        cmds = resolve_commands(ctx, "preflight")
        assert isinstance(cmds["checks"], list)
        assert len(cmds["checks"]) == 2
