"""Kubernetes-specific preflight checks."""

from __future__ import annotations

import subprocess
from typing import Any

from dds.preflight import CheckResult
from dds.providers.base import PreflightProvider


class KubernetesPreflightProvider(PreflightProvider):
    """Kubernetes preflight checks — kubectl context, AKS access, ACR access, helm."""

    def checks(self, project_cfg: dict[str, Any]) -> list[CheckResult]:
        """Run Kubernetes-specific preflight checks."""
        results = [
            self._check_kubectl(),
            self._check_az_login(),
        ]

        # Check AKS cluster connectivity
        k8s_cfg = project_cfg.get("kubernetes", {})
        cluster = k8s_cfg.get("cluster", "")
        rg = k8s_cfg.get("resource_group", "")
        if cluster and rg:
            results.append(self._check_aks_cluster(cluster, rg))

        # Check ACR access
        registry = project_cfg.get("registry", "")
        if registry:
            results.append(self._check_acr_access(registry))

        # Check helm (needed for cert-manager, etc.)
        results.append(self._check_helm())

        return results

    @staticmethod
    def _check_kubectl() -> CheckResult:
        """Check if kubectl is available and connected."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info", "--request-timeout=5s"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Extract cluster URL from output
                first_line = result.stdout.strip().split("\n")[0] if result.stdout else ""
                return CheckResult(
                    name="kubectl",
                    passed=True,
                    message=first_line or "Connected",
                )
            return CheckResult(
                name="kubectl",
                passed=False,
                message="kubectl not connected to a cluster. Run 'az aks get-credentials' first.",
            )
        except (subprocess.TimeoutExpired, OSError):
            return CheckResult(
                name="kubectl", passed=False, message="kubectl not found or not responding"
            )

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
    def _check_aks_cluster(cluster: str, resource_group: str) -> CheckResult:
        """Check if the AKS cluster exists and is accessible."""
        try:
            result = subprocess.run(
                [
                    "az", "aks", "show",
                    "--name", cluster,
                    "--resource-group", resource_group,
                    "--query", "provisioningState",
                    "-o", "tsv",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip().lower() == "succeeded":
                return CheckResult(
                    name=f"AKS cluster ({cluster})",
                    passed=True,
                    message=f"Provisioned in {resource_group}",
                )
            return CheckResult(
                name=f"AKS cluster ({cluster})",
                passed=False,
                message=f"Cluster not ready: {result.stdout.strip() or result.stderr.strip()}",
            )
        except (subprocess.TimeoutExpired, OSError):
            return CheckResult(
                name=f"AKS cluster ({cluster})",
                passed=False,
                message="az CLI not responding",
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

    @staticmethod
    def _check_helm() -> CheckResult:
        """Check if Helm is available."""
        try:
            result = subprocess.run(
                ["helm", "version", "--short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return CheckResult(
                    name="Helm",
                    passed=True,
                    message=result.stdout.strip(),
                )
            return CheckResult(
                name="Helm",
                passed=True,
                message="Not installed (optional — needed for cert-manager)",
            )
        except (subprocess.TimeoutExpired, OSError):
            return CheckResult(
                name="Helm",
                passed=True,
                message="Not installed (optional — needed for cert-manager)",
            )
