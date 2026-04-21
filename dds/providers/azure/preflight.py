"""Azure-specific preflight checks."""

from __future__ import annotations

import subprocess
from typing import Any

from dds.preflight import CheckResult
from dds.providers.base import PreflightProvider


class AzurePreflightProvider(PreflightProvider):
    """Azure preflight checks — login status, ACR access."""

    def checks(self, project_cfg: dict[str, Any]) -> list[CheckResult]:
        """Run Azure-specific preflight checks."""
        results = [self._check_az_login()]

        registry = project_cfg.get("registry", "")
        if registry:
            results.append(self._check_acr_access(registry))

        return results

    @staticmethod
    def _check_az_login() -> CheckResult:
        """Check if the Azure CLI is authenticated."""
        try:
            result = subprocess.run(
                ["az", "account", "show", "--query", "name", "-o", "tsv"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return CheckResult(
                    name="Azure login",
                    passed=True,
                    message=f"Logged in as: {result.stdout.strip()}",
                )
            return CheckResult(
                name="Azure login",
                passed=False,
                message="Not logged in. Run 'az login' first.",
            )
        except (subprocess.TimeoutExpired, OSError):
            return CheckResult(
                name="Azure login", passed=False, message="az CLI not responding"
            )

    @staticmethod
    def _check_acr_access(registry: str) -> CheckResult:
        """Check if we can access the ACR registry."""
        registry_name = registry.split(".")[0]
        try:
            result = subprocess.run(
                [
                    "az", "acr", "show", "--name", registry_name,
                    "--query", "loginServer", "-o", "tsv",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return CheckResult(
                    name="ACR access",
                    passed=True,
                    message=f"Registry: {result.stdout.strip()}",
                )
            return CheckResult(
                name="ACR access",
                passed=False,
                message=f"Cannot access registry '{registry_name}'",
            )
        except (subprocess.TimeoutExpired, OSError):
            return CheckResult(
                name="ACR access", passed=False, message="az CLI not responding"
            )
