from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from minio import Minio
import kubernetes
import requests
import yaml
from kubernetes import config
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_minio_shareable_link(object_name, bucket_name, settings):
    try:
        client = Minio(
            settings.MINIO_PUBLIC_URL,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_PUBLIC_SECURE,
        )
        client.bucket_exists(settings.BUCKET_NAME)
        url = client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(hours=168),  # Link valid for 7 days
        )
        return url
    except Exception as e:
        logger.error(f"Error connecting to MinIO: {e}")
        return None


def label_pod_for_deletion(namespace, pod_name):
    """
    Label a Kubernetes pod for deletion by adding a 'terminate-at' annotation.

    Parameters
    ----------
    namespace : str
        The namespace of the pod.
    pod_name : str
        The name of the pod to be labeled for deletion.

    Raises
    ------
    Exception
        If there is an error labeling the pod for deletion.
    """

    # Load Kubernetes configuration
    # config.load_incluster_config()  # Use in-cluster config
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    # Label the pod for deletion
    body = {
        "metadata": {
            "annotations": {"terminate-at": (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        }
    }
    try:
        with kubernetes.client.ApiClient() as api_client:
            api_instance = kubernetes.client.CoreV1Api(api_client)
            api_instance.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
            logger.info(f"Pod {pod_name} labeled for deletion")
    except Exception as e:
        logger.error(f"Error labeling pod {pod_name} for deletion: {e}")


def get_namespaces(id_token, api_urls, private_clusters=None):
    """
    Retrieves a list of unique namespaces from multiple API URLs.

    Parameters
    ----------
    id_token : str
        The ID token used for authorization when accessing public clusters.
    api_urls : list
        A list of API URLs to query for namespaces.
    private_clusters : dict, optional
        A dictionary where keys are API URLs of private clusters and values are their respective tokens. Defaults to an empty dict.

    Returns
    -------
    list
        A list of unique namespace names retrieved from the provided API URLs.
    """
    if "BACKEND" in os.environ and os.environ["BACKEND"] == "compose":
        return [os.environ["PROJECT_NAME"]]
    if private_clusters is None:
        private_clusters = {}
    namespace_list = []
    for api_url in api_urls:
        if api_url in private_clusters:
            token = private_clusters[api_url]
            try:
                response = requests.get(
                    api_url + "/api/v1/namespaces", headers={"Authorization": "Bearer {}".format(token)}, verify=False
                )
            except Exception:
                continue
        else:
            try:
                response = requests.get(
                    api_url + "/api/v1/namespaces", headers={"Authorization": "Bearer {}".format(id_token)}, verify=False
                )
            except Exception:
                continue
        namespaces = json.loads(response.text)
        if "items" in namespaces:
            for namespace in namespaces["items"]:
                namespace_list.append(namespace["metadata"]["name"])
    return sorted(set(namespace_list))


def get_cluster_status(id_token, api_urls, cluster_names, private_clusters=None):
    """
    Retrieve the status of clusters and their nodes.

    Parameters
    ----------
    id_token : str
        The ID token for authentication.
    api_urls : list
        A list of API URLs for the clusters.
    cluster_names : dict
        A dictionary mapping API URLs to cluster names.
    private_clusters : dict, optional
        A dictionary mapping private cluster API URLs to their tokens. Defaults to {}.

    Returns
    -------
    tuple
        A tuple containing:
            - node_status_dict (dict): A dictionary mapping node names to their status and schedulability.
            - cluster_dict (dict): A dictionary mapping cluster names to their node names.
    """
    if private_clusters is None:
        private_clusters = {}
    cluster_dict = {}
    node_status_dict = {}
    for api_url in api_urls:

        if api_url in private_clusters:
            token = private_clusters[api_url]
            try:
                response = requests.get(
                    api_url + "/api/v1/nodes", headers={"Authorization": "Bearer {}".format(token)}, verify=False
                )
            except Exception:

                cluster = cluster_names[api_url]
                cluster_dict[cluster] = ["Cluster API Not Reachable"]
                node_status_dict["Cluster API Not Reachable"] = ["API"]
                continue
        else:
            if api_url.endswith("None"):
                cluster = cluster_names[api_url]
                cluster_dict[cluster] = ["Cluster API Not Reachable"]
                node_status_dict["Cluster API Not Reachable"] = ["API"]
                continue
            else:
                try:
                    response = requests.get(
                        api_url + "/api/v1/nodes", headers={"Authorization": "Bearer {}".format(id_token)}, verify=False
                    )
                except Exception:
                    cluster = cluster_names[api_url]
                    cluster_dict[cluster] = ["Cluster API Not Reachable"]
                    node_status_dict["Cluster API Not Reachable"] = ["API"]
                    continue
        nodes = json.loads(response.text)

        if "items" not in nodes:
            cluster = cluster_names[api_url]
            cluster_dict[cluster] = ["Cluster API Not Reachable"]
            node_status_dict["Cluster API Not Reachable"] = ["API"]
            continue
        for node in nodes["items"]:
            node_name = node["metadata"]["name"]
            node_status_dict[node_name] = []
            cluster = cluster_names[api_url]
            if cluster in cluster_dict:
                cluster_dict[cluster].append(node_name)
            else:
                cluster_dict[cluster] = [node_name]
            for condition in node["status"]["conditions"]:
                if condition["type"] == "Ready":
                    node_status_dict[node_name].append(condition["status"])

            if "unschedulable" in node["spec"]:
                node_status_dict[node_name].append(node["spec"]["unschedulable"])
            else:
                node_status_dict[node_name].append(False)
    return node_status_dict, cluster_dict


def get_available_resources(id_token, api_urls, cluster_names, private_clusters=None):
    """
    Retrieves available GPU, CPU, and RAM resources from multiple Kubernetes clusters.

    Parameters
    ----------
    id_token : str
        The ID token for authentication.
    api_urls : list
        List of API URLs for the Kubernetes clusters.
    cluster_names : dict
        Dictionary mapping API URLs to cluster names.
    private_clusters : list, optional
        List of private clusters with their tokens. Defaults to {}.

    Returns
    -------
    tuple
        A tuple containing:
            - gpu_dict (dict): Dictionary with GPU availability information for each node.
            - cpu_dict (dict): Dictionary with CPU availability information for each node.
            - ram_dict (dict): Dictionary with RAM availability information for each node.
            - gpu_allocations (dict): Dictionary with GPU allocation details for each pod.
    """
    if private_clusters is None:
        private_clusters = {}
    gpu_dict = {}
    cpu_dict = {}
    ram_dict = {}
    gpu_allocations = {}

    for api_url in api_urls:
        cluster_name = cluster_names[api_url]
        if api_url in private_clusters:
            token = private_clusters[api_url]
            try:
                response = requests.get(
                    api_url + "/api/v1/pods", headers={"Authorization": "Bearer {}".format(token)}, verify=False
                )
                pods = json.loads(response.text)
                response = requests.get(
                    api_url + "/api/v1/nodes", headers={"Authorization": "Bearer {}".format(token)}, verify=False
                )

                nodes = json.loads(response.text)

            except Exception:
                continue

        else:
            try:
                response = requests.get(
                    api_url + "/api/v1/pods", headers={"Authorization": "Bearer {}".format(id_token)}, verify=False
                )
                pods = json.loads(response.text)
                response = requests.get(
                    api_url + "/api/v1/nodes", headers={"Authorization": "Bearer {}".format(id_token)}, verify=False
                )

                nodes = json.loads(response.text)
            except Exception:
                continue

        node_status_dict = {}

        for node in nodes["items"]:

            node_name = "{}/{}".format(cluster_name, node["metadata"]["name"])

            node_status_dict[node_name] = []

            for condition in node["status"]["conditions"]:
                if condition["type"] == "Ready":
                    node_status_dict[node_name].append(condition["status"])

            if "unschedulable" in node["spec"]:
                node_status_dict[node_name].append(node["spec"]["unschedulable"])
            else:
                node_status_dict[node_name].append(False)

        for node in nodes["items"]:

            node_name = "{}/{}".format(cluster_name, node["metadata"]["name"])

            if "nvidia.com/gpu.product" in node["metadata"]["labels"]:
                gpu_name = node["metadata"]["labels"]["nvidia.com/gpu.product"]
            else:
                gpu_name = "N/A"

            if "nvidia.com/gpu.memory" in node["metadata"]["labels"]:
                gpu_size = str(round(int(node["metadata"]["labels"]["nvidia.com/gpu.memory"]) / 1024)) + " Gi"
            else:
                gpu_size = "N/A"

            if "nvidia.com/gpu" in node["status"]["allocatable"]:
                n_gpu_allocatable = int(node["status"]["allocatable"]["nvidia.com/gpu"])
            else:
                n_gpu_allocatable = 0
            n_cpu_allocatable = int(node["status"]["allocatable"]["cpu"])
            ram_allocatable = float(int(node["status"]["allocatable"]["memory"][:-2]) / (1024.0 * 1024.0))

            n_gpu_requested = 0
            n_cpus_requested = 0
            ram_requested = 0
            for pod in pods["items"]:
                if "nodeName" not in pod["spec"]:
                    continue
                if pod["spec"]["nodeName"] != node_name.split("/")[1]:
                    continue
                if pod["status"].get("phase") != "Running":
                    continue
                containers = pod["spec"]["containers"]
                for container in containers:
                    resources = container["resources"]

                    cpu = 0
                    ram = 0
                    if "requests" in resources:
                        req = resources["requests"]
                        if "nvidia.com/gpu" in req:

                            pod_name = pod["metadata"]["name"]
                            if pod_name.startswith("jupyter"):
                                pod_name = pod_name.replace("-2d", "-").replace("-40", "@").replace("-2e", ".")[len("jupyter-") :]
                            gpu_allocations[pod_name + ", " + pod["metadata"]["namespace"]] = {
                                "node": node_name.split("/")[1],
                                "cluster": cluster_name,
                                "namespace": pod["metadata"]["namespace"],
                                "gpu": req["nvidia.com/gpu"],
                                "gpu_name": gpu_name,
                                "gpu_size": gpu_size,
                                "expiration": pod["metadata"]["annotations"].get("terminate-at", "N/A"),
                            }
                            if "terminate-at" in pod["metadata"]["annotations"]:
                                expiry_time = datetime.strptime(
                                    pod["metadata"]["annotations"].get("terminate-at"), "%Y-%m-%dT%H:%M:%SZ"
                                )
                                if datetime.utcnow() > expiry_time:
                                    gpu_allocations[pod_name + ", " + pod["metadata"]["namespace"]]["is_expired"] = True

                            n_gpu_requested += int(req["nvidia.com/gpu"])
                        if "cpu" in req:
                            container_cpu = req["cpu"]
                            if container_cpu[-1] == "m":
                                container_cpu = container_cpu[:-1]
                                container_cpu = int(container_cpu) / 1000.0
                            else:
                                container_cpu = int(container_cpu)
                            if container_cpu > cpu:
                                cpu = container_cpu
                        if "memory" in req:
                            if req["memory"][-2:] == "Mi":
                                container_memory = int(req["memory"][:-2]) / 1024.0
                            elif req["memory"][-2:] == "Gi":
                                container_memory = int(req["memory"][:-2])

                            elif req["memory"][-1:] == "M":
                                container_memory = int(req["memory"][:-1]) / 1024.0
                            else:

                                container_memory = int(req["memory"]) / (1024 * 1024 * 1024)
                            if container_memory > ram:
                                ram = container_memory

                    # if 'limits' in resources:
                    #    lim = resources['limits']
                    #    if 'cpu' in lim:
                    #        container_cpu = lim['cpu']
                    #        if container_cpu[-1] == 'm':
                    #            container_cpu = container_cpu[:-1]
                    #            container_cpu = int(container_cpu)/1000.
                    #        else:
                    #            container_cpu = int(container_cpu)
                    #        if container_cpu > cpu:
                    #            cpu = container_cpu
                    #    if 'memory' in lim:
                    #        if lim['memory'][-2:] == "Mi":
                    #            container_memory = int(lim['memory'][:-2]) / 1024.
                    #        elif lim['memory'][-2:] == "Gi":
                    #            container_memory = int(lim['memory'][:-2])
                    #        if container_memory > ram:
                    #            ram = container_memory
                    n_cpus_requested += cpu
                    ram_requested += ram

            gpu_dict[node_name] = []

            if node_status_dict[node_name][0] != "True":
                gpu_dict[node_name].append("NA")
                gpu_dict[node_name].append("NA")
            elif node_status_dict[node_name][1]:
                gpu_dict[node_name].append("NA")
                gpu_dict[node_name].append("NA")
            else:
                gpu_dict[node_name].append(n_gpu_allocatable - n_gpu_requested)
                gpu_dict[node_name].append(n_gpu_allocatable)
            gpu_dict[node_name].append("{}, {}".format(gpu_name, gpu_size))

            cpu_dict[node_name] = []
            cpu_dict[node_name].append(n_cpu_allocatable - n_cpus_requested)
            cpu_dict[node_name].append(n_cpu_allocatable)
            cpu_dict[node_name].append((n_cpu_allocatable - n_cpus_requested) * 100 / n_cpu_allocatable)

            ram_dict[node_name] = []
            ram_dict[node_name].append(ram_allocatable - ram_requested)
            ram_dict[node_name].append(ram_allocatable)
            ram_dict[node_name].append((ram_allocatable - ram_requested) * 100 / ram_allocatable)
    return gpu_dict, cpu_dict, ram_dict, gpu_allocations


def get_filtered_available_nodes(gpu_dict, cpu_dict, ram_dict, gpu_request, cpu_request, memory_request):
    """
    Filters and returns nodes that meet the specified GPU, CPU, and memory requirements.

    Parameters
    ----------
    gpu_dict : dict
        A dictionary where keys are node names and values are lists containing GPU information.
    cpu_dict : dict
        A dictionary where keys are node names and values are lists containing CPU information.
    ram_dict : dict
        A dictionary where keys are node names and values are lists containing RAM information.
    gpu_request : int
        The minimum number of GPUs required.
    cpu_request : float
        The minimum amount of CPU required.
    memory_request : float
        The minimum amount of memory required.

    Returns
    -------
    tuple
        Three dictionaries containing the filtered nodes and their respective GPU, CPU, and RAM information.
    """

    filtered_nodes = []
    for node in gpu_dict:
        if (
            int(gpu_dict[node][0]) >= gpu_request
            and float(cpu_dict[node][0]) >= cpu_request
            and float(ram_dict[node][0]) >= memory_request
        ):
            filtered_nodes.append(node)

    return (
        {node: gpu_dict[node] for node in filtered_nodes},
        {node: cpu_dict[node] for node in filtered_nodes},
        {node: ram_dict[node] for node in filtered_nodes},
    )


def generate_kubeconfig(id_token, user_id, namespace, cluster_id, settings):
    """
    Generates a Kubernetes configuration dictionary for a given user and cluster.

    Parameters
    ----------
    id_token : str
        The ID token for the user.
    user_id : str
        The user ID.
    namespace : str
        The Kubernetes namespace.
    cluster_id : str
        The cluster ID.
    settings : object
        An object containing various settings, including:
        - CLUSTER_NAMES (dict): A dictionary mapping cluster names to their IDs.
        - PRIVATE_CLUSTERS (dict): A dictionary of private clusters with their tokens.
        - OIDC_ISSUER_URL (str): The OIDC issuer URL.
        - OIDC_RP_CLIENT_ID (str): The OIDC client ID.
        - OIDC_RP_CLIENT_SECRET (str): The OIDC client secret.

    Returns
    -------
    dict
        A dictionary representing the Kubernetes configuration.
    """
    cluster_apis = {k: v for v, k in settings.CLUSTER_NAMES.items()}

    if cluster_apis[cluster_id] in settings.PRIVATE_CLUSTERS:
        kube_config = {
            "apiVersion": "v1",
            "kind": "Config",
            "preferences": {},
            "current-context": "MAIA/{}".format(user_id),
            "contexts": [
                {"name": "MAIA/{}".format(user_id), "context": {"user": user_id, "cluster": "MAIA", "namespace": namespace}}
            ],
            "clusters": [
                {
                    "name": "MAIA",
                    "cluster": {
                        "certificate-authority-data": "",  # settings.CLUSTER_CA,
                        "server": cluster_apis[cluster_id],
                        "insecure-skip-tls-verify": True,
                    },
                }
            ],
            "users": [{"name": user_id, "user": {"token": settings.PRIVATE_CLUSTERS[cluster_apis[cluster_id]]}}],
        }

    else:

        kube_config = {
            "apiVersion": "v1",
            "kind": "Config",
            "preferences": {},
            "current-context": "MAIA/{}".format(user_id),
            "contexts": [
                {"name": "MAIA/{}".format(user_id), "context": {"user": user_id, "cluster": "MAIA", "namespace": namespace}}
            ],
            "clusters": [
                {
                    "name": "MAIA",
                    "cluster": {
                        "certificate-authority-data": "",  # settings.CLUSTER_CA,
                        "server": cluster_apis[cluster_id],
                        "insecure-skip-tls-verify": True,
                    },
                }
            ],
            "users": [
                {
                    "name": user_id,
                    "user": {
                        "auth-provider": {
                            "config": {
                                "idp-issuer-url": settings.OIDC_ISSUER_URL,
                                "client-id": settings.OIDC_RP_CLIENT_ID,
                                "id-token": id_token,
                                "client-secret": settings.OIDC_RP_CLIENT_SECRET,
                            },
                            "name": "oidc",
                        }
                    },
                }
            ],
        }

    return kube_config


def get_namespace_details(settings, id_token, namespace, user_id, is_admin=False):
    """
    Retrieve details about the namespace including workspace applications, remote desktops, SSH ports, MONAI models,
    Orthanc instances and deployed clusters.

    Parameters
    ----------
    settings : object
        Configuration settings containing API URLs and private cluster tokens.
    id_token : str
        Identity token for authentication.
    namespace : str
        The namespace to retrieve details for.
    user_id : str
        The user ID to filter resources.
    is_admin : bool, optional
        Flag indicating if the user has admin privileges. Defaults to False.

    Returns
    -------
    tuple
        A tuple containing:
        - maia_workspace_apps (dict): Dictionary of workspace applications with their URLs.
        - remote_desktop_dict (dict): Dictionary of remote desktop URLs for users.
        - ssh_ports (dict): Dictionary of SSH ports for users.
        - monai_models (dict): Dictionary of MONAI models.
        - orthanc_list (dict): Dictionary of Orthanc instances.
        - deployed_clusters (list): List of clusters where the namespace is deployed.
    """
    maia_workspace_apps = {}
    remote_desktop_dict = {}
    orthanc_list = []
    monai_models = {}
    ssh_ports = {}
    deployed_clusters = []
    nvflare_dashboards = []

    for api_url in settings.API_URL:
        if api_url in settings.PRIVATE_CLUSTERS:
            token = settings.PRIVATE_CLUSTERS[api_url]
            response = requests.get(
                api_url + "/apis/networking.k8s.io/v1/namespaces/{}/ingresses".format(namespace),
                headers={"Authorization": "Bearer {}".format(token)},
                verify=False,
            )
        else:
            response = requests.get(
                api_url + "/apis/networking.k8s.io/v1/namespaces/{}/ingresses".format(namespace),
                headers={"Authorization": "Bearer {}".format(id_token)},
                verify=False,
            )
        ingresses = json.loads(response.text)

        if api_url in settings.PRIVATE_CLUSTERS:
            token = settings.PRIVATE_CLUSTERS[api_url]
            try:
                response = requests.get(
                    api_url + "/api/v1/namespaces/{}/services".format(namespace),
                    headers={"Authorization": "Bearer {}".format(token)},
                    verify=False,
                )
            except Exception:
                continue
        else:
            try:
                response = requests.get(
                    api_url + "/api/v1/namespaces/{}/services".format(namespace),
                    headers={"Authorization": "Bearer {}".format(id_token)},
                    verify=False,
                )
            except Exception:
                continue
        services = json.loads(response.text)

        if "code" in services:
            if services["code"] == 403:
                ...

        if "items" in ingresses:
            if "items" in services:
                if len(ingresses["items"]) > 0 or len(services["items"]) > 0:
                    deployed_clusters.append(settings.CLUSTER_NAMES[api_url])

                for ingress in ingresses["items"]:
                    for rule in ingress["spec"]["rules"]:
                        if "host" not in rule:
                            rule["host"] = settings.DEFAULT_INGRESS_HOST
                        for path in rule["http"]["paths"]:
                            if path["backend"]["service"]["name"].endswith("-maia-monailabel"):
                                monai_models[path["backend"]["service"]["name"][: -len("-maia-monailabel")]] = {
                                    "monai_label": "https://" + rule["host"] + path["path"]
                                }
                            if path["backend"]["service"]["name"] == "proxy-public":
                                maia_workspace_apps["hub"] = "https://" + rule["host"] + path["path"]
                            if path["backend"]["service"]["name"] == namespace + "-orthanc-svc":

                                maia_workspace_apps["orthanc"] = "https://" + rule["host"] + path["path"]
                                maia_workspace_apps["ohif"] = "https://" + rule["host"] + path["path"] + "/ohif/"

                            if "port" in path["backend"]["service"] and "name" in path["backend"]["service"]["port"]:
                                if path["backend"]["service"]["port"]["name"] == "orthanc":
                                    orthanc_list.append(
                                        {
                                            "name": ingress["metadata"]["name"],
                                            "dicom_port": "",
                                            "url": "https://" + rule["host"] + path["path"] + "/dicom-web/",
                                        }
                                    )
                            if (
                                "labels" in ingress["metadata"]
                                and "app.kubernetes.io/name" in ingress["metadata"]["labels"]
                                and ingress["metadata"]["labels"]["app.kubernetes.io/name"] == "maia-nvflare-dashboard"
                            ):
                                nvflare_dashboards.append(
                                    {
                                        "name": ingress["metadata"]["name"][: -len("-maia-nvflare-dashboard")],
                                        "url": "https://" + rule["host"] + path["path"],
                                    }
                                )
                            if path["backend"]["service"]["name"] == namespace + "-mlflow-mkg" and path["path"].endswith(
                                "mlflow"
                            ):
                                maia_workspace_apps["mlflow"] = "https://" + rule["host"] + path["path"]
                            if path["backend"]["service"]["name"] == namespace + "-mlflow-mkg" and path["path"].endswith(
                                "minio-console"
                            ):
                                maia_workspace_apps["minio_console"] = "https://" + rule["host"] + path["path"]

                for service in services["items"]:
                    for port in service["spec"]["ports"]:
                        if "name" in port and port["name"] == "remote-desktop-port":
                            if "hub" in maia_workspace_apps:
                                hub_url = maia_workspace_apps["hub"]
                                user = (
                                    service["metadata"]["name"][len("jupyter-") :]
                                    .replace("-2d", "-")
                                    .replace("-40", "@")
                                    .replace("-2e", ".")
                                )
                                url = f"{hub_url}/user/{user}/proxy/80/desktop/{user}/"
                                if user_id == user or is_admin:
                                    remote_desktop_dict[user] = url
                            else:
                                hub_url = "KUBEFLOW"
                                user = (
                                    service["metadata"]["name"][len("jupyter-") :]
                                    .replace("-2d", "-")
                                    .replace("-40", "@")
                                    .replace("-2e", ".")
                                )
                                try:
                                    app_name = service["spec"]["selector"]["app"]
                                except Exception:
                                    app_name = service["metadata"]["name"][len("jupyter-") :]
                                url = f"{hub_url}/notebook/{namespace}/{app_name}/proxy/80/desktop/{user}/"
                                if user_id == user or is_admin:
                                    remote_desktop_dict[user] = url

                        if "name" in port and port["name"] == "ssh":
                            # Backward compatibility
                            if service["metadata"]["name"].endswith("-ssh"):
                                user = (
                                    service["metadata"]["name"][len("jupyter-") : -len("-ssh")]
                                    .replace("-2d", "-")
                                    .replace("-40", "@")
                                    .replace("-2e", ".")
                                )
                                if user_id == user or is_admin:
                                    ssh_ports[user] = port["port"]
                            else:
                                user = (
                                    service["metadata"]["name"][len("jupyter-") :]
                                    .replace("-2d", "-")
                                    .replace("-40", "@")
                                    .replace("-2e", ".")
                                )
                                if user_id == user or is_admin:
                                    ssh_ports[user] = port["port"]

                        if "name" in port and port["name"] == "orthanc-dicom":
                            for orthanc in orthanc_list:
                                if orthanc["name"] == service["metadata"]["labels"]["app"] + "-orthanc":
                                    if service["spec"]["type"] == "NodePort":
                                        orthanc["dicom_port"] = port["nodePort"]
                                    elif service["spec"]["type"] == "LoadBalancer":
                                        orthanc["dicom_port"] = port["port"]
        if settings.CLUSTER_NAMES[api_url] not in deployed_clusters:
            continue
        if hasattr(settings, "GLOBAL_NAMESPACES") and settings.GLOBAL_NAMESPACES is not None:
            for global_namespace in settings.GLOBAL_NAMESPACES:
                if api_url in settings.PRIVATE_CLUSTERS:
                    token = settings.PRIVATE_CLUSTERS[api_url]
                    response = requests.get(
                        api_url + "/apis/networking.k8s.io/v1/namespaces/{}/ingresses".format(global_namespace),
                        headers={"Authorization": "Bearer {}".format(token)},
                        verify=False,
                    )
                else:
                    response = requests.get(
                        api_url + "/apis/networking.k8s.io/v1/namespaces/{}/ingresses".format(global_namespace),
                        headers={"Authorization": "Bearer {}".format(id_token)},
                        verify=False,
                    )
                ingresses = json.loads(response.text)

                if api_url in settings.PRIVATE_CLUSTERS:
                    token = settings.PRIVATE_CLUSTERS[api_url]
                    try:
                        response = requests.get(
                            api_url + "/api/v1/namespaces/{}/services".format(global_namespace),
                            headers={"Authorization": "Bearer {}".format(token)},
                            verify=False,
                        )
                    except Exception:
                        continue
                else:
                    try:
                        response = requests.get(
                            api_url + "/api/v1/namespaces/{}/services".format(global_namespace),
                            headers={"Authorization": "Bearer {}".format(id_token)},
                            verify=False,
                        )
                    except Exception:
                        continue
                services = json.loads(response.text)

                if "items" in ingresses:
                    if "items" in services:
                        for ingress in ingresses["items"]:
                            for rule in ingress["spec"]["rules"]:
                                if "host" not in rule:
                                    rule["host"] = settings.DEFAULT_INGRESS_HOST
                                for path in rule["http"]["paths"]:
                                    if path["backend"]["service"]["name"] == "maia-xnat":
                                        maia_workspace_apps["xnat"] = "https://" + rule["host"] + path["path"]
                                    if path["backend"]["service"]["name"] == "istio-ingressgateway":
                                        maia_workspace_apps["kubeflow"] = "https://" + rule["host"] + path["path"]

    if "hub" not in maia_workspace_apps:
        maia_workspace_apps["hub"] = "N/A"
    if "orthanc" not in maia_workspace_apps:
        maia_workspace_apps["orthanc"] = "N/A"
    if "ohif" not in maia_workspace_apps:
        maia_workspace_apps["ohif"] = "N/A"
    if "label_studio" not in maia_workspace_apps:
        maia_workspace_apps["label_studio"] = "N/A"
    if "kubeflow" not in maia_workspace_apps:
        maia_workspace_apps["kubeflow"] = "N/A"
    else:
        for remote_desktop in remote_desktop_dict:
            if remote_desktop_dict[remote_desktop].startswith("KUBEFLOW"):
                remote_desktop_dict[remote_desktop] = (
                    maia_workspace_apps["kubeflow"] + remote_desktop_dict[remote_desktop][len("KUBEFLOW") :]
                )
    if "mlflow" not in maia_workspace_apps:
        maia_workspace_apps["mlflow"] = "N/A"
    if "minio_console" not in maia_workspace_apps:
        maia_workspace_apps["minio_console"] = "N/A"
    if "xnat" not in maia_workspace_apps:
        maia_workspace_apps["xnat"] = "N/A"

    return maia_workspace_apps, remote_desktop_dict, ssh_ports, monai_models, orthanc_list, deployed_clusters, nvflare_dashboards


def create_namespace_from_context(namespace_id):
    """
    Create a Kubernetes namespace using the provided namespace ID.

    Parameters
    ----------
    namespace_id : str
        The ID of the namespace to be created.

    Returns
    -------
    None
        This function does not return any value. It prints the API response or an exception message.

    Raises
    ------
    ApiException
        If there is an error when calling the Kubernetes CoreV1Api to create the namespace.
    """
    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)
        body = kubernetes.client.V1Namespace(metadata=kubernetes.client.V1ObjectMeta(name=namespace_id))
        try:
            _ = api_instance.create_namespace(body)
            # print(api_response)
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespace: \n")
            print(e)


def create_namespace(request, settings, namespace_id, cluster_id):
    """
    Creates a Kubernetes namespace using the provided request, settings, namespace ID, and cluster ID.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object containing session and user information.
    settings : Settings
        The settings object containing configuration details.
    namespace_id : str
        The ID of the namespace to be created.
    cluster_id : str
        The ID of the Kubernetes cluster where the namespace will be created.

    Returns
    -------
    None

    Raises
    ------
    ApiException
        If an error occurs while creating the namespace using the Kubernetes API.
    """
    id_token = request.session.get("oidc_id_token")
    kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", cluster_id, settings=settings)
    config.load_kube_config_from_dict(kubeconfig_dict)
    with open(Path("/tmp").joinpath("kubeconfig-ns"), "w") as f:
        yaml.dump(kubeconfig_dict, f)
        os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-ns"))

        create_namespace_from_context(namespace_id)


def create_cifs_secret_from_context(namespace, user_id, username, password, public_key):
    """
    Create a CIFS secret in the specified Kubernetes namespace.

    Parameters
    ----------
    namespace : str
        The Kubernetes namespace where the secret will be created.
    user_id : str
        The user ID to be used in the secret name.
    username : str
        The CIFS username to be encrypted and stored in the secret.
    password : str
        The CIFS password to be encrypted and stored in the secret.
    public_key : str
        The public key used to encrypt the username and password.

    Returns
    -------
    None

    Raises
    ------
    ApiException
        If there is an error when calling the Kubernetes API to create the secret.
    """
    from MAIA.dashboard_utils import encrypt_string

    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)
        secret = kubernetes.client.V1Secret()
        secret.metadata = kubernetes.client.V1ObjectMeta(name=f"{user_id}-cifs", namespace=namespace)

        encrypted_username = encrypt_string(public_key, username)
        encrypted_password = encrypt_string(public_key, password)

        secret.type = "fstab/cifs"
        secret.data = {
            "username": base64.b64encode(encrypted_username.encode()).decode(),
            "password": base64.b64encode(encrypted_password.encode()).decode(),
        }
        try:
            # Check if the secret already exists
            existing_secret = api_instance.read_namespaced_secret(secret.metadata.name, namespace)
            # If it exists, delete it
            if existing_secret is not None:
                print(f"Deleting existing secret: {secret.metadata.name}")
                api_instance.delete_namespaced_secret(secret.metadata.name, namespace)
        except kubernetes.client.exceptions.ApiException as e:
            print(f"Exception checking/deleting existing secret: {e}")
            if e.status != 404:
                raise
        api_instance.create_namespaced_secret(namespace, secret)


def create_cifs_secret(request, cluster_id, settings, namespace, user_id, username, password, public_key):
    """
    Create a CIFS secret in the specified Kubernetes namespace.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object containing session and user information.
    cluster_id : str
        The ID of the Kubernetes cluster.
    settings : dict
        The settings dictionary containing configuration details.
    namespace : str
        The Kubernetes namespace where the secret will be created.
    user_id : str
        The user ID for the CIFS secret.
    username : str
        The username for the CIFS secret.
    password : str
        The password for the CIFS secret.
    public_key : str
        The public key for the CIFS secret.

    Returns
    -------
    None
    """
    id_token = request.session.get("oidc_id_token")
    kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", cluster_id, settings=settings)
    config.load_kube_config_from_dict(kubeconfig_dict)
    with open(Path("/tmp").joinpath("kubeconfig-ns"), "w") as f:
        yaml.dump(kubeconfig_dict, f)
        os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-ns"))

        create_cifs_secret_from_context(namespace, user_id, username, password, public_key)


def create_helm_repo_secret_from_context(repo_name, helm_repo_config, argocd_namespace="argocd"):
    """
    Create a Helm repository secret in the specified Argo CD namespace using the provided Helm repository configuration.

    Parameters
    ----------
    repo_name : str
        The name of the Helm repository.
    helm_repo_config : dict
        A dictionary containing the Helm repository configuration with the following keys:
        - "username" (str): The username for the Helm repository.
        - "password" (str): The password for the Helm repository.
        - "project" (str): The project associated with the Helm repository.
        - "url" (str): The URL of the Helm repository.
        - "type" (str): The type of the Helm repository.
        - "name" (str): The name of the Helm repository.
        - "enableOCI" (str): A flag indicating whether OCI is enabled for the Helm repository.
    argocd_namespace : str, optional
        The namespace in which to create the secret (default is "argocd").

    Returns
    -------
    None

    Raises
    ------
    ApiException
        If there is an error when calling the Kubernetes API to create the secret.
    """

    username = helm_repo_config["username"]
    password = helm_repo_config["password"]
    if "project" not in helm_repo_config:
        project = None
    else:
        project = helm_repo_config["project"]
    url = helm_repo_config["url"]
    type = helm_repo_config["type"]
    name = helm_repo_config["name"]
    enable_oci = helm_repo_config["enableOCI"]

    kubeconfig = os.environ.get("DEPLOY_KUBECONFIG", None)
    if kubeconfig is None:
        kubeconfig = os.environ.get("KUBECONFIG", None)
    config.load_kube_config(config_file=kubeconfig)
    # If secret already exists, delete it before creating a new one
    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)
        try:
            api_instance.delete_namespaced_secret(name=f"repo-{repo_name}", namespace=argocd_namespace)
        except kubernetes.client.exceptions.ApiException as e:
            # If the error is 404 (Not Found), we can ignore it;
            # otherwise, raise the exception
            if e.status != 404:
                raise
    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)
        secret = kubernetes.client.V1Secret()
        secret.metadata = kubernetes.client.V1ObjectMeta(
            name=f"repo-{repo_name}", labels={"argocd.argoproj.io/secret-type": "repository"}, namespace=argocd_namespace
        )
        if project is not None:
            secret.data = {
                "username": base64.b64encode(username.encode()).decode(),
                "password": base64.b64encode(password.encode()).decode(),
                "project": base64.b64encode(project.encode()).decode(),
                "url": base64.b64encode(url.encode()).decode(),
                "type": base64.b64encode(type.encode()).decode(),
                "name": base64.b64encode(name.encode()).decode(),
                "enableOCI": base64.b64encode(enable_oci.encode()).decode(),
            }
        else:
            secret.data = {
                "username": base64.b64encode(username.encode()).decode(),
                "password": base64.b64encode(password.encode()).decode(),
                "url": base64.b64encode(url.encode()).decode(),
                "type": base64.b64encode(type.encode()).decode(),
                "name": base64.b64encode(name.encode()).decode(),
                "enableOCI": base64.b64encode(enable_oci.encode()).decode(),
            }

        try:
            api_response = api_instance.create_namespaced_secret(argocd_namespace, secret)
            print(api_response)
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespaced_secret: %s\n" % e)


def create_docker_registry_secret_from_context(docker_credentials, namespace, secret_name):
    """
    Creates a Kubernetes secret of type `kubernetes.io/dockerconfigjson` in the specified namespace
    using the provided Docker registry credentials.

    Parameters
    ----------
    docker_credentials : dict
    A dictionary containing Docker registry credentials with the following keys:
    - "registry" : str
        The Docker registry URL (e.g., "https://index.docker.io/v1/").
    - "username" : str
        The username for the Docker registry.
    - "password" : str
        The password for the Docker registry.
    namespace : str
        The Kubernetes namespace where the secret will be created.
    secret_name : str
        The name of the Kubernetes secret to be created.

    Raises
    ------
    ApiException
        If there is an error while creating the Kubernetes secret, an exception is raised
        with details about the failure.

    Notes
    -----
    This function uses the Kubernetes Python client to create the secret. Ensure that the
    Kubernetes client is properly configured to interact with the desired cluster.

    """

    docker_credentials_dict = {
        "auths": {
            docker_credentials["registry"]: {
                "username": docker_credentials["username"],
                "password": docker_credentials["password"],
                "auth": base64.b64encode(f"{docker_credentials['username']}:{docker_credentials['password']}".encode()).decode(),
            }
        }
    }
    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)
        secret = kubernetes.client.V1Secret()
        secret.metadata = kubernetes.client.V1ObjectMeta(name=secret_name, namespace=namespace)
        secret.data = {
            ".dockerconfigjson": base64.b64encode(json.dumps(docker_credentials_dict).encode()).decode(),
            "config.json": base64.b64encode(
                json.dumps(docker_credentials_dict).encode()
            ).decode(),  # Needed for KubeFlow to mount the secret with Kaniko
        }
        secret.type = "kubernetes.io/dockerconfigjson"

        try:
            api_response = api_instance.create_namespaced_secret(namespace, secret)
            print(api_response)
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespaced_secret: %s\n" % e)


def retrieve_json_key_for_maia_registry_authentication_from_context(namespace, secret_name, registry_url):
    """
    Retrieve the JSON key for MAIA registry authentication from a Kubernetes secret.
    This function reads a Kubernetes secret in the specified namespace, decodes the `.dockerconfigjson`
    field, and extracts the password for the given registry URL.

    Parameters
    ----------
    namespace : str
        The namespace in which the Kubernetes secret is located.
    secret_name : str
        The name of the Kubernetes secret containing the `.dockerconfigjson`.
    registry_url : str
        The URL of the container registry for which the authentication key is required.

    Returns
    -------
    str
        The password associated with the specified registry URL in the `.dockerconfigjson`.
        Returns an empty dictionary if an exception occurs.

    Raises
    ------
    kubernetes.client.exceptions.ApiException
        If there is an error while reading the Kubernetes secret.
    """
    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)

        try:
            secret = api_instance.read_namespaced_secret(name=secret_name, namespace=namespace)

            # Decode the .dockerconfigjson
            dockerconfig = base64.b64decode(secret.data[".dockerconfigjson"]).decode()
            dockerconfig_json = json.loads(dockerconfig)
            return dockerconfig_json["auths"][registry_url]["password"]
        except ApiException as e:
            print("Exception when calling CoreV1Api->read_namespaced_secret: %s\n" % e)
            return {}


def retrieve_json_key_for_maia_registry_authentication(request, cluster_id, settings, namespace, secret_name, registry_url):
    """
    Retrieves the JSON key for MAIA registry authentication.

    This function generates a kubeconfig dictionary using the provided
    OpenID Connect (OIDC) ID token and user information, writes it to a
    temporary kubeconfig file, and sets the `KUBECONFIG` environment
    variable. It then delegates the retrieval of the JSON key to another
    function.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object containing the session and user information.
    cluster_id : str
        The ID of the Kubernetes cluster.
    settings : dict
        The settings dictionary containing configuration details.
    namespace : str
        The Kubernetes namespace where the secret is located.
    secret_name : str
        The name of the Kubernetes secret containing the registry credentials.
    registry_url : str
        The URL of the container registry.

    Returns
    -------
    dict
        A dictionary containing the JSON key for MAIA registry authentication.

    Raises
    ------
    KeyError
        If the `oidc_id_token` is not found in the session.
    FileNotFoundError
        If there is an issue writing the kubeconfig file to the temporary directory.
    """
    id_token = request.session.get("oidc_id_token")
    kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", cluster_id, settings=settings)
    config.load_kube_config_from_dict(kubeconfig_dict)
    with open(Path("/tmp").joinpath("kubeconfig-ns"), "w") as f:
        yaml.dump(kubeconfig_dict, f)
        os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-ns"))

        return retrieve_json_key_for_maia_registry_authentication_from_context(namespace, secret_name, registry_url)
