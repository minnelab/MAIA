#!/usr/bin/env python

from __future__ import annotations

import os
import sys
import time
import uuid
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent
from typing import List, Optional, Tuple

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from loguru import logger

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
TRANSFER_IMAGE = "alpine:3.19"       # must have apk; rsync installed at runtime
RSYNC_PORT = 873
POD_READY_TIMEOUT = 300              # seconds to wait for transfer pods to start
TRANSFER_TIMEOUT = 7200             # seconds to wait for rsync to finish (2 h)
POLL_INTERVAL = 5
TRANSFER_LABEL = "maia-pod-transfer"

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
DESC = dedent("""
    Transfer a Kubernetes pod and its node-local Persistent Volumes to another node.

    Uses only Kubernetes-native operations — no SSH or host commands needed.

    The data path is a direct in-cluster rsync stream between two ephemeral pods,
    one on each node, so no data passes through the machine running this script.

    How it works (per PVC that has node affinity):
      1.  A temporary PVC is created with the same spec as the original.
      2.  An rsync *server* pod is pinned to the target node and mounts the temp PVC.
          With WaitForFirstConsumer storage classes (e.g. local-path) the provisioner
          creates the PV on the correct node when the server pod is scheduled.
      3.  A ClusterIP Service exposes the rsync daemon inside the cluster.
      4.  An rsync *client* pod is pinned to the source node and mounts the original
          PVC (read-only).  It pushes data directly to the server pod.
      5.  After a successful transfer the temporary resources are cleaned up.
      6.  The original PVC name is preserved: old PVC is deleted, new PVC (same name)
          is statically pre-bound to the migrated PV on the target node.
      7.  The workload's nodeSelector is updated and it is scaled back up.

    PVCs backed by cluster-wide storage (NFS, Ceph, cloud block/object) are left
    untouched; only their pod's scheduling is updated.
    """)  # noqa: E501

EPILOG = dedent("""
    Example calls:
    ::
        {f}  --namespace ml-project --pod-name jupyter-0 --target-node gpu-node-2
        {f}  --namespace default    --pod-name myapp-0   --target-node worker-3 \\
             --kubeconfig ~/.kube/config --transfer-timeout 14400 --delete-old-pvs
    """.format(f=Path(__file__).stem))


# ---------------------------------------------------------------------------
# Kubernetes helpers
# ---------------------------------------------------------------------------

def load_kube_config(kubeconfig: Optional[str]) -> None:
    if kubeconfig:
        config.load_kube_config(config_file=kubeconfig)
    elif os.environ.get("KUBECONFIG") or os.environ.get("KUBECONFIG_LOCAL"):
        kc = os.environ.get("KUBECONFIG_LOCAL") or os.environ["KUBECONFIG"]
        config.load_kube_config(config_file=kc)
    else:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()


def get_pod(ns: str, name: str, v1: client.CoreV1Api) -> client.V1Pod:
    return v1.read_namespaced_pod(name, ns)


def resolve_owner(
    ns: str,
    pod: client.V1Pod,
    apps: client.AppsV1Api,
) -> Tuple[str, object]:
    """Walk owner references: Pod → ReplicaSet → Deployment, or → StatefulSet."""
    for ref in pod.metadata.owner_references or []:
        if ref.kind == "StatefulSet":
            return "StatefulSet", apps.read_namespaced_stateful_set(ref.name, ns)
        if ref.kind == "ReplicaSet":
            rs = apps.read_namespaced_replica_set(ref.name, ns)
            for rref in rs.metadata.owner_references or []:
                if rref.kind == "Deployment":
                    return "Deployment", apps.read_namespaced_deployment(rref.name, ns)
    return "Pod", pod


def pvc_names_from_pod(pod: client.V1Pod) -> List[str]:
    return [
        v.persistent_volume_claim.claim_name
        for v in (pod.spec.volumes or [])
        if v.persistent_volume_claim
    ]


def read_pvc_and_pv(
    ns: str, pvc_name: str, v1: client.CoreV1Api
) -> Tuple[client.V1PersistentVolumeClaim, Optional[client.V1PersistentVolume]]:
    pvc = v1.read_namespaced_persistent_volume_claim(pvc_name, ns)
    pv = v1.read_persistent_volume(pvc.spec.volume_name) if pvc.spec.volume_name else None
    return pvc, pv


def pv_is_node_local(pv: client.V1PersistentVolume) -> bool:
    return bool(pv.spec.node_affinity) or bool(pv.spec.host_path)


def pv_node_name(pv: client.V1PersistentVolume) -> Optional[str]:
    na = pv.spec.node_affinity
    if na and na.required:
        for term in na.required.node_selector_terms:
            for expr in term.match_expressions or []:
                if expr.key == "kubernetes.io/hostname" and expr.operator == "In":
                    return expr.values[0]
    return None


# ---------------------------------------------------------------------------
# Wait helpers
# ---------------------------------------------------------------------------

def _deadline(timeout: int) -> float:
    return time.monotonic() + timeout


def wait_pod_gone(ns: str, name: str, v1: client.CoreV1Api, timeout: int = 180) -> bool:
    end = _deadline(timeout)
    while time.monotonic() < end:
        try:
            v1.read_namespaced_pod(name, ns)
        except ApiException as e:
            if e.status == 404:
                return True
            raise
        logger.debug(f"Waiting for pod {name} to terminate…")
        time.sleep(POLL_INTERVAL)
    return False


def wait_pod_phase(
    ns: str, name: str, phases: List[str], v1: client.CoreV1Api, timeout: int = POD_READY_TIMEOUT
) -> Optional[str]:
    end = _deadline(timeout)
    while time.monotonic() < end:
        try:
            pod = v1.read_namespaced_pod(name, ns)
            if pod.status.phase in phases:
                return pod.status.phase
            logger.debug(f"Pod {name}: {pod.status.phase}")
        except ApiException as e:
            if e.status != 404:
                raise
        time.sleep(POLL_INTERVAL)
    return None


def wait_pvc_bound(
    ns: str, name: str, v1: client.CoreV1Api, timeout: int = POD_READY_TIMEOUT
) -> Optional[client.V1PersistentVolumeClaim]:
    end = _deadline(timeout)
    while time.monotonic() < end:
        pvc = v1.read_namespaced_persistent_volume_claim(name, ns)
        if pvc.status.phase == "Bound":
            return pvc
        logger.debug(f"PVC {name}: {pvc.status.phase}")
        time.sleep(POLL_INTERVAL)
    return None


def wait_pv_phase(name: str, phase: str, v1: client.CoreV1Api, timeout: int = 90) -> bool:
    end = _deadline(timeout)
    while time.monotonic() < end:
        pv = v1.read_persistent_volume(name)
        if pv.status.phase == phase:
            return True
        logger.debug(f"PV {name}: {pv.status.phase}")
        time.sleep(POLL_INTERVAL)
    return False


# ---------------------------------------------------------------------------
# Workload scaling
# ---------------------------------------------------------------------------

def scale(kind: str, name: str, ns: str, replicas: int, apps: client.AppsV1Api) -> None:
    patch = {"spec": {"replicas": replicas}}
    if kind == "Deployment":
        apps.patch_namespaced_deployment_scale(name, ns, patch)
    elif kind == "StatefulSet":
        apps.patch_namespaced_stateful_set_scale(name, ns, patch)
    logger.info(f"Scaled {kind}/{name} → {replicas} replica(s)")


def set_node_selector(
    kind: str, name: str, ns: str, node: str, apps: client.AppsV1Api
) -> None:
    """Pin the workload's pod template to *node* via nodeSelector."""
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "nodeName": None,
                    "nodeSelector": {"kubernetes.io/hostname": node},
                }
            }
        }
    }
    if kind == "Deployment":
        apps.patch_namespaced_deployment(name, ns, patch)
    elif kind == "StatefulSet":
        apps.patch_namespaced_stateful_set(name, ns, patch)
    logger.info(f"Updated {kind}/{name}: nodeSelector → {node}")


# ---------------------------------------------------------------------------
# Transfer-pod factory helpers
# ---------------------------------------------------------------------------

_RSYNCD_CONF = "\n".join([
    "pid file = /var/run/rsyncd.pid",
    "lock file = /var/run/rsync.lock",
    "log file = /dev/stdout",
    "",
    "[data]",
    "    path = /data",
    "    comment = maia transfer",
    "    read only = false",
    "    use chroot = no",
    "    list = yes",
    "    uid = 0",
    "    gid = 0",
    "    timeout = 0",
    "    ignore errors = no",
    "    transfer logging = yes",
])


def _labels(tid: str, role: str) -> dict:
    return {TRANSFER_LABEL: tid, "role": role}


def create_configmap(ns: str, name: str, tid: str, v1: client.CoreV1Api) -> None:
    v1.create_namespaced_config_map(ns, client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=name, namespace=ns, labels={TRANSFER_LABEL: tid}),
        data={"rsyncd.conf": _RSYNCD_CONF},
    ))


def create_server_pod(
    ns: str, name: str, node: str, pvc: str, cm: str, tid: str, v1: client.CoreV1Api
) -> None:
    """Rsync daemon on target node; mounting *pvc* triggers WaitForFirstConsumer provisioning."""
    v1.create_namespaced_pod(ns, client.V1Pod(
        metadata=client.V1ObjectMeta(name=name, namespace=ns, labels=_labels(tid, "server")),
        spec=client.V1PodSpec(
            node_name=node,
            restart_policy="Never",
            containers=[client.V1Container(
                name="rsync",
                image=TRANSFER_IMAGE,
                command=["/bin/sh", "-c"],
                args=["apk add --no-cache rsync && "
                      "rsync --daemon --no-detach --config=/etc/rsyncd/rsyncd.conf"],
                ports=[client.V1ContainerPort(container_port=RSYNC_PORT)],
                volume_mounts=[
                    client.V1VolumeMount(name="data",   mount_path="/data"),
                    client.V1VolumeMount(name="config", mount_path="/etc/rsyncd", read_only=True),
                ],
                resources=client.V1ResourceRequirements(
                    requests={"cpu": "50m",  "memory": "64Mi"},
                    limits={"cpu":   "500m", "memory": "256Mi"},
                ),
            )],
            volumes=[
                client.V1Volume(name="data",
                                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=pvc)),
                client.V1Volume(name="config",
                                config_map=client.V1ConfigMapVolumeSource(name=cm)),
            ],
        ),
    ))
    logger.info(f"Created rsync server pod {name!r} on node {node!r}")


def create_service(ns: str, name: str, tid: str, v1: client.CoreV1Api) -> None:
    v1.create_namespaced_service(ns, client.V1Service(
        metadata=client.V1ObjectMeta(name=name, namespace=ns, labels={TRANSFER_LABEL: tid}),
        spec=client.V1ServiceSpec(
            selector=_labels(tid, "server"),
            ports=[client.V1ServicePort(port=RSYNC_PORT, target_port=RSYNC_PORT, protocol="TCP")],
            type="ClusterIP",
        ),
    ))
    logger.info(f"Created rsync service {name!r}")


def create_client_pod(
    ns: str, name: str, node: str, pvc: str, svc: str, tid: str, v1: client.CoreV1Api
) -> None:
    """Rsync client on source node; polls until server is ready then pushes data."""
    cmd = (
        f"apk add --no-cache rsync netcat-openbsd && "
        f"echo 'Waiting for rsync server {svc}…' && "
        f"until nc -z {svc} {RSYNC_PORT}; do sleep 3; done && "
        f"echo 'Server ready – starting transfer' && "
        f"rsync -avz --progress --stats /source/ rsync://{svc}:{RSYNC_PORT}/data/ && "
        f"echo 'Transfer complete'"
    )
    v1.create_namespaced_pod(ns, client.V1Pod(
        metadata=client.V1ObjectMeta(name=name, namespace=ns, labels=_labels(tid, "client")),
        spec=client.V1PodSpec(
            node_name=node,
            restart_policy="Never",
            containers=[client.V1Container(
                name="rsync",
                image=TRANSFER_IMAGE,
                command=["/bin/sh", "-c"],
                args=[cmd],
                volume_mounts=[client.V1VolumeMount(name="source", mount_path="/source", read_only=True)],
                resources=client.V1ResourceRequirements(
                    requests={"cpu": "100m", "memory": "128Mi"},
                    limits={"cpu":   "1",    "memory": "512Mi"},
                ),
            )],
            volumes=[
                client.V1Volume(name="source",
                                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                    claim_name=pvc, read_only=True)),
            ],
        ),
    ))
    logger.info(f"Created rsync client pod {name!r} on node {node!r}")


def _safe_delete_pod(ns: str, name: str, v1: client.CoreV1Api) -> None:
    try:
        v1.delete_namespaced_pod(name, ns, grace_period_seconds=0)
    except ApiException as e:
        if e.status != 404:
            logger.warning(f"Could not delete pod {name}: {e.reason}")


def _safe_delete_svc(ns: str, name: str, v1: client.CoreV1Api) -> None:
    try:
        v1.delete_namespaced_service(name, ns)
    except ApiException as e:
        if e.status != 404:
            logger.warning(f"Could not delete service {name}: {e.reason}")


def _safe_delete_cm(ns: str, name: str, v1: client.CoreV1Api) -> None:
    try:
        v1.delete_namespaced_config_map(name, ns)
    except ApiException as e:
        if e.status != 404:
            logger.warning(f"Could not delete configmap {name}: {e.reason}")


def _safe_delete_pvc(ns: str, name: str, v1: client.CoreV1Api) -> None:
    try:
        v1.delete_namespaced_persistent_volume_claim(name, ns)
    except ApiException as e:
        if e.status != 404:
            logger.warning(f"Could not delete PVC {name}: {e.reason}")


def _safe_delete_pv(name: str, v1: client.CoreV1Api) -> None:
    try:
        v1.delete_persistent_volume(name)
        logger.info(f"Deleted PV {name}")
    except ApiException as e:
        if e.status != 404:
            logger.warning(f"Could not delete PV {name}: {e.reason}")


# ---------------------------------------------------------------------------
# Core transfer logic
# ---------------------------------------------------------------------------

def run_rsync_transfer(
    ns: str,
    src_pvc: str,
    dst_pvc: str,
    src_node: str,
    dst_node: str,
    v1: client.CoreV1Api,
    transfer_timeout: int,
) -> bool:
    """
    Stream data from *src_pvc* (on *src_node*) to *dst_pvc* (on *dst_node*) using
    an in-cluster rsync daemon.  Returns True on success.
    """
    tid = str(uuid.uuid4())[:8]
    cm_name  = f"xfr-cfg-{tid}"
    srv_name = f"xfr-srv-{tid}"
    svc_name = f"xfr-svc-{tid}"
    cli_name = f"xfr-cli-{tid}"

    created: List[Tuple[str, str]] = []
    try:
        create_configmap(ns, cm_name, tid, v1);  created.append(("cm",  cm_name))
        create_server_pod(ns, srv_name, dst_node, dst_pvc, cm_name, tid, v1)
        created.append(("pod", srv_name))
        create_service(ns, svc_name, tid, v1);   created.append(("svc", svc_name))

        logger.info(f"Waiting for rsync server pod to reach Running "
                    f"(this also triggers PVC provisioning on {dst_node!r})…")
        phase = wait_pod_phase(ns, srv_name, ["Running"], v1, timeout=POD_READY_TIMEOUT)
        if phase != "Running":
            logger.error(f"Server pod {srv_name!r} did not reach Running within "
                         f"{POD_READY_TIMEOUT}s – check node resources and storage class")
            return False

        create_client_pod(ns, cli_name, src_node, src_pvc, svc_name, tid, v1)
        created.append(("pod", cli_name))

        logger.info(f"Transferring data: {src_pvc!r} → {dst_pvc!r} "
                    f"(timeout {transfer_timeout}s)…")
        phase = wait_pod_phase(
            ns, cli_name, ["Succeeded", "Failed"], v1, timeout=transfer_timeout
        )
        if phase == "Succeeded":
            logger.info("rsync finished successfully")
            return True
        logger.error(f"rsync client pod ended with phase={phase!r}; check pod logs for details")
        return False

    finally:
        for kind, name in reversed(created):
            if kind == "pod":
                _safe_delete_pod(ns, name, v1)
            elif kind == "svc":
                _safe_delete_svc(ns, name, v1)
            elif kind == "cm":
                _safe_delete_cm(ns, name, v1)


def migrate_pvc(
    ns: str,
    pvc_name: str,
    old_pv: client.V1PersistentVolume,
    src_node: str,
    dst_node: str,
    v1: client.CoreV1Api,
    transfer_timeout: int,
) -> None:
    """
    Move *pvc_name* from *src_node* to *dst_node*:
      1. Provision new PV on dst_node via a temp PVC + rsync server pod.
      2. Transfer data in-cluster.
      3. Rebind PVC name to new PV (preserving original PVC name).
    """
    old_pvc = v1.read_namespaced_persistent_volume_claim(pvc_name, ns)
    storage_req    = old_pvc.spec.resources.requests.get("storage", "1Gi")
    access_modes   = old_pvc.spec.access_modes
    sc_name        = old_pvc.spec.storage_class_name
    volume_mode    = old_pvc.spec.volume_mode or "Filesystem"
    old_pv_name    = old_pv.metadata.name
    old_reclaim    = old_pv.spec.persistent_volume_reclaim_policy

    tmp_name = f"{pvc_name[:40]}-xfr-{str(uuid.uuid4())[:6]}"
    logger.info(f"Creating temp PVC {tmp_name!r} (will be provisioned on {dst_node!r})…")

    v1.create_namespaced_persistent_volume_claim(ns, client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=tmp_name, namespace=ns),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=access_modes,
            resources=client.V1ResourceRequirements(requests={"storage": storage_req}),
            storage_class_name=sc_name,
            volume_mode=volume_mode,
        ),
    ))

    try:
        ok = run_rsync_transfer(
            ns, pvc_name, tmp_name, src_node, dst_node, v1, transfer_timeout
        )
        if not ok:
            raise RuntimeError(f"Data transfer for PVC {pvc_name!r} failed")

        # Retrieve the new PV that was provisioned on dst_node
        bound = wait_pvc_bound(ns, tmp_name, v1, timeout=60)
        if not bound:
            raise RuntimeError(f"Temp PVC {tmp_name!r} is not Bound after transfer")
        new_pv_name = bound.spec.volume_name
        logger.info(f"New PV {new_pv_name!r} provisioned on target node {dst_node!r}")

        # Guard both PVs against accidental deletion during the swap
        v1.patch_persistent_volume(new_pv_name, {"spec": {"persistentVolumeReclaimPolicy": "Retain"}})
        logger.debug(f"PV {new_pv_name!r} → Retain")
        if old_reclaim != "Retain":
            v1.patch_persistent_volume(old_pv_name, {"spec": {"persistentVolumeReclaimPolicy": "Retain"}})
            logger.debug(f"PV {old_pv_name!r} → Retain (was {old_reclaim!r})")

        # Delete old PVC → old PV becomes Released (data still on disk, Retain policy)
        logger.info(f"Deleting old PVC {pvc_name!r}…")
        v1.delete_namespaced_persistent_volume_claim(pvc_name, ns)

        # Delete temp PVC → new PV becomes Released (Retain policy keeps data)
        logger.info(f"Deleting temp PVC {tmp_name!r}…")
        v1.delete_namespaced_persistent_volume_claim(tmp_name, ns)
        tmp_name = None  # mark as gone

        wait_pv_phase(new_pv_name, "Released", v1, timeout=60)

        # Clear claimRef so new PV becomes Available for binding
        v1.patch_persistent_volume(new_pv_name, {"spec": {"claimRef": None}})
        wait_pv_phase(new_pv_name, "Available", v1, timeout=60)

        # Re-create PVC with the original name, statically pre-bound to the new PV
        logger.info(f"Re-creating PVC {pvc_name!r} pre-bound to {new_pv_name!r} on {dst_node!r}…")
        v1.create_namespaced_persistent_volume_claim(ns, client.V1PersistentVolumeClaim(
            metadata=client.V1ObjectMeta(name=pvc_name, namespace=ns),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=access_modes,
                resources=client.V1ResourceRequirements(requests={"storage": storage_req}),
                storage_class_name=sc_name,
                volume_mode=volume_mode,
                volume_name=new_pv_name,   # static pre-binding; prevents dynamic provisioning
            ),
        ))

        bound2 = wait_pvc_bound(ns, pvc_name, v1, timeout=120)
        if not bound2:
            raise RuntimeError(f"New PVC {pvc_name!r} failed to bind to {new_pv_name!r}")

        logger.info(f"PVC {pvc_name!r} migrated → node {dst_node!r}  PV: {new_pv_name!r}")

    except Exception:
        if tmp_name:
            _safe_delete_pvc(ns, tmp_name, v1)
        raise


# ---------------------------------------------------------------------------
# Standalone-pod recreation
# ---------------------------------------------------------------------------

def recreate_standalone_pod(
    ns: str,
    pod: client.V1Pod,
    dst_node: str,
    v1: client.CoreV1Api,
) -> None:
    """Delete the pod and re-create it pinned to *dst_node*."""
    logger.info(f"Deleting standalone pod {pod.metadata.name!r}…")
    v1.delete_namespaced_pod(pod.metadata.name, ns, grace_period_seconds=0)
    wait_pod_gone(ns, pod.metadata.name, v1, timeout=120)

    # Strip server-managed / read-only fields before re-creating
    spec = pod.spec
    spec.node_name = dst_node
    spec.node_selector = None

    new_pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=pod.metadata.name,
            namespace=ns,
            labels=pod.metadata.labels,
            annotations=pod.metadata.annotations,
        ),
        spec=spec,
    )
    v1.create_namespaced_pod(ns, new_pod)
    logger.info(f"Recreated pod {pod.metadata.name!r} on node {dst_node!r}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def get_arg_parser() -> ArgumentParser:
    p = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)
    p.add_argument("--namespace",   "-n", required=True,
                   help="Namespace of the pod to transfer")
    p.add_argument("--pod-name",    "-p", required=True,
                   help="Name of the pod to transfer")
    p.add_argument("--target-node", "-t", required=True,
                   help="Destination node name")
    p.add_argument("--kubeconfig",  "-k", default=None,
                   help="Path to kubeconfig (default: $KUBECONFIG / in-cluster)")
    p.add_argument("--transfer-image", default=TRANSFER_IMAGE,
                   help=f"Container image used for rsync pods (default: {TRANSFER_IMAGE}). "
                        "Must have apk or rsync pre-installed.")
    p.add_argument("--transfer-timeout", type=int, default=TRANSFER_TIMEOUT,
                   help=f"Max seconds to wait for each rsync transfer (default: {TRANSFER_TIMEOUT})")
    p.add_argument("--delete-old-pvs", action="store_true",
                   help="Delete old (Released) PVs after migration. "
                        "By default they are kept as a safety net.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be done, make no changes")
    return p


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = get_arg_parser().parse_args()

    global TRANSFER_IMAGE, TRANSFER_TIMEOUT
    TRANSFER_IMAGE   = args.transfer_image
    TRANSFER_TIMEOUT = args.transfer_timeout

    load_kube_config(args.kubeconfig)
    v1   = client.CoreV1Api()
    apps = client.AppsV1Api()

    ns          = args.namespace
    pod_name    = args.pod_name
    dst_node    = args.target_node

    # ------------------------------------------------------------------
    # 1. Gather information
    # ------------------------------------------------------------------
    logger.info(f"Inspecting pod {ns}/{pod_name}…")
    try:
        pod = get_pod(ns, pod_name, v1)
    except ApiException as e:
        if e.status == 404:
            logger.error(f"Pod {pod_name!r} not found in namespace {ns!r}")
            sys.exit(1)
        raise

    src_node = pod.spec.node_name
    logger.info(f"Source node : {src_node}")
    logger.info(f"Target node : {dst_node}")

    if src_node == dst_node:
        logger.warning("Pod is already on the target node — nothing to do.")
        sys.exit(0)

    try:
        v1.read_node(dst_node)
    except ApiException as e:
        if e.status == 404:
            logger.error(f"Target node {dst_node!r} does not exist in this cluster")
            sys.exit(1)
        raise

    kind, workload = resolve_owner(ns, pod, apps)
    wl_name = workload.metadata.name
    replicas = getattr(getattr(workload, "spec", None), "replicas", 1) or 1
    logger.info(f"Workload    : {kind}/{wl_name}  ({replicas} replica(s))")

    all_pvcs = pvc_names_from_pod(pod)
    logger.info(f"PVCs        : {all_pvcs or '(none)'}")

    to_migrate = []   # (pvc_name, pvc_obj, pv_obj)
    for pn in all_pvcs:
        pvc, pv = read_pvc_and_pv(ns, pn, v1)
        if pv and pv_is_node_local(pv):
            node = pv_node_name(pv) or "?"
            logger.info(f"  {pn}: PV {pv.metadata.name!r} on {node!r} → WILL MIGRATE")
            to_migrate.append((pn, pvc, pv))
        elif pv:
            logger.info(f"  {pn}: cluster-wide storage, no data migration needed")
        else:
            logger.warning(f"  {pn}: no bound PV found, skipping")

    # ------------------------------------------------------------------
    # 2. Dry-run short-circuit
    # ------------------------------------------------------------------
    if args.dry_run:
        logger.info("[dry-run] No changes will be made.")
        logger.info(f"[dry-run] Would migrate {len(to_migrate)} PVC(s): "
                    f"{[p[0] for p in to_migrate]}")
        logger.info(f"[dry-run] Would pin {kind}/{wl_name} nodeSelector → {dst_node!r}")
        sys.exit(0)

    # ------------------------------------------------------------------
    # 3. Scale down workload (releases PVC mounts so rsync can run clean)
    # ------------------------------------------------------------------
    if kind in ("Deployment", "StatefulSet"):
        scale(kind, wl_name, ns, 0, apps)
        logger.info(f"Waiting for pod {pod_name!r} to terminate…")
        if not wait_pod_gone(ns, pod_name, v1, timeout=180):
            logger.error("Pod did not terminate within 180s — aborting, scaling back up")
            scale(kind, wl_name, ns, replicas, apps)
            sys.exit(1)

    # ------------------------------------------------------------------
    # 4. Migrate each node-local PVC
    # ------------------------------------------------------------------
    failed = []
    for pvc_name, _pvc, pv in to_migrate:
        logger.info(f"── Migrating PVC {pvc_name!r} ──────────────────────────")
        try:
            migrate_pvc(
                ns, pvc_name, pv, src_node, dst_node, v1, args.transfer_timeout
            )
        except Exception as exc:
            logger.error(f"Migration of {pvc_name!r} failed: {exc}")
            failed.append(pvc_name)

    if failed:
        logger.error(f"Failed PVCs: {failed}")
        logger.warning("Scaling workload back up on source node to restore service.")
        if kind in ("Deployment", "StatefulSet"):
            scale(kind, wl_name, ns, replicas, apps)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 5. Optionally clean up old (Released) PVs
    # ------------------------------------------------------------------
    for _pvc_name, _pvc, pv in to_migrate:
        if args.delete_old_pvs:
            _safe_delete_pv(pv.metadata.name, v1)
        else:
            logger.info(f"Old PV {pv.metadata.name!r} left in Released state "
                        f"(use --delete-old-pvs to remove it automatically)")

    # ------------------------------------------------------------------
    # 6. Update workload scheduling and scale back up
    # ------------------------------------------------------------------
    if kind in ("Deployment", "StatefulSet"):
        set_node_selector(kind, wl_name, ns, dst_node, apps)
        scale(kind, wl_name, ns, replicas, apps)
    elif kind == "Pod":
        # Standalone pod: delete + recreate on target node
        recreate_standalone_pod(ns, pod, dst_node, v1)

    logger.info(f"✓ Pod {pod_name!r} successfully transferred to node {dst_node!r}")


if __name__ == "__main__":
    main()
