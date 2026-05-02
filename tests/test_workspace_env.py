from __future__ import annotations

from types import SimpleNamespace
from typing import List

import pytest

from MAIA.workspace_env import (
    SSH_HOSTNAME_ANNOTATION,
    discover_workspace_env,
)


def _service(name, ports, annotations=None):
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, annotations=annotations or {}),
        spec=SimpleNamespace(ports=ports),
    )


def _port(name, port, node_port=None):
    return SimpleNamespace(name=name, port=port, node_port=node_port)


class FakeCoreV1:
    def __init__(self, services: List, raise_on_list: bool = False):
        self._services = services
        self._raise = raise_on_list
        self.calls = []

    def list_namespaced_service(self, namespace):
        self.calls.append(namespace)
        if self._raise:
            raise RuntimeError("forbidden")
        return SimpleNamespace(items=self._services)


def test_jupyterhub_path_uses_env_vars_only(tmp_path):
    """When JupyterHub injects all extraEnv, no K8s lookup happens."""
    env = {
        "JUPYTERHUB_USER": "alice@example.com",
        "JUPYTERHUB_BASE_URL": "/group-hub/",
        "HOSTNAME": "ssh.maia.example",
        "NAMESPACE": "alice-ns",
        "SSH_PORT_alice__at__example.com": "32022",
    }
    factory_called = []

    def factory():
        factory_called.append(True)
        return FakeCoreV1([])

    result = discover_workspace_env(
        env=env, namespace_file=str(tmp_path / "missing"), core_v1_factory=factory
    )

    assert result == {
        "JUPYTERHUB_USER": "alice@example.com",
        "JUPYTERHUB_BASE_URL": "/group-hub/",
        "NAMESPACE": "alice-ns",
        "SSH_HOSTNAME": "ssh.maia.example",
        "SSH_PORT": "32022",
    }
    # Everything resolved from env, so no K8s lookup needed.
    assert factory_called == []


def test_kubeflow_path_uses_namespace_file_and_service_lookup(tmp_path):
    """Kubeflow doesn't set JUPYTERHUB_USER; we recover via NB_PREFIX + K8s."""
    ns_file = tmp_path / "namespace"
    ns_file.write_text("alice-ns\n")

    env = {
        "NB_PREFIX": "/notebook/alice-ns/alice-at-example-com",
        # HOSTNAME is the pod name in Kubeflow — must be ignored.
        "HOSTNAME": "alice-at-example-com-0",
    }
    fake = FakeCoreV1(
        [
            _service(
                "jupyter-alice-at-example-com-ssh",
                ports=[_port("ssh", port=2022, node_port=32055)],
                annotations={SSH_HOSTNAME_ANNOTATION: "ssh.maia.example"},
            ),
        ]
    )

    result = discover_workspace_env(
        env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake
    )

    assert result == {
        "JUPYTERHUB_USER": "alice-at-example-com",
        "JUPYTERHUB_BASE_URL": "",
        "NAMESPACE": "alice-ns",
        "SSH_HOSTNAME": "ssh.maia.example",
        "SSH_PORT": "32055",
    }
    assert fake.calls == ["alice-ns"]


def test_kubeflow_falls_back_to_clusterip_port_when_no_node_port(tmp_path):
    ns_file = tmp_path / "namespace"
    ns_file.write_text("p1")

    env = {"NB_PREFIX": "/notebook/p1/bob"}
    fake = FakeCoreV1(
        [
            _service(
                "jupyter-bob-ssh",
                ports=[_port("ssh", port=2022, node_port=None)],
                annotations={SSH_HOSTNAME_ANNOTATION: "ssh.example"},
            ),
        ]
    )

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake)
    assert result["SSH_PORT"] == "2022"


def test_unrelated_services_are_ignored(tmp_path):
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {"NB_PREFIX": "/notebook/ns1/me"}
    fake = FakeCoreV1(
        [
            _service("jupyter-other-ssh", ports=[_port("ssh", 2022, 30000)]),
            _service("some-other-svc", ports=[_port("ssh", 2022, 30001)]),
            _service(
                "jupyter-me",
                ports=[_port("ssh", 2022, 30099)],
                annotations={SSH_HOSTNAME_ANNOTATION: "host.example"},
            ),
        ]
    )

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake)
    assert result["SSH_PORT"] == "30099"
    assert result["SSH_HOSTNAME"] == "host.example"


def test_missing_everything_returns_na(tmp_path):
    result = discover_workspace_env(
        env={}, namespace_file=str(tmp_path / "missing"), core_v1_factory=None
    )
    assert result == {
        "JUPYTERHUB_USER": "N/A",
        "JUPYTERHUB_BASE_URL": "",
        "NAMESPACE": "N/A",
        "SSH_HOSTNAME": "N/A",
        "SSH_PORT": "N/A",
    }


def test_kubeflow_without_ssh_hostname_annotation_returns_na(tmp_path):
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {"NB_PREFIX": "/notebook/ns1/me"}
    fake = FakeCoreV1(
        [_service("jupyter-me-ssh", ports=[_port("ssh", 2022, 30099)], annotations={})]
    )

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake)
    assert result["SSH_PORT"] == "30099"
    assert result["SSH_HOSTNAME"] == "N/A"


def test_k8s_api_failure_does_not_crash(tmp_path):
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {"NB_PREFIX": "/notebook/ns1/me"}
    fake = FakeCoreV1([], raise_on_list=True)

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake)
    assert result["SSH_PORT"] == "N/A"
    assert result["SSH_HOSTNAME"] == "N/A"
    assert result["NAMESPACE"] == "ns1"
    assert result["JUPYTERHUB_USER"] == "me"


def test_factory_exception_is_caught(tmp_path):
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {"NB_PREFIX": "/notebook/ns1/me"}

    def boom():
        raise RuntimeError("not in cluster")

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=boom)
    assert result["SSH_PORT"] == "N/A"
    assert result["SSH_HOSTNAME"] == "N/A"


def test_env_ssh_port_takes_precedence_over_service_lookup(tmp_path):
    """If JupyterHub has already injected SSH_PORT_<user>, don't override it."""
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {
        "JUPYTERHUB_USER": "me",
        "HOSTNAME": "ssh.example",
        "SSH_PORT_me": "11111",
    }
    fake = FakeCoreV1(
        [_service("jupyter-me-ssh", ports=[_port("ssh", 2022, 99999)],
                  annotations={SSH_HOSTNAME_ANNOTATION: "should-not-win"})]
    )

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake)
    assert result["SSH_PORT"] == "11111"
    assert result["SSH_HOSTNAME"] == "ssh.example"
    # When everything env-driven, K8s lookup is skipped entirely.
    assert fake.calls == []


def test_kubeflow_uses_jupyterhub_encoded_username_from_nb_prefix(tmp_path):
    """Kubeflow notebook names match the JupyterHub-encoded form used by the
    SSH service (e.g. ``alice-40example-2ecom`` for ``alice@example.com``)."""
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {"NB_PREFIX": "/notebook/ns1/alice-40example-2ecom"}
    fake = FakeCoreV1(
        [
            _service(
                "jupyter-alice-40example-2ecom-ssh",
                ports=[_port("ssh", 2022, 30001)],
                annotations={SSH_HOSTNAME_ANNOTATION: "host.example"},
            ),
        ]
    )

    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=lambda: fake)
    assert result["JUPYTERHUB_USER"] == "alice-40example-2ecom"
    assert result["SSH_PORT"] == "30001"
    assert result["SSH_HOSTNAME"] == "host.example"


def test_nb_prefix_with_trailing_slash(tmp_path):
    ns_file = tmp_path / "ns"
    ns_file.write_text("ns1")
    env = {"NB_PREFIX": "/notebook/ns1/me/"}
    result = discover_workspace_env(env=env, namespace_file=str(ns_file), core_v1_factory=None)
    assert result["JUPYTERHUB_USER"] == "me"


@pytest.mark.parametrize(
    "ns_content,expected",
    [("ns1\n", "ns1"), ("ns2", "ns2"), ("  ns3  \n", "ns3")],
)
def test_namespace_file_is_stripped(tmp_path, ns_content, expected):
    ns_file = tmp_path / "namespace"
    ns_file.write_text(ns_content)
    result = discover_workspace_env(
        env={}, namespace_file=str(ns_file), core_v1_factory=None
    )
    assert result["NAMESPACE"] == expected
