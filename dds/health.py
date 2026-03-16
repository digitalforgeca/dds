"""Post-deploy health verification — confirm services are alive after deployment."""

from __future__ import annotations

import time
import urllib.error
import urllib.request

from dds.console import console
from dds.context import DeployContext
from dds.utils.azure import az_json


def verify_container_health(
    ctx: DeployContext,
    max_retries: int = 5,
    retry_delay: float = 6.0,
) -> bool:
    """Verify a Container App is healthy after deployment.

    Checks running state + optional HTTP health_path endpoint.
    Returns True if healthy, False otherwise.
    """
    health_path = ctx.svc_cfg.get("health_path", "")
    console.print(f"\n[yellow]🏥 Verifying health: {ctx.app_name}...[/yellow]")

    for attempt in range(1, max_retries + 1):
        try:
            data = az_json(
                f"containerapp show --name {ctx.app_name} --resource-group {ctx.resource_group}"
            )
            props = data.get("properties", {})
            running = props.get("runningStatus", "unknown")

            if running.lower() not in ("running", "runningstate"):
                if attempt < max_retries:
                    _retry_msg(attempt, max_retries, f"status={running}", retry_delay)
                    time.sleep(retry_delay)
                    continue
                console.print(f"  [red]❌ Container not running (status: {running})[/red]")
                return False

            revision = props.get("latestRevisionName", "unknown")
            fqdn = props.get("configuration", {}).get("ingress", {}).get("fqdn", "")
            console.print(f"  ✅ Running | Revision: {revision}")

            if health_path and fqdn:
                url = f"https://{fqdn}{health_path}"
                if _http_check(url, verbose=ctx.verbose):
                    console.print(f"  ✅ Health endpoint OK: {url}")
                    return True
                elif attempt < max_retries:
                    _retry_msg(attempt, max_retries, "health check failed", retry_delay)
                    time.sleep(retry_delay)
                    continue
                else:
                    console.print(f"  [red]❌ Health endpoint failed: {url}[/red]")
                    return False

            return True  # No health_path — running state is sufficient

        except Exception as e:
            if attempt < max_retries:
                _retry_msg(attempt, max_retries, str(e), retry_delay)
                time.sleep(retry_delay)
            else:
                console.print(f"  [red]❌ Health check failed: {e}[/red]")
                return False

    return False


def _retry_msg(attempt: int, max_retries: int, reason: str, delay: float) -> None:
    console.print(
        f"  [dim]Attempt {attempt}/{max_retries}: {reason}, retrying in {delay}s...[/dim]"
    )


def _http_check(url: str, timeout: float = 10.0, verbose: bool = False) -> bool:
    """HTTP GET, return True if 2xx."""
    if verbose:
        console.print(f"  [dim]GET {url}[/dim]")
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "dds-health-check/0.2")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False
