"""Deployment context — shared state passed through the deploy pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeployContext:
    """Immutable context for a single service deployment.

    Replaces the (name, svc_cfg, env_cfg, project_cfg, verbose) tuple
    that was threaded through every function.
    """

    name: str
    svc_cfg: dict[str, Any]
    env_cfg: dict[str, Any]
    project_cfg: dict[str, Any]
    verbose: bool = False

    @property
    def app_name(self) -> str:
        return self.svc_cfg.get("name", self.name)

    @property
    def resource_group(self) -> str:
        return self.svc_cfg.get("resource_group", self.env_cfg.get("resource_group", ""))

    @property
    def registry(self) -> str:
        return self.project_cfg.get("registry", "")

    @property
    def registry_name(self) -> str:
        return self.registry.split(".")[0] if self.registry else ""

    @property
    def service_type(self) -> str:
        return self.svc_cfg.get("type", "")
