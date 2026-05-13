from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any

import kubernetes as k8s
import pytest
from kubernetes.client import ApiException


NAMESPACE = "default"
RESOURCE_CLAIM_NAME_MPS = "default-mps"
RESOURCE_CLAIM_NAME_TIMESLICE = "default-timeslice"
POD_NAME_PREFIX = "cuda-vectoradd-mps"
POD_COUNT = 3
POD_READY_TIMEOUT_SECONDS = 600
DELETE_TIMEOUT_SECONDS = 120
LOGGER = logging.getLogger(__name__)
LogEmitter = Callable[[str], None]


def _kubeconfig_from_env() -> str:
    kubeconfig = os.environ.get("KUBECONFIG")
    if not kubeconfig:
        pytest.skip("KUBECONFIG must be set to run NVIDIA DRA tests")
    return kubeconfig


def _kubernetes_clients() -> tuple[k8s.client.CoreV1Api, k8s.client.CustomObjectsApi]:
    k8s.config.load_kube_config(config_file=_kubeconfig_from_env())
    return k8s.client.CoreV1Api(), k8s.client.CustomObjectsApi()


def _json_for_log(value: Any) -> str:
    sanitized = k8s.client.ApiClient().sanitize_for_serialization(value)
    return json.dumps(sanitized, indent=2, sort_keys=True)


def _emit_for_pytest(message: str, output: LogEmitter | None = None) -> None:
    LOGGER.info("%s", message)
    if output is not None:
        output(message)


def _log_pod_content(core_api: k8s.client.CoreV1Api, pod: dict[str, Any], label: str, output: LogEmitter | None = None) -> None:
    pod_name = pod["metadata"]["name"]
    namespace = pod["metadata"].get("namespace", NAMESPACE)

    try:
        live_pod = core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as exc:
        if exc.status == 404:
            _emit_for_pytest(f"{label} pod {namespace}/{pod_name} not found", output)
            return
        raise

    _emit_for_pytest(f"{label} pod {namespace}/{pod_name} content:\n{_json_for_log(live_pod)}", output)

    try:
        pod_logs = core_api.read_namespaced_pod_log(name=pod_name, namespace=namespace)
    except ApiException as exc:
        LOGGER.warning("%s pod %s/%s logs unavailable: %s", label, namespace, pod_name, exc)
        if output is not None:
            output(f"{label} pod {namespace}/{pod_name} logs unavailable: {exc}")
        return

    _emit_for_pytest(f"{label} pod {namespace}/{pod_name} logs:\n{pod_logs}", output)


def _resource_claim_timeslice() -> dict[str, Any]:
    return {
        "apiVersion": "resource.k8s.io/v1",
        "kind": "ResourceClaim",
        "metadata": {
            "name": RESOURCE_CLAIM_NAME_TIMESLICE,
            "namespace": "default",
        },
        "spec": {
            "devices": {
                "requests": [
                    {
                        "name": "ts-gpu",
                        "exactly": {
                            "count": 1,
                            "deviceClassName": "gpu.nvidia.com",
                            "selectors": [
                                {
                                    "cel": {
                                        # This matches your DeviceClass's specific requirement for the 'type' attribute
                                        "expression": 'device.attributes["gpu.nvidia.com"].type == "gpu"',
                                    }
                                }
                            ],
                        },
                    }
                ],
                "config": [
                    {
                        "opaque": {
                            "driver": "gpu.nvidia.com",
                            "parameters": {
                                "apiVersion": "resource.nvidia.com/v1beta1",
                                "kind": "GpuConfig",
                                "sharing": {"strategy": "TimeSlicing"},
                            },
                        },
                        "requests": ["ts-gpu"],
                    }
                ]
            }
        },
    }


def _resource_claim_mps() -> dict[str, Any]:
    return {
        "apiVersion": "resource.k8s.io/v1",
        "kind": "ResourceClaim",
        "metadata": {
            "name": RESOURCE_CLAIM_NAME_MPS,
            "namespace": NAMESPACE,
        },
        "spec": {
            "devices": {
                "config": [
                    {
                        "opaque": {
                            "driver": "gpu.nvidia.com",
                            "parameters": {
                                "apiVersion": "resource.nvidia.com/v1beta1",
                                "kind": "GpuConfig",
                                "sharing": {
                                    "strategy": "MPS",
                                    "mpsConfig": {
                                        "defaultPinnedDeviceMemoryLimit": "2Gi",
                                        "defaultActiveThreadPercentage": 50,
                                    },
                                },
                            },
                        },
                        "requests": ["mps-gpu"],
                    }
                ],
                "requests": [
                    {
                        "exactly": {
                            "allocationMode": "ExactCount",
                            "count": 1,
                            "deviceClassName": "gpu.nvidia.com",
                            "selectors": [
                                {
                                    "cel": {
                                        "expression": 'device.attributes["gpu.nvidia.com"].type == "gpu"',
                                    }
                                }
                            ],
                        },
                        "name": "mps-gpu",
                    }
                ],
            }
        },
    }


def _pod(index: int) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"{POD_NAME_PREFIX}-{index}",
            "namespace": NAMESPACE,
        },
        "spec": {
            "restartPolicy": "OnFailure",
            "runtimeClassName": "nvidia",
            "containers": [
                {
                    "name": "cuda-vectoradd",
                    "image": "nvcr.io/nvidia/pytorch:24.07-py3",
                    "command": [
                        "sh",
                        "-c",
                        (
                            "python3 -c 'import torch; "
                            'a = torch.ones((512, 512, 512, 1), dtype=torch.float32, device="cuda"); '
                            'b = torch.ones((512, 512, 512, 1), dtype=torch.float32, device="cuda"); '
                            "c = a + b; print(torch.sum(c))'"
                        ),
                    ],
                    "resources": {
                        "claims": [
                            {
                                "name": "mps-gpu",
                                "request": "mps-gpu",
                            }
                        ]
                    },
                }
            ],
            "resourceClaims": [
                {
                    "name": "mps-gpu",
                    "resourceClaimName": RESOURCE_CLAIM_NAME_MPS,
                }
            ],
        },
    }


def _ignore_not_found(exc: ApiException) -> None:
    if exc.status != 404:
        raise exc


def _delete_test_resources(
    core_api: k8s.client.CoreV1Api,
    custom_api: k8s.client.CustomObjectsApi,
    pods: list[dict[str, Any]],
) -> None:
    for pod in pods:
        try:
            core_api.delete_namespaced_pod(
                name=pod["metadata"]["name"],
                namespace=pod["metadata"].get("namespace", NAMESPACE),
                grace_period_seconds=0,
            )
        except ApiException as exc:
            _ignore_not_found(exc)

    _wait_for_pods_to_delete(core_api, pods)

    for resource_claim_name in (RESOURCE_CLAIM_NAME_MPS, RESOURCE_CLAIM_NAME_TIMESLICE):
        try:
            custom_api.delete_namespaced_custom_object(
                group="resource.k8s.io",
                version="v1",
                namespace=NAMESPACE,
                plural="resourceclaims",
                name=resource_claim_name,
            )
        except ApiException as exc:
            _ignore_not_found(exc)

    _wait_for_resource_claim_to_delete(custom_api, RESOURCE_CLAIM_NAME_MPS)
    _wait_for_resource_claim_to_delete(custom_api, RESOURCE_CLAIM_NAME_TIMESLICE)


def _wait_for_pods_to_delete(core_api: k8s.client.CoreV1Api, pods: list[dict[str, Any]]) -> None:
    deadline = time.time() + DELETE_TIMEOUT_SECONDS
    pending_pods = {pod["metadata"]["name"]: pod for pod in pods}

    while pending_pods and time.time() < deadline:
        for pod_name, pod in list(pending_pods.items()):
            try:
                core_api.read_namespaced_pod(
                    name=pod_name,
                    namespace=pod["metadata"].get("namespace", NAMESPACE),
                )
            except ApiException as exc:
                if exc.status == 404:
                    pending_pods.pop(pod_name)
                else:
                    raise

        if pending_pods:
            time.sleep(2)

    assert not pending_pods, f"Timed out waiting for pods to delete: {sorted(pending_pods)}"


def _wait_for_resource_claim_to_delete(custom_api: k8s.client.CustomObjectsApi, resource_claim_name: str) -> None:
    deadline = time.time() + DELETE_TIMEOUT_SECONDS

    while time.time() < deadline:
        try:
            custom_api.get_namespaced_custom_object(
                group="resource.k8s.io",
                version="v1",
                namespace=NAMESPACE,
                plural="resourceclaims",
                name=resource_claim_name,
            )
        except ApiException as exc:
            if exc.status == 404:
                return
            raise

        time.sleep(2)

    pytest.fail(f"Timed out waiting for ResourceClaim {resource_claim_name} to delete")


def _wait_for_pods_to_succeed(core_api: k8s.client.CoreV1Api, pods: list[dict[str, Any]], output: LogEmitter | None = None) -> None:
    deadline = time.time() + POD_READY_TIMEOUT_SECONDS
    pending_pods = {pod["metadata"]["name"]: pod for pod in pods}
    last_phases: dict[str, str] = {}

    while pending_pods and time.time() < deadline:
        for pod_name, pod in list(pending_pods.items()):
            namespace = pod["metadata"].get("namespace", NAMESPACE)

            try:
                pod_status = core_api.read_namespaced_pod(name=pod_name, namespace=namespace).status
            except ApiException as exc:
                if exc.status == 404:
                    last_phases[pod_name] = "NotFound"
                    continue
                raise

            phase = pod_status.phase or "Unknown"
            last_phases[pod_name] = phase

            if phase == "Succeeded":
                pending_pods.pop(pod_name)
            elif phase == "Failed":
                _log_pod_content(core_api, pod, "failed", output)
                pytest.fail(f"Pod {pod_name} failed while requesting the shared ResourceClaim")

        if pending_pods:
            time.sleep(10)

    for pod in pending_pods.values():
        _log_pod_content(core_api, pod, "timeout", output)

    assert not pending_pods, f"Timed out waiting for pods to succeed. Last phases: {last_phases}"


def test_three_pods_can_request_the_same_dra_resource_claim(capfd: pytest.CaptureFixture[str]) -> None:
    core_api, custom_api = _kubernetes_clients()
    pods = [_pod(index) for index in range(1, POD_COUNT + 1)]

    def print_uncaptured(message: str) -> None:
        with capfd.disabled():
            print(f"\n{message}", flush=True)

    claim_name = pods[0]["spec"]["resourceClaims"][0]["resourceClaimName"]
    assert all(pod["spec"]["resourceClaims"][0]["resourceClaimName"] == claim_name for pod in pods)

    _emit_for_pytest(f"Generated pods requesting ResourceClaim {claim_name}:\n{_json_for_log(pods)}", print_uncaptured)

    _delete_test_resources(core_api, custom_api, pods)

    try:
        mps_claim = _resource_claim_mps()
        timeslice_claim = _resource_claim_timeslice()
        _emit_for_pytest(f"Creating ResourceClaim {RESOURCE_CLAIM_NAME_MPS}:\n{_json_for_log(mps_claim)}", print_uncaptured)
        custom_api.create_namespaced_custom_object(
            group="resource.k8s.io",
            version="v1",
            namespace=NAMESPACE,
            plural="resourceclaims",
            body=mps_claim,
        )
        _emit_for_pytest(
            f"Creating ResourceClaim {RESOURCE_CLAIM_NAME_TIMESLICE}:\n{_json_for_log(timeslice_claim)}",
            print_uncaptured,
        )
        custom_api.create_namespaced_custom_object(
            group="resource.k8s.io",
            version="v1",
            namespace=NAMESPACE,
            plural="resourceclaims",
            body=timeslice_claim,
        )

        for pod in pods:
            _emit_for_pytest(
                f"Creating pod {pod['metadata'].get('namespace', NAMESPACE)}/{pod['metadata']['name']}:\n{_json_for_log(pod)}",
                print_uncaptured,
            )
            created_pod = core_api.create_namespaced_pod(namespace=pod["metadata"].get("namespace", NAMESPACE), body=pod)
            _emit_for_pytest(
                f"Created pod {pod['metadata'].get('namespace', NAMESPACE)}/{pod['metadata']['name']}:\n{_json_for_log(created_pod)}",
                print_uncaptured,
            )

        _wait_for_pods_to_succeed(core_api, pods, print_uncaptured)
    finally:
        for pod in pods:
            _log_pod_content(core_api, pod, "final", print_uncaptured)
        _delete_test_resources(core_api, custom_api, pods)
