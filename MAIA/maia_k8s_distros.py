import os

dev_distros = ["microk8s", "k0s", "k3s"]


def get_api_port(k8s_distribution):
    port = None
    if k8s_distribution == "microk8s":
        port = 16443
    elif k8s_distribution == "k0s":
        port = 6443
    elif k8s_distribution == "k3s":
        port = None
    else:
        raise ValueError(f"K8S_DISTRIBUTION {os.environ['K8S_DISTRIBUTION']} not supported")
    return port


def get_gpu_operator_toolkit(k8s_distribution):

    if k8s_distribution == "microk8s":
        gpu_operator_values_toolkit = {
            "env": [
                {"name": "CONTAINERD_CONFIG", "value": "/var/snap/microk8s/current/args/containerd-template.toml"},
                {"name": "CONTAINERD_SOCKET", "value": "/var/snap/microk8s/common/run/containerd.sock"},
                {"name": "CONTAINERD_RUNTIME_CLASS", "value": "nvidia"},
                {"name": "CONTAINERD_SET_AS_DEFAULT", "value": "true"},
            ]
        }

    elif k8s_distribution == "rke2":
        gpu_operator_values_toolkit = {
            "driver": {"enabled": False},
            "env": [
                {"name": "CONTAINERD_SOCKET", "value": "/run/k3s/containerd/containerd.sock"},
                {"name": "CONTAINERD_CONFIG", "value": "/var/lib/rancher/rke2/agent/etc/containerd/config.toml.tmpl"},
                {"name": "CONTAINERD_RUNTIME_CLASS", "value": "nvidia"},
                {"name": "CONTAINERD_SET_AS_DEFAULT", "value": "true"},
            ],
        }
    elif k8s_distribution == "k0s":
        gpu_operator_values_toolkit = {
            "operator": {"defaultRuntime": "containerd"},
            "toolkit": {
                "env": [
                    {"name": "CONTAINERD_CONFIG", "value": "/etc/k0s/containerd.d/nvidia.toml"},
                    {"name": "CONTAINERD_SOCKET", "value": "/run/k0s/containerd.sock"},
                    {"name": "CONTAINERD_RUNTIME_CLASS", "value": "nvidia"},
                ]
            },
        }
    elif k8s_distribution == "k3s":
        ...
        # TODO: Implement k3s GPU operator toolkit
    else:
        raise ValueError(f"K8S_DISTRIBUTION {k8s_distribution} not supported")
    return gpu_operator_values_toolkit


def get_storage_class(k8s_distribution):
    if k8s_distribution in dev_distros:
        if k8s_distribution == "microk8s":
            storage_class = "microk8s-hostpath"
        elif k8s_distribution == "k0s":
            storage_class = "local-path"
        elif k8s_distribution == "k3s":
            storage_class = "local-path"
    else:
        storage_class = "local-path"
    return storage_class


def get_ingress_class(k8s_distribution):
    if k8s_distribution in dev_distros:
        ingress_class = "maia-core-traefik"
    else:
        ingress_class = "nginx"
    return ingress_class
