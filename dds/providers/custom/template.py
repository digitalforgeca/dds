"""Command template engine — interpolate and execute config-driven commands."""

from __future__ import annotations

import os
import subprocess
from string import Formatter
from typing import Any

from dds.console import console
from dds.context import DeployContext


class SafeFormatter(Formatter):
    """String formatter that leaves unresolved placeholders intact instead of raising."""

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, f"{{{key}}}")
        return super().get_value(key, args, kwargs)

    def format_field(self, value, format_spec):
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            return value  # Leave unresolved placeholders as-is
        return super().format_field(value, format_spec)


_formatter = SafeFormatter()


def build_variables(ctx: DeployContext) -> dict[str, str]:
    """Build the interpolation variable dict from DeployContext.

    Merges all config layers + computed properties into a flat dict.
    Service config wins over env config wins over project config.
    """
    from dds.utils.git import git_info

    info = git_info()

    variables: dict[str, str] = {}

    # Project-level config (lowest priority)
    for k, v in ctx.project_cfg.items():
        if isinstance(v, str):
            variables[k] = v

    # Environment-level config
    for k, v in ctx.env_cfg.items():
        if isinstance(v, str):
            variables[k] = v

    # Service-level config (highest priority)
    for k, v in ctx.svc_cfg.items():
        if isinstance(v, str):
            variables[k] = v

    # Computed/standard variables
    variables.update({
        "name": ctx.name,
        "app_name": ctx.app_name,
        "service": ctx.name,
        "service_type": ctx.service_type,
        "resource_group": ctx.resource_group,
        "registry": ctx.registry,
        "registry_name": ctx.registry_name,
        "provider": ctx.provider,
        "git_hash": info.get("hash", "unknown"),
        "git_branch": info.get("branch", "unknown"),
        "build_time": info.get("build_time", ""),
    })

    # Environment variables (prefixed with env.)
    # Allow ${ENV_VAR} syntax in commands too — handled at exec time
    for k, v in os.environ.items():
        variables[f"env.{k}"] = v

    return variables


def interpolate(template: str, variables: dict[str, str]) -> str:
    """Interpolate a command template with variables.

    Uses Python string formatting: {name}, {host}, {port}, etc.
    Unresolved placeholders are left as-is (no KeyError).
    """
    return _formatter.format(template, **variables)


def resolve_commands(ctx: DeployContext, service_type: str) -> dict[str, str | list[str]]:
    """Resolve the command templates for a service type.

    Looks up the `commands` dict from service → env → project config.
    Returns the commands for the given service_type section.

    Config structure:
    ```yaml
    commands:
      container-app:
        build: "docker build -t {image} ."
        deploy: "docker compose up -d {service}"
        rollback: "docker compose restart {service}"
        logs: "docker compose logs --tail {tail} {service}"
        health: "curl -sf http://{host}:{port}{health_path}"
        status: "docker compose ps {service}"
        revisions: "docker images {image} --format '{{.Tag}} {{.CreatedAt}}'"
      static-site:
        build: "{build_cmd}"
        deploy: "rsync -avz {build_dir}/ {host}:{remote_path}/"
        status: "ssh {host} ls -la {remote_path}/index.html"
      database:
        provision: "docker exec {container} createdb -U {user} {database}"
        status: "docker exec {container} psql -U {user} -c '\\l' | grep {database}"
      preflight:
        checks:
          - "ssh -o BatchMode=yes {host} echo ok"
          - "docker compose version"
      secrets:
        fetch: "cat {vault_name} | grep '^{secret_name}=' | cut -d= -f2-"
    ```
    """
    # Merge commands from all levels (project < env < service)
    commands: dict[str, Any] = {}

    project_cmds = ctx.project_cfg.get("commands", {}).get(service_type, {})
    if project_cmds:
        commands.update(project_cmds)

    env_cmds = ctx.env_cfg.get("commands", {}).get(service_type, {})
    if env_cmds:
        commands.update(env_cmds)

    svc_cmds = ctx.svc_cfg.get("commands", {}).get(service_type, {})
    if svc_cmds:
        commands.update(svc_cmds)

    return commands


def run_template(
    template: str,
    variables: dict[str, str],
    verbose: bool = False,
    capture: bool = False,
    host: str | None = None,
) -> subprocess.CompletedProcess:
    """Interpolate a template and execute it.

    If `host` is set, wraps the command in SSH.
    """
    cmd = interpolate(template, variables)

    if host:
        cmd = f"ssh -o BatchMode=yes -o ConnectTimeout=10 {host} {cmd!r}"

    if verbose:
        console.print(f"[dim]$ {cmd}[/dim]")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if verbose and result.stdout:
        console.print(result.stdout.rstrip())

    return result


def run_template_checked(
    template: str,
    variables: dict[str, str],
    action_name: str,
    verbose: bool = False,
    capture: bool = False,
    host: str | None = None,
) -> str:
    """Run a template command and raise on failure."""
    result = run_template(template, variables, verbose=verbose, capture=capture, host=host)

    if result.returncode != 0:
        cmd = interpolate(template, variables)
        console.print(f"[red]{action_name} failed:[/red] {cmd}")
        if result.stderr:
            console.print(result.stderr.strip()[:500])
        raise RuntimeError(f"{action_name} failed (exit {result.returncode})")

    return result.stdout.strip() if capture else ""
