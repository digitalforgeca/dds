"""Infrastructure provisioning — creates cloud resources for a project.

Replaces Terraform with idempotent az CLI commands.
Currently supports: AKS clusters, ACR registries, namespaces, cert-manager.
"""

from __future__ import annotations

import subprocess
from typing import Any

from dds.console import console
from dds.providers.azure.utils import az, az_json


def provision_kubernetes(project_cfg: dict[str, Any], env_cfg: dict[str, Any], verbose: bool = False) -> None:
    """Provision Kubernetes infrastructure for a project environment.

    Creates (idempotently):
    - ACR registry
    - AKS cluster with autoscaling
    - ACR ↔ AKS attachment
    - cert-manager + Let's Encrypt issuer
    - Application namespaces
    """
    registry = project_cfg.get("registry", "")
    registry_name = registry.split(".")[0] if registry else ""
    rg = project_cfg.get("kubernetes", {}).get("resource_group", env_cfg.get("resource_group", ""))
    location = env_cfg.get("location", project_cfg.get("location", "eastus2"))

    k8s_cfg = project_cfg.get("kubernetes", {})
    cluster_name = k8s_cfg.get("cluster", "")
    node_cfg = k8s_cfg.get("nodes", {})
    vm_size = node_cfg.get("vm_size", "Standard_B2ms")
    node_count = node_cfg.get("count", 1)
    min_count = node_cfg.get("min", 1)
    max_count = node_cfg.get("max", 3)
    k8s_version = node_cfg.get("version", "")

    if not cluster_name:
        console.print("[red]Error:[/red] kubernetes.cluster not set in dds.yaml")
        raise SystemExit(1)

    if not rg:
        console.print("[red]Error:[/red] resource_group not set in dds.yaml")
        raise SystemExit(1)

    console.print("═" * 60)
    console.print(f"  [bold]DDS Provision — Kubernetes Infrastructure[/bold]")
    console.print(f"  Resource Group: {rg} ({location})")
    console.print("═" * 60)
    console.print()

    # ── 1. ACR ───────────────────────────────────────────────────────────
    if registry_name:
        console.print(f"[bold]──── 1. ACR: {registry_name} ────[/bold]")
        if _resource_exists("acr", registry_name, rg):
            console.print(f"  ✅ ACR '{registry_name}' already exists.")
        else:
            console.print(f"  ⏳ Creating ACR '{registry_name}'...")
            az(
                f"acr create --resource-group {rg} --name {registry_name} "
                f"--sku Basic --location {location} --admin-enabled false",
                verbose=verbose,
            )
            console.print(f"  ✅ ACR '{registry_name}' created.")
        console.print()

    # ── 2. AKS Cluster ──────────────────────────────────────────────────
    console.print(f"[bold]──── 2. AKS: {cluster_name} ────[/bold]")
    if _resource_exists("aks", cluster_name, rg):
        console.print(f"  ✅ AKS '{cluster_name}' already exists.")
    else:
        console.print(f"  ⏳ Creating AKS '{cluster_name}'...")
        console.print(f"     VM: {vm_size} | Autoscale: {min_count}–{max_count}")

        # Detect log analytics workspace
        log_workspace_id = _find_log_workspace(rg, verbose)
        monitoring_args = ""
        if log_workspace_id:
            monitoring_args = f"--enable-addons monitoring --workspace-resource-id {log_workspace_id}"
            console.print(f"     Monitoring: attached to workspace")

        version_arg = f"--kubernetes-version {k8s_version}" if k8s_version else ""

        az(
            f"aks create --resource-group {rg} --name {cluster_name} "
            f"--location {location} {version_arg} "
            f"--node-count {node_count} --node-vm-size {vm_size} "
            f"--enable-cluster-autoscaler --min-count {min_count} --max-count {max_count} "
            f"--network-plugin kubenet --generate-ssh-keys "
            f"--enable-managed-identity --enable-oidc-issuer --enable-workload-identity "
            f"--enable-addons azure-keyvault-secrets-provider --enable-secret-rotation "
            f"{monitoring_args}".strip(),
            verbose=verbose,
        )
        console.print(f"  ✅ AKS '{cluster_name}' created.")
    console.print()

    # ── 3. Get Credentials ──────────────────────────────────────────────
    console.print(f"[bold]──── 3. Fetching kubeconfig ────[/bold]")
    az(
        f"aks get-credentials --resource-group {rg} --name {cluster_name} --overwrite-existing",
        verbose=verbose,
    )
    console.print(f"  ✅ kubeconfig updated for {cluster_name}.")
    console.print()

    # ── 4. ACR ↔ AKS Attachment ─────────────────────────────────────────
    if registry_name:
        console.print(f"[bold]──── 4. ACR ↔ AKS attachment ────[/bold]")
        console.print(f"  ⏳ Ensuring ACR '{registry_name}' is attached...")
        acr_attached = False
        try:
            az(
                f"aks update --resource-group {rg} --name {cluster_name} "
                f"--attach-acr {registry_name}",
                verbose=verbose,
            )
            console.print(f"  ✅ ACR attached via managed identity.")
            acr_attached = True
        except RuntimeError:
            console.print(f"  ⚠️  Managed identity ACR attach failed (RBAC).")
            console.print(f"  ⏳ Falling back to imagePullSecret...")

        if not acr_attached:
            # Fallback: enable admin on ACR and create pull secrets per namespace
            try:
                az(f"acr update --name {registry_name} --resource-group {rg} --admin-enabled true",
                   verbose=verbose)
                namespaces = _collect_namespaces(project_cfg)
                _create_acr_pull_secrets(registry_name, rg, namespaces, verbose)
                console.print(f"  ✅ ACR pull secrets created in {len(namespaces)} namespace(s).")
            except RuntimeError as e:
                console.print(f"  ⚠️  ACR pull secret fallback failed: {e}")
                console.print(f"     You may need to manually configure image pull access.")
        console.print()

    # ── 5. cert-manager ─────────────────────────────────────────────────
    cert_cfg = k8s_cfg.get("cert_manager", {})
    if cert_cfg.get("enabled", True):
        console.print(f"[bold]──── 5. cert-manager ────[/bold]")
        _install_cert_manager(cert_cfg, verbose)
        console.print()

    # ── 6. Namespaces ───────────────────────────────────────────────────
    namespaces = _collect_namespaces(project_cfg)
    if namespaces:
        console.print(f"[bold]──── 6. Namespaces ────[/bold]")
        for ns in namespaces:
            _ensure_namespace(ns, verbose)
        console.print()

    # ── Summary ──────────────────────────────────────────────────────────
    console.print("═" * 60)
    console.print(f"  [green]✅ Provisioning complete![/green]")
    console.print()
    if registry_name:
        console.print(f"  ACR:        {registry_name}.azurecr.io")
    console.print(f"  AKS:        {cluster_name} ({vm_size})")
    console.print(f"  Autoscale:  {min_count}–{max_count} nodes")
    if namespaces:
        console.print(f"  Namespaces: {', '.join(namespaces)}")
    console.print()
    console.print(f"  Next: dds deploy <env> -s <service>")
    console.print("═" * 60)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _resource_exists(resource_type: str, name: str, rg: str) -> bool:
    """Check if an Azure resource exists (idempotent guard)."""
    cmd_map = {
        "acr": f"acr show --name {name} --resource-group {rg}",
        "aks": f"aks show --name {name} --resource-group {rg}",
    }
    cmd = cmd_map.get(resource_type)
    if not cmd:
        return False

    try:
        result = subprocess.run(
            f"az {cmd} --query name -o tsv",
            shell=True, capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except (subprocess.TimeoutExpired, OSError):
        return False


def _find_log_workspace(rg: str, verbose: bool = False) -> str:
    """Find an existing Log Analytics workspace in the resource group."""
    try:
        result = subprocess.run(
            f"az monitor log-analytics workspace list --resource-group {rg} "
            f"--query '[0].id' -o tsv",
            shell=True, capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _install_cert_manager(cert_cfg: dict[str, Any], verbose: bool = False) -> None:
    """Install cert-manager via Helm if not already present."""
    from dds.providers.kubernetes.utils import helm, kubectl

    # Check if already installed
    result = subprocess.run(
        "kubectl get namespace cert-manager",
        shell=True, capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("  ✅ cert-manager already installed.")
    else:
        # Check helm is available
        import shutil
        if shutil.which("helm") is None:
            console.print("  ⚠️  Helm not found — skipping cert-manager install.")
            console.print("     Install helm, then re-run: dds provision <env>")
            return

        console.print("  ⏳ Installing cert-manager via Helm...")
        try:
            helm("repo add jetstack https://charts.jetstack.io", verbose=verbose)
        except RuntimeError:
            pass  # Already added
        try:
            helm("repo update jetstack", verbose=verbose)
        except RuntimeError:
            pass  # May fail transiently
        helm(
            "install cert-manager jetstack/cert-manager "
            "--namespace cert-manager --create-namespace "
            "--set crds.enabled=true --wait",
            verbose=verbose,
        )
        console.print("  ✅ cert-manager installed.")

    # Apply ClusterIssuer
    issuer_email = cert_cfg.get("email", "admin@guardrail.tech")
    ingress_class = cert_cfg.get("ingress_class", "webapprouting.kubernetes.azure.com")

    console.print("  ⏳ Applying Let's Encrypt ClusterIssuer...")
    issuer_yaml = f"""apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: {issuer_email}
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            ingressClassName: {ingress_class}"""

    result = subprocess.run(
        f"echo '{issuer_yaml}' | kubectl apply -f -",
        shell=True, capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("  ✅ ClusterIssuer 'letsencrypt-prod' applied.")
    else:
        console.print(f"  ⚠️  ClusterIssuer apply failed: {result.stderr.strip()}")


def _collect_namespaces(project_cfg: dict[str, Any]) -> list[str]:
    """Collect all namespaces referenced in environment configs."""
    namespaces: list[str] = []
    for env_name, env_cfg in project_cfg.get("environments", {}).items():
        k8s = env_cfg.get("kubernetes", {})
        ns = k8s.get("namespace", "")
        if ns and ns not in namespaces:
            namespaces.append(ns)
    return namespaces


def _create_acr_pull_secrets(
    registry_name: str, rg: str, namespaces: list[str], verbose: bool = False
) -> None:
    """Create imagePullSecrets in each namespace using ACR admin credentials."""
    from dds.providers.azure.utils import az

    creds_json = az(
        f"acr credential show --name {registry_name} --resource-group {rg} -o json",
        capture=True, verbose=verbose,
    )
    import json
    creds = json.loads(creds_json)
    username = creds.get("username", "")
    password = creds.get("passwords", [{}])[0].get("value", "")

    if not username or not password:
        raise RuntimeError(f"Could not retrieve ACR admin credentials for {registry_name}")

    for ns in namespaces:
        _ensure_namespace(ns, verbose)
        result = subprocess.run(
            f"kubectl create secret docker-registry acr-pull-secret "
            f"--namespace {ns} "
            f"--docker-server={registry_name}.azurecr.io "
            f"--docker-username={username} "
            f"--docker-password={password} "
            f"--dry-run=client -o yaml | kubectl apply -f -",
            shell=True, capture_output=True, text=True,
        )
        if result.returncode != 0:
            console.print(f"  \u26a0\ufe0f  Pull secret failed for {ns}: {result.stderr.strip()}")


def _ensure_namespace(namespace: str, verbose: bool = False) -> None:
    """Create a namespace if it doesn't exist."""
    result = subprocess.run(
        f"kubectl get namespace {namespace}",
        shell=True, capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print(f"  ✅ Namespace '{namespace}' exists.")
    else:
        from dds.providers.kubernetes.utils import kubectl

        kubectl(f"create namespace {namespace}", verbose=verbose)
        console.print(f"  ✅ Namespace '{namespace}' created.")
