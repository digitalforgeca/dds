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


def _az_check(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    """Run an az CLI check command with timeout."""
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def check_az_login() -> CheckResult:
    """Check if the Azure CLI is authenticated."""
    try:
        result = _az_check(["az", "account", "show", "--query", "name", "-o", "tsv"])
        if result.returncode == 0 and result.stdout.strip():
            return CheckResult(
                name="Azure login", passed=True, message=f"Logged in as: {result.stdout.strip()}"
            )
        return CheckResult(
            name="Azure login", passed=False, message="Not logged in. Run 'az login' first."
        )
    except (subprocess.TimeoutExpired, OSError):
        return CheckResult(name="Azure login", passed=False, message="az CLI not responding")


def check_acr_access(registry: str) -> CheckResult:
    """Check if we can access the ACR registry."""
    if not registry:
        return CheckResult(name="ACR access", passed=False, message="No registry configured")

    registry_name = registry.split(".")[0]
    try:
        result = _az_check(
            ["az", "acr", "show", "--name", registry_name, "--query", "loginServer", "-o", "tsv"]
        )
        if result.returncode == 0 and result.stdout.strip():
            return CheckResult(
                name="ACR access", passed=True, message=f"Registry: {result.stdout.strip()}"
            )
        return CheckResult(
            name="ACR access", passed=False, message=f"Cannot access registry '{registry_name}'"
        )
    except (subprocess.TimeoutExpired, OSError):
        return CheckResult(name="ACR access", passed=False, message="az CLI not responding")


def check_docker() -> CheckResult:
    """Check if Docker is available and running."""
    if shutil.which("docker") is None:
        return CheckResult(name="Docker", passed=True, message="Not installed (ACR builds only)")

    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return CheckResult(name="Docker", passed=True, message="Running")
        return CheckResult(
            name="Docker",
            passed=True,
            message="Installed but not running (ACR builds still available)",
        )
    except (subprocess.TimeoutExpired, OSError):
        return CheckResult(name="Docker", passed=True, message="Installed (status unknown)")


def run_preflight(project_cfg: dict | None = None) -> list[CheckResult]:
    """Run all preflight checks and return results."""
    results = [
        check_command("Azure CLI", "az"),
        check_command("Git", "git"),
        check_az_login(),
        check_docker(),
    ]

    if project_cfg:
        registry = project_cfg.get("registry", "")
        if registry:
            results.append(check_acr_access(registry))

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
