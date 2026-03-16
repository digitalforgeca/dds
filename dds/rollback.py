"""Rollback support — revert Container Apps to a previous revision."""

from __future__ import annotations

import json
from typing import Any

from dds.console import console
from dds.context import DeployContext
from dds.utils.azure import az


def list_revisions(app_name: str, rg: str, verbose: bool = False) -> list[dict[str, Any]]:
    """List all revisions for a Container App, newest first."""
    output = az(
        f"containerapp revision list --name {app_name} --resource-group {rg} -o json",
        verbose=verbose,
        capture=True,
    )
    revisions = json.loads(output) if output else []
    revisions.sort(
        key=lambda r: r.get("properties", {}).get("createdTime", ""),
        reverse=True,
    )
    return revisions


def rollback_container_app(ctx: DeployContext, target_revision: str | None = None) -> bool:
    """Rollback a Container App to a previous revision."""
    console.print(f"\n[bold yellow]⏪ Rolling back: {ctx.app_name}[/bold yellow]")

    revisions = list_revisions(ctx.app_name, ctx.resource_group, verbose=ctx.verbose)
    if len(revisions) < 2 and target_revision is None:
        console.print("[red]No previous revision to roll back to.[/red]")
        return False

    # Find current active revision
    current = next(
        (r.get("name", "") for r in revisions if r.get("properties", {}).get("active")),
        None,
    )

    # Resolve target
    if target_revision is None:
        target_revision = next(
            (
                r.get("name", "")
                for r in revisions
                if r.get("name", "") != current
                and r.get("properties", {}).get("trafficWeight", 0) == 0
            ),
            None,
        )
        if target_revision is None:
            console.print("[red]No suitable previous revision found.[/red]")
            return False

    console.print(f"  Current: {current}\n  Target:  {target_revision}")

    # Activate → redirect traffic → deactivate old
    az(
        f"containerapp revision activate --name {ctx.app_name} "
        f"--resource-group {ctx.resource_group} --revision {target_revision}",
        verbose=ctx.verbose,
    )
    az(
        f"containerapp ingress traffic set --name {ctx.app_name} "
        f"--resource-group {ctx.resource_group} --revision-weight {target_revision}=100",
        verbose=ctx.verbose,
    )
    if current and current != target_revision:
        az(
            f"containerapp revision deactivate --name {ctx.app_name} "
            f"--resource-group {ctx.resource_group} --revision {current}",
            verbose=ctx.verbose,
        )

    console.print(f"\n[green]✅ Rolled back {ctx.app_name} → {target_revision}[/green]")
    return True


def show_revisions(ctx: DeployContext) -> None:
    """Display revision history for a Container App."""
    revisions = list_revisions(ctx.app_name, ctx.resource_group, verbose=ctx.verbose)

    if not revisions:
        console.print(f"[yellow]No revisions found for {ctx.app_name}.[/yellow]")
        return

    console.print(f"\n[bold]📜 Revisions: {ctx.app_name}[/bold]\n")
    for rev in revisions:
        props = rev.get("properties", {})
        active = props.get("active", False)
        weight = props.get("trafficWeight", 0)
        containers = props.get("template", {}).get("containers", [{}])
        image = containers[0].get("image", "?") if containers else "?"

        icon = "🟢" if active else "⚪"
        traffic = f" ({weight}%)" if weight > 0 else ""

        console.print(
            f"  {icon} {rev.get('name', '?')}{traffic}\n"
            f"     Image: {image}\n"
            f"     Created: {props.get('createdTime', '?')} | "
            f"Health: {props.get('healthState', '?')}"
        )
    console.print()
