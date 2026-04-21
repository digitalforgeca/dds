"""Abstract base classes for cloud providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from dds.context import DeployContext


class ContainerProvider(ABC):
    """Manages container-based service deployments (build, deploy, rollback, logs, health)."""

    @abstractmethod
    def build(self, ctx: DeployContext) -> str:
        """Build a container image. Returns the full image reference."""

    @abstractmethod
    def deploy(self, ctx: DeployContext, image: str) -> None:
        """Deploy a container image to the target environment."""

    @abstractmethod
    def status(self, ctx: DeployContext) -> None:
        """Print status for a container service."""

    @abstractmethod
    def rollback(self, ctx: DeployContext, target_revision: str | None = None) -> bool:
        """Rollback to a previous deployment. Returns True on success."""

    @abstractmethod
    def revisions(self, ctx: DeployContext) -> None:
        """Show revision/deployment history."""

    @abstractmethod
    def logs(
        self,
        ctx: DeployContext,
        follow: bool = False,
        tail: int = 100,
        system: bool = False,
    ) -> None:
        """Tail or stream logs from a container service."""

    @abstractmethod
    def health(self, ctx: DeployContext) -> bool:
        """Verify health of a deployed container. Returns True if healthy."""


class StaticProvider(ABC):
    """Manages static site deployments (blob storage, S3, GCS, etc.)."""

    @abstractmethod
    def deploy(self, ctx: DeployContext) -> None:
        """Build and upload a static site."""

    @abstractmethod
    def status(self, ctx: DeployContext) -> None:
        """Print status for a static site."""


class SwaProvider(ABC):
    """Manages Static Web App deployments (Azure SWA, Amplify, Firebase Hosting, etc.)."""

    @abstractmethod
    def deploy(self, ctx: DeployContext) -> None:
        """Build and deploy to a managed static web app service."""

    @abstractmethod
    def status(self, ctx: DeployContext) -> None:
        """Print status for a managed static web app."""


class DatabaseProvider(ABC):
    """Manages database provisioning and status."""

    @abstractmethod
    def provision(self, ctx: DeployContext) -> None:
        """Provision a database."""

    @abstractmethod
    def status(self, ctx: DeployContext) -> None:
        """Print status for a database."""


class SecretProvider(ABC):
    """Fetches secrets from a cloud secret manager (Key Vault, Secrets Manager, etc.)."""

    @abstractmethod
    def fetch(self, vault_name: str, secret_name: str, verbose: bool = False) -> str | None:
        """Fetch a secret value. Returns None if not found."""


class PreflightProvider(ABC):
    """Provider-specific preflight checks (auth, registry access, etc.)."""

    @abstractmethod
    def checks(self, project_cfg: dict[str, Any]) -> list[Any]:
        """Run provider-specific preflight checks. Returns list of CheckResult."""
