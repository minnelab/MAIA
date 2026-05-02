"""Discover the runtime environment for a MAIA workspace notebook.

Used by ``docker/MAIA-Workspace/Welcome.ipynb`` so the welcome page works the
same way whether the pod was spawned by JupyterHub (which injects everything as
``extraEnv``) or by Kubeflow's Notebook Controller (which does not).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
SSH_HOSTNAME_ANNOTATION = "maia.kthcloud.io/ssh-hostname"


def _sanitize(jupyterhub_user: str) -> str:
    return jupyterhub_user.replace("@", "__at__")


def _user_from_nb_prefix(nb_prefix: str) -> Optional[str]:
    # Kubeflow Notebook Controller sets NB_PREFIX to "/notebook/<ns>/<name>".
    parts = [p for p in nb_prefix.split("/") if p]
    return parts[-1] if parts else None


def _read_namespace_file(path: str = NAMESPACE_FILE) -> Optional[str]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return p.read_text().strip() or None
    except OSError:
        return None


def _lookup_ssh_service(core_v1, namespace: str, jupyterhub_user: str):
    """Find the Service exposing this user's SSH port.

    Returns ``(ssh_port, ssh_hostname)`` or ``(None, None)``. Service is matched
    by name prefix (``jupyter-<user>`` with optional ``-ssh`` suffix to match
    both the legacy and current naming used by ``maia-namespace-base``).
    """
    try:
        services = core_v1.list_namespaced_service(namespace).items
    except Exception:
        return None, None

    candidates = (f"jupyter-{jupyterhub_user}-ssh", f"jupyter-{jupyterhub_user}")
    for svc in services:
        name = svc.metadata.name
        if name not in candidates:
            continue
        for port in svc.spec.ports or []:
            if port.name != "ssh":
                continue
            ssh_port = port.node_port or port.port
            annotations = svc.metadata.annotations or {}
            return (
                str(ssh_port) if ssh_port is not None else None,
                annotations.get(SSH_HOSTNAME_ANNOTATION),
            )
    return None, None


def discover_workspace_env(
    *,
    env: Optional[dict] = None,
    namespace_file: str = NAMESPACE_FILE,
    core_v1_factory: Optional[Callable[[], object]] = None,
) -> dict:
    """Return ``{JUPYTERHUB_USER, JUPYTERHUB_BASE_URL, NAMESPACE, SSH_HOSTNAME, SSH_PORT}``.

    Resolution order for each field:

    * JupyterHub-injected env vars (existing behaviour).
    * Kubeflow fallbacks: ``NB_PREFIX`` for the user, the service-account
      namespace file for the namespace, the per-namespace Service annotation
      ``maia.kthcloud.io/ssh-hostname`` for the host, and the matching Service
      port for ``SSH_PORT``.

    Anything still unknown becomes ``"N/A"`` so the notebook templates render
    cleanly.

    Parameters are injectable for tests; callers in production should leave
    them as default and only need ``from kubernetes import client, config``
    imported elsewhere if K8s lookups are desired.
    """
    env = os.environ if env is None else env

    jupyterhub_user = env.get("JUPYTERHUB_USER")
    if not jupyterhub_user:
        nb_prefix = env.get("NB_PREFIX")
        if nb_prefix:
            jupyterhub_user = _user_from_nb_prefix(nb_prefix)

    namespace = env.get("NAMESPACE") or _read_namespace_file(namespace_file)

    sanitized = _sanitize(jupyterhub_user) if jupyterhub_user else None
    ssh_port = env.get(f"SSH_PORT_{sanitized}") if sanitized else None
    # JupyterHub overrides HOSTNAME with the SSH host; Kubeflow leaves it as
    # the pod name, so trust HOSTNAME only when JUPYTERHUB_USER is also set.
    ssh_hostname = env.get("HOSTNAME") if env.get("JUPYTERHUB_USER") else None

    if (not ssh_port or not ssh_hostname) and core_v1_factory and namespace and jupyterhub_user:
        try:
            core_v1 = core_v1_factory()
        except Exception:
            core_v1 = None
        if core_v1 is not None:
            looked_up_port, looked_up_host = _lookup_ssh_service(core_v1, namespace, jupyterhub_user)
            ssh_port = ssh_port or looked_up_port
            ssh_hostname = ssh_hostname or looked_up_host

    return {
        "JUPYTERHUB_USER": jupyterhub_user or "N/A",
        "JUPYTERHUB_BASE_URL": env.get("JUPYTERHUB_BASE_URL", ""),
        "NAMESPACE": namespace or "N/A",
        "SSH_HOSTNAME": ssh_hostname or "N/A",
        "SSH_PORT": ssh_port or "N/A",
    }
