"""Rollback support — revert Container Apps to a previous revision."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from dds.utils.azure import az, az_json

console = Console()


def list_revisions(
    app_name: str,
    rg: str,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """List all revisions for a Container App, newest first."""
    import json

    output = az(
        f"containerapp revision list --name {app_name} --resource-group {rg} -o json",
        verbose=verbose,
        capture=True,
    )
    revisions = json.loads(output) if output else []

    # Sort by creation time descending
    revisions.sort(
        key=lambda r: r.get("properties", {}).get("createdTime", ""),
        reverse=True,
    )
    return revisions


def rollback_container_app(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    target_revision: str | None = None,
    verbose: bool = False,
) -> bool:
    """Rollback a Container App to a previous revision.

    If target_revision is None, rolls back to the most recent non-active revision.
    """
    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", name)

    console.print(f"\n[bold yellow]⏪ Rolling back: {app_name}[/bold yellow]")

    # Get current and available revisions
    revisions = list_revisions(app_name, rg, verbose=verbose)
    if len(revisions) < 2 and target_revision is None:
        console.print("[red]No previous revision to roll back to.[/red]")
        return False

    # Find current active revision
    current = None
    for rev in revisions:
        props = rev.get("properties", {})
        if props.get("active", False):
            current = rev.get("name", "")
            break

    if target_revision is None:
        # Find the most recent non-active revision
        for rev in revisions:
            rev_name = rev.get("name", "")
            props = rev.get("properties", {})
            if rev_name != current and props.get("trafficWeight", 0) == 0:
                target_revision = rev_name
                break

        if target_revision is None:
            console.print("[red]No suitable previous revision found.[/red]")
            return False

    console.print(f"  Current: {current}")
    console.print(f"  Target:  {target_revision}")

    # Activate the target revision
    console.print(f"\n[yellow]Activating revision: {target_revision}...[/yellow]")
    az(
        f"containerapp revision activate "
        f"--name {app_name} --resource-group {rg} "
        f"--revision {target_revision}",
        verbose=verbose,
    )

    # Redirect 100% traffic to the target revision
    console.print(f"[yellow]Redirecting traffic to {target_revision}...[/yellow]")
    az(
        f"containerapp ingress traffic set "
        f"--name {app_name} --resource-group {rg} "
        f"--revision-weight {target_revision}=100",
        verbose=verbose,
    )

    # Deactivate the old revision
    if current and current != target_revision:
        console.print(f"[yellow]Deactivating old revision: {current}...[/yellow]")
        az(
            f"containerapp revision deactivate "
            f"--name {app_name} --resource-group {rg} "
            f"--revision {current}",
            verbose=verbose,
        )

    console.print(f"\n[green]✅ Rolled back {app_name} → {target_revision}[/green]")
    return True


def show_revisions(
    name: str,
    svc_cfg: dict[str, Any],
    env_cfg: dict[str, Any],
    project_cfg: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Display revision history for a Container App."""
    rg = env_cfg.get("resource_group", "")
    app_name = svc_cfg.get("name", name)

    revisions = list_revisions(app_name, rg, verbose=verbose)

    if not revisions:
        console.print(f"[yellow]No revisions found for {app_name}.[/yellow]")
        return

    console.print(f"\n[bold]📜 Revisions: {app_name}[/bold]\n")

    for rev in revisions:
        rev_name = rev.get("name", "?")
        props = rev.get("properties", {})
        created = props.get("createdTime", "?")
        active = props.get("active", False)
        weight = props.get("trafficWeight", 0)
        health = props.get("healthState", "?")

        # Extract image from template
        containers = props.get("template", {}).get("containers", [{}])
        image = containers[0].get("image", "?") if containers else "?"

        status_icon = "🟢" if active else "⚪"
        traffic_str = f" ({weight}%)" if weight > 0 else ""

        console.print(
            f"  {status_icon} {rev_name}{traffic_str}\n"
            f"     Image: {image}\n"
            f"     Created: {created} | Health: {health}"
        )
    console.print()
