"""Kubernetes provider — AKS + Kustomize deployments, ACR builds, kubectl operations."""

from __future__ import annotations

from dds.providers.kubernetes.container import KubernetesContainerProvider
from dds.providers.kubernetes.preflight import KubernetesPreflightProvider
from dds.providers.kubernetes.secrets import KubernetesSecretProvider

# Singleton instances (stateless, safe to reuse)
_container = KubernetesContainerProvider()
_secret = KubernetesSecretProvider()
_preflight = KubernetesPreflightProvider()


def get_container_provider() -> KubernetesContainerProvider:
    return _container


def get_secret_provider() -> KubernetesSecretProvider:
    return _secret


def get_preflight_provider() -> KubernetesPreflightProvider:
    return _preflight
