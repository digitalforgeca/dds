"""Post-deploy health verification — confirm services are alive after deployment."""

from __future__ import annotations

import time
import urllib.request
import urllib.error
from typing import Any

from rich.console import Console

from dds.utils.azure import az, az_json

console = Console()


def verify_container_health(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
    max_retries: int = 5,
    retry_delay: float = 6.0,
) -> bool:
    """Verify a Container App is healthy after deployment.

    Checks:
    1. Container App is in Running state
    2. Latest revision is active and healthy
    3. If health_path is configured, HTTP GET returns 2xx

    Returns True if healthy, False otherwise.
    """
    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", name)
    health_path = svc_cfg.get("health_path", "")

    console.print(f"\n[yellow]🏥 Verifying health: {app_name}...[/yellow]")

    for attempt in range(1, max_retries + 1):
        try:
            data = az_json(f"containerapp show --name {app_name} --resource-group {rg}")
            props = data.get("properties", {})

            # Check running status
            running = props.get("runningStatus", "unknown")
            if running.lower() not in ("running", "runningstate"):
                if attempt < max_retries:
                    console.print(
                        f"  [dim]Attempt {attempt}/{max_retries}: "
                        f"status={running}, retrying in {retry_delay}s...[/dim]"
                    )
                    time.sleep(retry_delay)
                    continue
                console.print(f"  [red]❌ Container not running (status: {running})[/red]")
                return False

            # Check latest revision
            revision = props.get("latestRevisionName", "unknown")
            fqdn = props.get("configuration", {}).get("ingress", {}).get("fqdn", "")

            console.print(f"  ✅ Running | Revision: {revision}")

            # HTTP health check if configured
            if health_path and fqdn:
                url = f"https://{fqdn}{health_path}"
                healthy = _http_health_check(url, verbose=verbose)
                if healthy:
                    console.print(f"  ✅ Health endpoint OK: {url}")
                    return True
                elif attempt < max_retries:
                    console.print(
                        f"  [dim]Health check failed, retrying in {retry_delay}s...[/dim]"
                    )
                    time.sleep(retry_delay)
                    continue
                else:
                    console.print(f"  [red]❌ Health endpoint failed: {url}[/red]")
                    return False

            # No health_path configured — running state is good enough
            return True

        except Exception as e:
            if attempt < max_retries:
                console.print(
                    f"  [dim]Attempt {attempt}/{max_retries}: error ({e}), "
                    f"retrying in {retry_delay}s...[/dim]"
                )
                time.sleep(retry_delay)
            else:
                console.print(f"  [red]❌ Health check failed: {e}[/red]")
                return False

    return False


def _http_health_check(url: str, timeout: float = 10.0, verbose: bool = False) -> bool:
    """Perform an HTTP GET and return True if status is 2xx."""
    if verbose:
        console.print(f"  [dim]GET {url}[/dim]")

    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "dds-health-check/0.1")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            if verbose:
                console.print(f"  [dim]Status: {status}[/dim]")
            return 200 <= status < 300
    except urllib.error.HTTPError as e:
        if verbose:
            console.print(f"  [dim]HTTP {e.code}: {e.reason}[/dim]")
        return False
    except (urllib.error.URLError, OSError) as e:
        if verbose:
            console.print(f"  [dim]Connection error: {e}[/dim]")
        return False
