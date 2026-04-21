"""Preflight checks — validate prerequisites before deploying."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from dds.console import console


@dataclass
class CheckResult:
    """Result of a preflight check."""

    name: str
    passed: bool
    message: str


def check_command(name: str, cmd: str, version_flag: str = "--version") -> CheckResult:
    """Check if a CLI tool is available and get its version."""
    path = shutil.which(cmd)
    if path is None:
        return CheckResult(name=name, passed=False, message=f"'{cmd}' not found in PATH")

    try:
        result = subprocess.run([cmd, version_flag], capture_output=True, text=True, timeout=10)
        version = result.stdout.strip().split("\n")[0] if result.stdout else "unknown"
        return CheckResult(name=name, passed=True, message=version)
    except (subprocess.TimeoutExpired, OSError) as e:
        return CheckResult(
            name=name, passed=True, message=f"found at {path} (version check failed: {e})"
        )


def check_docker() -> CheckResult:
    """Check if Docker is available and running."""
    if shutil.which("docker") is None:
        return CheckResult(name="Docker", passed=True, message="Not installed (remote builds only)")

    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return CheckResult(name="Docker", passed=True, message="Running")
        return CheckResult(
            name="Docker",
            passed=True,
            message="Installed but not running (remote builds still available)",
        )
    except (subprocess.TimeoutExpired, OSError):
        return CheckResult(name="Docker", passed=True, message="Installed (status unknown)")


def run_preflight(project_cfg: dict | None = None) -> list[CheckResult]:
    """Run all preflight checks and return results."""
    # Generic checks (all providers)
    results = [
        check_command("Git", "git"),
        check_docker(),
    ]

    if project_cfg:
        # Provider-specific checks
        from dds.providers import get_preflight_provider, resolve_provider

        provider_name = resolve_provider(project_cfg=project_cfg)

        # Check for the provider's CLI tool
        _PROVIDER_CLI: dict[str, tuple[str, str]] = {
            "azure": ("Azure CLI", "az"),
            "aws": ("AWS CLI", "aws"),
            "gcp": ("Google Cloud SDK", "gcloud"),
        }
        cli_info = _PROVIDER_CLI.get(provider_name)
        if cli_info:
            results.insert(0, check_command(cli_info[0], cli_info[1]))

        # Provider-specific checks (login, registry access, etc.)
        try:
            provider = get_preflight_provider(provider_name)
            results.extend(provider.checks(project_cfg))
        except SystemExit:
            results.append(
                CheckResult(
                    name=f"Provider ({provider_name})",
                    passed=False,
                    message=f"Provider '{provider_name}' not available",
                )
            )

    return results


def print_preflight(results: list[CheckResult]) -> bool:
    """Print preflight results and return True if all passed."""
    console.print("\n[bold]🔍 Preflight Checks[/bold]\n")

    all_passed = True
    for r in results:
        icon = "✅" if r.passed else "❌"
        color = "green" if r.passed else "red"
        console.print(f"  {icon} [{color}]{r.name}[/{color}]: {r.message}")
        if not r.passed:
            all_passed = False

    console.print()
    msg = (
        "[green]All preflight checks passed.[/green]"
        if all_passed
        else "[red]Some preflight checks failed.[/red]"
    )
    console.print(f"{msg}\n")
    return all_passed
