"""Docker/SSH preflight checks — verify SSH connectivity and Docker on remote."""

from __future__ import annotations

import subprocess
from typing import Any

from dds.preflight import CheckResult
from dds.providers.base import PreflightProvider


class DockerPreflightProvider(PreflightProvider):
    """Docker/SSH preflight checks — SSH connectivity, remote Docker."""

    def checks(self, project_cfg: dict[str, Any]) -> list[CheckResult]:
        """Run Docker/SSH-specific preflight checks."""
        results = []

        host = project_cfg.get("host", "")
        if host:
            results.append(self._check_ssh(host))
            results.append(self._check_remote_docker(host))
        else:
            results.append(
                CheckResult(
                    name="SSH host",
                    passed=False,
                    message="No 'host' configured in dds.yaml",
                )
            )

        return results

    @staticmethod
    def _check_ssh(host: str) -> CheckResult:
        """Check SSH connectivity to the host."""
        try:
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, "echo ok"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and "ok" in result.stdout:
                return CheckResult(
                    name=f"SSH ({host})", passed=True, message="Connected"
                )
            return CheckResult(
                name=f"SSH ({host})",
                passed=False,
                message=f"Connection failed: {result.stderr.strip()[:100]}",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                name=f"SSH ({host})", passed=False, message="Connection timed out"
            )
        except OSError as e:
            return CheckResult(
                name=f"SSH ({host})", passed=False, message=f"SSH not available: {e}"
            )

    @staticmethod
    def _check_remote_docker(host: str) -> CheckResult:
        """Check Docker is available on the remote host."""
        try:
            result = subprocess.run(
                [
                    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                    host, "docker compose version",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip().split("\n")[0]
                return CheckResult(
                    name=f"Docker Compose ({host})",
                    passed=True,
                    message=version,
                )
            return CheckResult(
                name=f"Docker Compose ({host})",
                passed=False,
                message="docker compose not found on remote host",
            )
        except (subprocess.TimeoutExpired, OSError):
            return CheckResult(
                name=f"Docker Compose ({host})",
                passed=False,
                message="Could not check (SSH failed)",
            )
