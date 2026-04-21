"""Custom preflight provider — config-driven preflight checks."""

from __future__ import annotations

import subprocess
from typing import Any

from dds.preflight import CheckResult
from dds.providers.base import PreflightProvider
from dds.providers.custom.template import SafeFormatter

_formatter = SafeFormatter()


class CustomPreflightProvider(PreflightProvider):
    """Preflight checks driven by command templates.

    Configure in dds.yaml:
    ```yaml
    commands:
      preflight:
        checks:
          - "ssh -o BatchMode=yes {host} echo ok"
          - "docker compose version"
          - "kubectl cluster-info"
    ```
    """

    def checks(self, project_cfg: dict[str, Any]) -> list[CheckResult]:
        results = []

        commands = project_cfg.get("commands", {}).get("preflight", {})
        check_list = commands.get("checks", [])

        if not check_list:
            results.append(
                CheckResult(
                    name="Custom preflight",
                    passed=True,
                    message="No checks configured",
                )
            )
            return results

        # Build variables from project config
        variables = {
            k: v for k, v in project_cfg.items() if isinstance(v, str)
        }

        for check_tmpl in check_list:
            cmd = _formatter.format(check_tmpl, **variables)
            # Use the first few words as the check name
            name = cmd.split()[0:3]
            name_str = " ".join(name)
            if len(name_str) > 40:
                name_str = name_str[:37] + "..."

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    output = result.stdout.strip().split("\n")[0][:80]
                    results.append(
                        CheckResult(
                            name=name_str,
                            passed=True,
                            message=output or "OK",
                        )
                    )
                else:
                    err = result.stderr.strip()[:100] or "Non-zero exit"
                    results.append(
                        CheckResult(
                            name=name_str,
                            passed=False,
                            message=err,
                        )
                    )
            except subprocess.TimeoutExpired:
                results.append(
                    CheckResult(name=name_str, passed=False, message="Timed out")
                )
            except OSError as e:
                results.append(
                    CheckResult(name=name_str, passed=False, message=str(e))
                )

        return results
