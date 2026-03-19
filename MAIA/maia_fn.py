from __future__ import annotations

import base64
import json
import os
import random
import string
from pathlib import Path
from secrets import token_urlsafe
from typing import Dict, List

import kubernetes
import nltk
import toml
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from loguru import logger
from nltk.corpus import words
from omegaconf import OmegaConf

from MAIA.helm_values import read_config_dict_and_generate_helm_values_dict

from MAIA.versions import define_docker_image_versions, define_maia_docker_versions, define_maia_project_versions
from MAIA_scripts.MAIA_create_JupyterHub_config import create_jupyterhub_config_api

mysql_image = define_docker_image_versions()["mysql_image"]
mysql_image_version = define_docker_image_versions()["mysql"]
mkg_chart_version = define_maia_docker_versions()["mkg_chart_version"]
mkg_chart_type = define_maia_docker_versions()["mkg_chart_type"]
maia_mlflow_image_version = define_docker_image_versions()["maia-mlflow"]
maia_orthanc_image_version = define_docker_image_versions()["maia-orthanc"]
maia_orthanc_image = define_docker_image_versions()["maia-orthanc-image"]
maia_orthanc_chart_version = define_maia_project_versions()["maia-orthanc-chart_version"]
maia_orthanc_chart_type = define_maia_project_versions()["maia-orthanc-chart_type"]
maia_namespace_chart_version = define_maia_project_versions()["maia_namespace_chart_version"]
maia_namespace_chart_type = define_maia_project_versions()["maia_namespace_chart_type"]
maia_filebrowser_image_version = define_docker_image_versions()["maia-filebrowser"]
maia_filebrowser_chart_version = define_maia_project_versions()["maia_filebrowser_chart_version"]
maia_filebrowser_chart_type = define_maia_project_versions()["maia_filebrowser_chart_type"]
maia_kubeflow_chart_version = define_maia_project_versions()["maia-kubeflow-chart_version"]
maia_kubeflow_chart_type = define_maia_project_versions()["maia-kubeflow-chart_type"]
maia_nvflare_dashboard_chart_version = define_maia_project_versions()["maia-nvflare-dashboard-chart_version"]
maia_nvflare_dashboard_chart_type = define_maia_project_versions()["maia-nvflare-dashboard-chart_type"]
maia_nvflare_dashboard_image_version = define_docker_image_versions()["maia-nvflare-dashboard"]


def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for i in range(length))


def generate_human_memorable_password(length=12):
    nltk.download("words")
    word_list = words.words()
    password = "-".join(random.choice(word_list) for _ in range(length // 6))
    password += "".join(random.choice(string.ascii_letters + string.digits) for _ in range(length - len(password)))
    return password


def copy_certificate_authority_secret(
    namespace,
    source_secret_name="kubernetes-ca",
    target_secret_name="kubernetes-ca",
    source_namespace="cert-manager",
    opaque=False,
    cert_name="tls.crt",
    key_name="tls.key",
):
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)
    api = client.CoreV1Api()
    try:
        secret = api.read_namespaced_secret(name=source_secret_name, namespace=source_namespace)
    except ApiException as e:
        logger.error(f"Exception when calling CoreV1Api->read_namespaced_secret: {e}")
        return None
    try:
        api.create_namespaced_secret(
            namespace=namespace,
            body={
                "metadata": {"name": target_secret_name},
                "data": {cert_name: secret.data["tls.crt"], key_name: secret.data["tls.key"]},
                "type": "Opaque" if opaque else "kubernetes.io/tls",
            },
        )
    except ApiException as e:
        if e.status == 409:
            logger.debug(f"Secret {target_secret_name} already exists in namespace {namespace}, skipping creation.")
            return None
        else:
            logger.error(f"Exception when calling CoreV1Api->create_namespaced_secret: {e}")
            return None
    return secret


def create_config_map_from_data(
    data: str | List[str], config_map_name: str, namespace: str, kubeconfig_dict: Dict, data_key: str | List[str] = "values.yaml"
):
    """
    Create a ConfigMap on a Kubernetes Cluster.

    Parameters
    ----------
    data : str
        String containing the content of the ConfigMap to dump.
    config_map_name : str
        ConfigMap name.
    namespace : str
        Namespace where to create the ConfigMap.
    data_key : str, optional
        Value to use as the filename for the content in the ConfigMap.
    kubeconfig_dict : dict
        Kube Configuration dictionary for Kubernetes cluster authentication.
    """
    config.load_kube_config_from_dict(kubeconfig_dict)
    metadata = kubernetes.client.V1ObjectMeta(name=config_map_name, namespace=namespace)

    if isinstance(data_key, list) and isinstance(data, list):
        configmap = kubernetes.client.V1ConfigMap(
            api_version="v1", kind="ConfigMap", data={data_key[i]: data[i] for i in range(len(data))}, metadata=metadata
        )
    else:
        configmap = kubernetes.client.V1ConfigMap(api_version="v1", kind="ConfigMap", data={data_key: data}, metadata=metadata)

    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)

        pretty = "true"
        try:
            api_response = api_instance.create_namespaced_config_map(namespace, configmap, pretty=pretty)
            logger.debug(f"ConfigMap created: {api_response}")
        except ApiException as e:
            logger.error(f"Exception when calling CoreV1Api->delete_namespaced_config_map: {e}")


def get_ssh_port_dict(port_type, namespace, port_range, maia_metallb_ip=None):
    """
    Retrieve a dictionary of used SSH ports for services in a Kubernetes cluster.

    Parameters
    ----------
    port_type : str
        The type of port to check ('LoadBalancer' or 'NodePort').
    namespace : str
        The namespace to filter services by.
    port_range : tuple
        A tuple specifying the range of ports to check (start, end).
    maia_metallb_ip : str, optional
        The IP address of the MetalLB load balancer (default is None).

    Returns
    -------
    list of dict
        A list of dictionaries with service names as keys and their corresponding used SSH ports as values.
        Returns None if an exception occurs.
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()

    try:
        used_port = []
        services = v1.list_service_for_all_namespaces(watch=False)
        for svc in services.items:
            if port_type == "LoadBalancer":
                if svc.status.load_balancer.ingress is not None:
                    if svc.spec.type == "LoadBalancer" and svc.status.load_balancer.ingress[0].ip == maia_metallb_ip:
                        for port in svc.spec.ports:
                            if (port.name == "ssh" and svc.metadata.namespace == namespace) or (
                                port.name == "orthanc-dicom" and svc.metadata.namespace == namespace
                            ):
                                if svc.metadata.name.endswith("-ssh"):
                                    used_port.append({svc.metadata.name[: -len("-ssh")]: int(port.port)})
                                else:
                                    used_port.append({svc.metadata.name: int(port.port)})
            elif port_type == "NodePort":
                if svc.spec.type == "NodePort" and svc.metadata.namespace == namespace:
                    for port in svc.spec.ports:
                        if port.node_port >= port_range[0] and port.node_port <= port_range[1]:
                            if svc.metadata.name.endswith("-ssh"):
                                used_port.append({svc.metadata.name[: -len("-ssh")]: int(port.node_port)})
                            else:
                                used_port.append({svc.metadata.name: int(port.node_port)})
                if svc.spec.type == "LoadBalancer" and svc.metadata.namespace == namespace:
                    for port in svc.spec.ports:
                        if port.node_port is None:
                            continue
                        if port.node_port >= port_range[0] and port.node_port <= port_range[1]:
                            if svc.metadata.name.endswith("-ssh"):
                                used_port.append({svc.metadata.name[: -len("-ssh")]: int(port.node_port)})
                            else:
                                used_port.append({svc.metadata.name: int(port.node_port)})

        logger.debug(f"Used ports: {used_port}")
        return used_port
    except ApiException:
        logger.error("Exception when calling CoreV1Api->list_service_for_all_namespaces")
        return None


def get_ssh_ports(n_requested_ports, port_type, ip_range, maia_metallb_ip=None):
    """
    Retrieve a list of available SSH ports based on the specified criteria.

    Parameters
    ----------
    n_requested_ports : int
        The number of SSH ports requested.
    port_type : str
        The type of port to search for ('LoadBalancer' or 'NodePort').
    ip_range : tuple
        A tuple specifying the range of IPs to search within (start, end).
    maia_metallb_ip : str, optional
        The specific IP address to match for 'LoadBalancer' type. Defaults to None.

    Returns
    -------
    list
        A list of available SSH ports that meet the specified criteria.
    None
        If an error occurs during the process.
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()

    try:
        used_port = []
        services = v1.list_service_for_all_namespaces(watch=False)
        for svc in services.items:
            if port_type == "LoadBalancer":
                if svc.status.load_balancer.ingress is not None:
                    if svc.spec.type == "LoadBalancer" and svc.status.load_balancer.ingress[0].ip == maia_metallb_ip:
                        for port in svc.spec.ports:
                            if port.name == "ssh" or port.name == "orthanc-dicom":
                                used_port.append(int(port.port))
            elif port_type == "NodePort":
                if svc.spec.type == "NodePort":
                    for port in svc.spec.ports:
                        used_port.append(int(port.node_port))
                if svc.spec.type == "LoadBalancer":
                    for port in svc.spec.ports:
                        if port.node_port is None:
                            continue
                        used_port.append(int(port.node_port))
        logger.debug(f"Used ports: {used_port}")
        ports = []

        for _ in range(n_requested_ports):
            for port in range(ip_range[0], ip_range[1]):
                if port not in used_port:
                    ports.append(port)
                    used_port.append(port)
                    break

        return ports
    except ApiException:
        logger.error("Exception when calling CoreV1Api->list_service_for_all_namespaces")
        return None


def convert_username_to_jupyterhub_username(username):
    """
    Convert a username to a JupyterHub-compatible username.

    Parameters
    ----------
    username : str
        The original username.

    Returns
    -------
    str
        The JupyterHub-compatible username.
    """
    return username.replace("-", "-2d").replace("@", "-40").replace(".", "-2e")


def encode_docker_registry_secret(registry_server, registry_username, registry_password):
    """
    Encode Docker registry credentials into a base64-encoded string.

    Parameters
    ----------
    registry_server : str
        The Docker registry server.
    registry_username : str
        The Docker registry username.
    registry_password : str
        The Docker registry password.

    Returns
    -------
    str
        The base64-encoded Docker registry credentials.
    """
    auth = base64.b64encode(f"{registry_username}:{registry_password}".encode("utf-8")).decode("utf-8")
    return base64.b64encode(
        json.dumps(
            {"auths": {registry_server: {"username": registry_username, "password": registry_password, "auth": auth}}}
        ).encode("utf-8")
    ).decode("utf-8")


def deploy_oauth2_proxy(cluster_config, user_config, config_folder=None):
    """
    Deploy an OAuth2 Proxy using the provided cluster and user configurations.

    Parameters
    ----------
    cluster_config : dict
        Configuration dictionary for the cluster. Expected keys include:
            - "keycloak": A dictionary with "issuer_url", "client_id", and "client_secret".
            - "domain": The domain name for the cluster.
            - "url_type": The type of URL, either "subpath" or other.
            - "storage_class": The storage class for Redis.
            - "nginx_cluster_issuer" (optional): The cluster issuer for NGINX.
            - "traefik_resolver" (optional): The resolver for Traefik.
    user_config : dict
        Configuration dictionary for the user. Expected keys include:
            - "group_ID": The group ID for the user.
            - "group_subdomain": The subdomain for the user's group.
    config_folder : str, optional
        The folder path where the configuration files will be saved. Defaults to None.

    Returns
    -------
    dict
        A dictionary containing deployment details:
            - "namespace": The namespace for the deployment.
            - "release": The release name for the deployment.
            - "chart": The chart name for the deployment.
            - "repo": The repository URL for the chart.
            - "version": The chart version.
            - "values": The path to the generated values YAML file.
    """
    config_file = {
        "oidc_issuer_url": os.environ["keycloak_issuer_url"],
        "provider": "oidc",
        "upstreams": ["static://202"],
        "http_address": "0.0.0.0:4180",
        "oidc_groups_claim": "groups",
        "skip_jwt_bearer_tokens": True,
        "oidc_email_claim": "email",
        "allowed_groups": ["MAIA:" + user_config["group_ID"], os.environ.get("admin_group_ID", "MAIA:admin")],
        "scope": "openid email profile",
        "redirect_url": "https://{}.{}/oauth2/callback".format(user_config["group_subdomain"], cluster_config["domain"]),
        "email_domains": ["*"],
        "proxy_prefix": "/oauth2",
        "ssl_insecure_skip_verify": True,
        "insecure_oidc_skip_issuer_verification": True,
        "cookie_secure": True,
        "reverse_proxy": True,
        "pass_access_token": True,
        "pass_authorization_header": True,
        "set_authorization_header": True,
        "set_xauthrequest": True,
        "pass_user_headers": True,
        "whitelist_domains": ["*"],
    }

    if cluster_config["url_type"] == "subpath":
        config_file["redirect_url"] = "https://{}/oauth2-{}/callback".format(
            cluster_config["domain"], user_config["group_subdomain"]
        )
        config_file["proxy_prefix"] = "/oauth2-{}".format(user_config["group_subdomain"])

    oauth2_proxy_config = {
        "config": {
            "clientID": os.environ["keycloak_client_id"],
            "clientSecret": os.environ["keycloak_client_secret"],
            "cookieSecret": token_urlsafe(16),
            "configFile": toml.dumps(config_file),
        },
        "redis": {"enabled": True, "global": {"storageClass": cluster_config["storage_class"]}},
        "sessionStorage": {"type": "redis"},
        "image": {"repository": "quay.io/oauth2-proxy/oauth2-proxy", "tag": "", "pullPolicy": "IfNotPresent"},
        "service": {"type": "ClusterIP", "portNumber": 80, "appProtocol": "https", "annotations": {}},
        "serviceAccount": {"enabled": True, "name": "", "automountServiceAccountToken": True, "annotations": {}},
        "ingress": {
            "enabled": True,
            "path": "/oauth2",
            "pathType": "Prefix",
            "tls": [
                {
                    "secretName": "{}.{}-tls".format(user_config["group_subdomain"], cluster_config["domain"]),
                    "hosts": ["{}.{}".format(user_config["group_subdomain"], cluster_config["domain"])],
                }
            ],
            "hosts": ["{}.{}".format(user_config["group_subdomain"], cluster_config["domain"])],
            "annotations": {},
        },
    }

    if cluster_config["url_type"] == "subpath":
        oauth2_proxy_config["ingress"]["hosts"] = [cluster_config["domain"]]
        oauth2_proxy_config["ingress"]["tls"][0]["hosts"] = [cluster_config["domain"]]
        oauth2_proxy_config["ingress"]["path"] = "/oauth2-{}".format(user_config["group_subdomain"])
    if "nginx_cluster_issuer" in cluster_config:
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            oauth2_proxy_config["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            oauth2_proxy_config["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config[
                "nginx_cluster_issuer"
            ]
    if "traefik_resolver" in cluster_config:
        oauth2_proxy_config["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        oauth2_proxy_config["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            ...
        else:

            oauth2_proxy_config["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config["traefik_resolver"]
            )

    oauth2_proxy_config["chart_name"] = "oauth2-proxy"
    oauth2_proxy_config["chart_version"] = "7.7.8"
    oauth2_proxy_config["repo_url"] = "https://oauth2-proxy.github.io/manifests"

    Path(config_folder).joinpath(user_config["group_ID"], "oauth2_proxy_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(user_config["group_ID"], "oauth2_proxy_values", "oauth2_proxy_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(oauth2_proxy_config))

    return {
        "namespace": user_config["group_ID"].lower().replace("_", "-"),
        "release": user_config["group_ID"].lower().replace("_", "-") + "-oauth2-proxy",
        "chart": oauth2_proxy_config["chart_name"],
        "repo": oauth2_proxy_config["repo_url"],
        "version": oauth2_proxy_config["chart_version"],
        "values": str(Path(config_folder).joinpath(user_config["group_ID"], "oauth2_proxy_values", "oauth2_proxy_values.yaml")),
    }


def deploy_mysql(cluster_config, user_config, config_folder, mysql_configs):
    """
    Deploy a MySQL instance on a Kubernetes cluster using Helm.

    Parameters
    ----------
    cluster_config : dict
        Configuration dictionary for the cluster, including storage class.
    user_config : dict
        Configuration dictionary for the user, including group ID.
    config_folder : str
        Path to the folder where configuration files will be stored.
    mysql_configs : dict
        Configuration dictionary for MySQL, including user, password, and other settings.

    Returns
    -------
    dict
        A dictionary containing deployment details such as namespace, release name,
        chart name, repository URL, version, and values file path.
    """
    namespace = user_config["group_ID"].lower().replace("_", "-")
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())

    if "MYSQL_MEMORY_REQUEST_" + namespace in os.environ:
        memory_request = os.environ["MYSQL_MEMORY_REQUEST_" + namespace]
    else:
        memory_request = os.environ.get("MYSQL_MEMORY_REQUEST", "2Gi")
    if "MYSQL_MEMORY_LIMIT_" + namespace in os.environ:
        memory_limit = os.environ["MYSQL_MEMORY_LIMIT_" + namespace]
    else:
        memory_limit = os.environ.get("MYSQL_MEMORY_LIMIT", "2Gi")
    if "MYSQL_CPU_REQUEST_" + namespace in os.environ:
        cpu_request = os.environ["MYSQL_CPU_REQUEST_" + namespace]
    else:
        cpu_request = os.environ.get("MYSQL_CPU_REQUEST", "500m")
    if "MYSQL_CPU_LIMIT_" + namespace in os.environ:
        cpu_limit = os.environ["MYSQL_CPU_LIMIT_" + namespace]
    else:
        cpu_limit = os.environ.get("MYSQL_CPU_LIMIT", "500m")
    mysql_config = {
        "namespace": namespace,
        "chart_name": "mysql-db-v1",
        "docker_image": mysql_image,
        "tag": mysql_image_version,
        "memory_request": memory_request,
        "memory_limit": memory_limit,
        "cpu_request": cpu_request,
        "cpu_limit": cpu_limit,
        "deployment": True,
        "ports": {"mysql": [3306]},
        "persistent_volume": [
            {
                "mountPath": "/var/lib/mysql",
                "size": "20Gi",
                "access_mode": "ReadWriteOnce",
                "pvc_type": cluster_config["storage_class"],
            }
        ],
        "env_variables": {
            "MYSQL_ROOT_PASSWORD": mysql_configs.get("mysql_password", "root"),
            "MYSQL_USER": mysql_configs.get("mysql_user", "root"),
            "MYSQL_PASSWORD": mysql_configs.get("mysql_password", "root"),
            "MYSQL_DATABASE": "mysql",
        },
    }  # TODO: Change this to updated values

    mysql_values = read_config_dict_and_generate_helm_values_dict(mysql_config, kubeconfig)
    mysql_values["chart_version"] = mkg_chart_version
    if mkg_chart_type == "git_repo":
        mysql_values["path"] = "charts/maiakubegate"
        mysql_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
    else:
        mysql_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        mysql_values["chart_name"] = "mkg"

    Path(config_folder).joinpath(user_config["group_ID"], "mysql_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(user_config["group_ID"], "mysql_values", "mysql_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(mysql_values))

    return {
        "namespace": user_config["group_ID"].lower().replace("_", "-"),
        "release": user_config["group_ID"].lower().replace("_", "-") + "-mysql",
        "chart": mysql_values["chart_name"] if mkg_chart_type == "helm_repo" else mysql_values["path"],
        "repo": mysql_values["repo_url"],
        "version": mysql_values["chart_version"],
        "values": str(Path(config_folder).joinpath(user_config["group_ID"], "mysql_values", "mysql_values.yaml")),
    }


def deploy_mlflow(cluster_config, user_config, config_folder, mysql_config=None, minio_config=None):
    """
    Deploy an MLflow instance on a Kubernetes cluster using Helm.

    Parameters
    ----------
    cluster_config : dict
        Configuration dictionary for the Kubernetes cluster.
    user_config : dict
        Configuration dictionary for the user, including group_ID.
    config_folder : str
        Path to the folder where configuration files will be stored.
    mysql_config : dict, optional
        Configuration dictionary for MySQL, including mysql_user and mysql_password. Defaults to None.
    minio_config : dict, optional
        Configuration dictionary for MinIO, including console_access_key and console_secret_key. Defaults to None.

    Returns
    -------
    dict
        A dictionary containing deployment details such as namespace, release name,
        chart name, repository URL, chart version, and path to the values file.
    """
    namespace = user_config["group_ID"].lower().replace("_", "-")
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    default_registry = os.environ.get("MAIA_REGISTRY", "ghcr.io/minnelab")
    docker_image = os.environ.get("MAIA_PRIVATE_REGISTRY", default_registry) + "/maia-mlflow"
    if "MAIA_PRIVATE_REGISTRY_" + namespace in os.environ:
        docker_image = os.environ["MAIA_PRIVATE_REGISTRY_" + namespace] + "/maia-mlflow"

    private_registry = os.environ.get("MAIA_PRIVATE_REGISTRY", None)
    if "MAIA_PRIVATE_REGISTRY_" + namespace in os.environ:
        private_registry = os.environ["MAIA_PRIVATE_REGISTRY_" + namespace]

    if "MLFLOW_MEMORY_REQUEST_" + namespace in os.environ:
        memory_request = os.environ["MLFLOW_MEMORY_REQUEST_" + namespace]
    else:
        memory_request = os.environ.get("MLFLOW_MEMORY_REQUEST", "2Gi")
    if "MLFLOW_MEMORY_LIMIT_" + namespace in os.environ:
        memory_limit = os.environ["MLFLOW_MEMORY_LIMIT_" + namespace]
    else:
        memory_limit = os.environ.get("MLFLOW_MEMORY_LIMIT", "2Gi")
    if "MLFLOW_CPU_REQUEST_" + namespace in os.environ:
        cpu_request = os.environ["MLFLOW_CPU_REQUEST_" + namespace]
    else:
        cpu_request = os.environ.get("MLFLOW_CPU_REQUEST", "500m")
    if "MLFLOW_CPU_LIMIT_" + namespace in os.environ:
        cpu_limit = os.environ["MLFLOW_CPU_LIMIT_" + namespace]
    else:
        cpu_limit = os.environ.get("MLFLOW_CPU_LIMIT", "500m")
    mlflow_config = {
        "namespace": namespace,
        "chart_name": "mlflow-v1",
        "docker_image": docker_image,
        "tag": maia_mlflow_image_version,
        "deployment": True,
        "memory_request": memory_request,
        "memory_limit": memory_limit,
        "cpu_request": cpu_request,
        "cpu_limit": cpu_limit,
        "allocationTime": "180d",
        "ports": {"proxy": [80]},
        "ingress": {
            "enabled": True,
            "path": "mlflow",
            "host": f"{user_config['group_subdomain']}.{cluster_config['domain']}",
            "port": 80,
            "annotations": {},
        },
        "user_secret": [namespace],
        "user_secret_params": ["user", "password"],
        "env_variables": {
            "MYSQL_URL": "{}-mysql-mkg".format(namespace),
            "MYSQL_PASSWORD": mysql_config.get("mysql_password", "root"),
            "RUN_MINIO_PROXY": "True",
            "NAMESPACE": namespace,
            "MYSQL_USER": mysql_config.get("mysql_user", "root"),
            "BUCKET_NAME": "mlflow",
            "BUCKET_PATH": "mlflow",
            "AWS_ACCESS_KEY_ID": base64.b64decode(minio_config.get("console_access_key", "minio")).decode("utf-8"),
            "AWS_SECRET_ACCESS_KEY": base64.b64decode(minio_config.get("console_secret_key", "minio")).decode("utf-8"),
            "MLFLOW_S3_ENDPOINT_URL": "http://minio:80",
            "MLFLOW_PATH": "mlflow",
            "MINIO_CONSOLE_PATH": f"minio-console-{namespace}",
            "KUBEFLOW_URL": "https://kubeflow." + cluster_config["domain"],
        },
    }

    if cluster_config["url_type"] == "subpath":
        mlflow_config["ingress"]["path"] = "{}-mlflow".format(user_config["group_subdomain"])
        mlflow_config["ingress"]["host"] = cluster_config["domain"]
        mlflow_config["env_variables"]["MLFLOW_PATH"] = "{}-mlflow".format(user_config["group_subdomain"])
        mlflow_config["env_variables"]["MINIO_CONSOLE_PATH"] = "{}-minio-console".format(user_config["group_subdomain"])

    if "nginx_cluster_issuer" in cluster_config:
        mlflow_config["ingress"]["tlsSecretName"] = "{}.{}-tls".format(user_config["group_subdomain"], cluster_config["domain"])
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            mlflow_config["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"

        else:
            mlflow_config["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config["nginx_cluster_issuer"]
    if "traefik_resolver" in cluster_config:
        mlflow_config["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        mlflow_config["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            ...
        else:
            mlflow_config["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = cluster_config[
                "traefik_resolver"
            ]

    if private_registry is not None:
        mlflow_config["image_pull_secret"] = private_registry.replace(".", "-").replace("/", "-")
    mlflow_values = read_config_dict_and_generate_helm_values_dict(mlflow_config, kubeconfig)
    if mkg_chart_type == "helm_repo":
        mlflow_values["chart_name"] = "mkg"
        mlflow_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
    else:
        mlflow_values["path"] = "charts/maiakubegate"
        mlflow_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
    mlflow_values["chart_version"] = mkg_chart_version

    Path(config_folder).joinpath(user_config["group_ID"], "mlflow_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(user_config["group_ID"], "mlflow_values", "mlflow_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(mlflow_values))

    return {
        "namespace": user_config["group_ID"].lower().replace("_", "-"),
        "release": user_config["group_ID"].lower().replace("_", "-") + "-mlflow",
        "chart": mlflow_values["chart_name"] if mkg_chart_type == "helm_repo" else mlflow_values["path"],
        "repo": mlflow_values["repo_url"],
        "version": mlflow_values["chart_version"],
        "values": str(Path(config_folder).joinpath(user_config["group_ID"], "mlflow_values", "mlflow_values.yaml")),
    }


def deploy_orthanc(cluster_config, user_config, config_folder, project_config_dict=None):
    """
    Deploys Orthanc using the provided configuration.
    Parameters
    ----------
    cluster_config : dict
        Dictionary containing the cluster configuration.
    user_config : dict
        Dictionary containing the user configuration.
    config_folder : str or Path
        Path to the configuration folder.
    Returns
    -------
    dict
        A dictionary containing deployment details such as namespace, release, chart, repo, version, and values file path.
    """

    with open(Path(config_folder).joinpath(user_config["group_ID"], "maia_namespace_values", "namespace_values.yaml"), "r") as f:
        namespace_values = yaml.safe_load(f)
        orthanc_port = namespace_values["orthanc"]["port"]
    namespace = user_config["group_ID"].lower().replace("_", "-")
    orthanc_configs = generate_orthanc_configs(namespace, project_config_dict)
    ae_title = orthanc_configs["ae_title"]
    mysql_password = orthanc_configs["mysql_password"]
    private_registry = os.environ.get("MAIA_PRIVATE_REGISTRY", None)
    if "MAIA_PRIVATE_REGISTRY_" + namespace in os.environ:
        private_registry = os.environ["MAIA_PRIVATE_REGISTRY_" + namespace]

    default_registry = os.environ.get("MAIA_REGISTRY", "ghcr.io/minnelab")
    docker_image = f"{default_registry}/{maia_orthanc_image}"
    docker_version = maia_orthanc_image_version
    if "maia_orthanc_image_" + namespace in os.environ:
        docker_image = os.environ["maia_orthanc_image_" + namespace]
    if "maia_orthanc_version_" + namespace in os.environ:
        docker_version = os.environ["maia_orthanc_version_" + namespace]

    image_pull_secret = os.environ.get("imagePullSecrets", None)
    if "imagePullSecrets_" + namespace in os.environ:
        image_pull_secret = os.environ["imagePullSecrets_" + namespace]

    if "ORTHANC_CPU_REQUEST_" + namespace in os.environ:
        cpu_request = os.environ["ORTHANC_CPU_REQUEST_" + namespace]
    else:
        cpu_request = os.environ.get("ORTHANC_CPU_REQUEST", "4000m")
    if "ORTHANC_CPU_LIMIT_" + namespace in os.environ:
        cpu_limit = os.environ["ORTHANC_CPU_LIMIT_" + namespace]
    else:
        cpu_limit = os.environ.get("ORTHANC_CPU_LIMIT", "4000m")

    if "ORTHANC_MEMORY_REQUEST_" + namespace in os.environ:
        memory_request = os.environ["ORTHANC_MEMORY_REQUEST_" + namespace]
    else:
        memory_request = os.environ.get("ORTHANC_MEMORY_REQUEST", "4Gi")
    if "ORTHANC_MEMORY_LIMIT_" + namespace in os.environ:
        memory_limit = os.environ["ORTHANC_MEMORY_LIMIT_" + namespace]
    else:
        memory_limit = os.environ.get("ORTHANC_MEMORY_LIMIT", "4Gi")
    orthanc_config = {
        "pvc": {"pvc_type": cluster_config["shared_storage_class"], "access_mode": "ReadWriteMany", "size": "10Gi"},
        "imagePullSecret": image_pull_secret,
        "image": {"repository": docker_image, "tag": docker_version},
        "cpu_request": cpu_request,
        "cpu_limit": cpu_limit,
        "memory_request": memory_request,
        "memory_limit": memory_limit,
        "gpu": False,
        "orthanc_dicom_service_annotations": {},
        "ingress_annotations": {},
        "ingress_tls": {"host": ""},
        "monai_label_path": f"monai-label-{ae_title}",
        "orthanc_path": f"orthanc-{ae_title}",
        "orthanc_node_port": orthanc_port,
        "serviceType": "NodePort",
    }

    if "MONAI_LABEL_AUTH_USERNAME_" + namespace in os.environ and "MONAI_LABEL_AUTH_PASSWORD_" + namespace in os.environ:
        orthanc_config["monai_label_auth"] = {
            "enabled": True,
            "username": os.environ["MONAI_LABEL_AUTH_USERNAME_" + namespace],
            "password": os.environ["MONAI_LABEL_AUTH_PASSWORD_" + namespace],
        }
    else:
        orthanc_config["monai_label_auth"] = {
            "enabled": False,
        }
    if cluster_config["shared_storage_class"] == "local-path":
        orthanc_config["pvc"]["access_mode"] = "ReadWriteOnce"

    enable_mysql = True
    if enable_mysql:
        orthanc_config["mysql"] = {
            "enabled": True,
            "mysqlRootPassword": mysql_password,
            "mysqlUser": "maia-admin",
            "mysqlPassword": mysql_password,
            "mysqlDatabase": "orthanc",
            "image": mysql_image,
            "tag": mysql_image_version,
        }

    if private_registry is not None:
        orthanc_config["imagePullSecret"] = private_registry.replace(".", "-").replace("/", "-")

    namespace = user_config["group_ID"].lower().replace("_", "-")
    orthanc_custom_config = {
        "LuaScripts": ["/mnt/msp_models.lua"],
        "StableAge": 5,
        "DicomModalities": {
            # f"{namespace}-xnat": [f"{namespace}-XNAT", "maia-xnat.xnat", "8104"],
            f"{ae_title}": [f"{ae_title}", "maia-xnat.xnat", "8104"],
            # [ "DCM4CHEE", "dcm4chee-service.services", 11115 ]
        },
        "DicomWeb": {
            "Servers": {
                f"{namespace}-xnat": {
                    "Url": "http://maia-xnat.xnat:8104",
                    # http://dcm4chee-service.services:8080/dcm4chee-arc/aets/KAAPANA/rs
                    "HasDelete": False,
                }
            }
        },
    }

    if enable_mysql:
        orthanc_custom_config["MySQL"] = {
            "EnableIndex": True,
            "EnableStorage": False,
            "Host": user_config["group_ID"].lower().replace("_", "-") + "-orthanc-mysql",
            "Port": 3306,
            "UnixSocket": "",
            "Database": "orthanc",
            "Username": "maia-admin",
            "Password": mysql_password,
            "EnableSsl": False,
            "SslVerifyServerCertificates": True,
            "SslCACertificates": "",
            "Lock": True,
            "MaximumConnectionRetries": 10,
            "ConnectionRetryInterval": 5,
            "IndexConnectionsCount": 1,
        }

    orthanc_config.update({"orthanc_config_map": {"enabled": True, "orthanc_config": orthanc_custom_config}})
    if project_config_dict and "monai_label_models" in project_config_dict:
        orthanc_config["orthanc_config_map"]["models_json"] = project_config_dict["monai_label_models"]

    domain = cluster_config["domain"]
    group_subdomain = user_config["group_subdomain"]

    if "url_type" in cluster_config:
        if cluster_config["url_type"] == "subdomain":
            orthanc_address = f"{group_subdomain}.{domain}"
        elif cluster_config["url_type"] == "subpath":
            orthanc_address = domain
        else:
            orthanc_address = None

    if orthanc_address is not None:
        orthanc_config["ingress_tls"]["host"] = orthanc_address

    if cluster_config["ssh_port_type"] == "LoadBalancer":
        orthanc_config["orthanc_dicom_service_annotations"]["metallb.universe.tf/allow-shared-ip"] = cluster_config.get(
            "metallb_shared_ip", False
        )
        orthanc_config["orthanc_dicom_service_annotations"]["metallb.io/ip-allocated-from-pool"] = cluster_config.get(
            "metallb_ip_pool", False
        )
        orthanc_config["orthanc_node_port"] = {"loadBalancer": orthanc_port}
        orthanc_config["loadBalancerIp"] = cluster_config.get("maia_metallb_ip", False)
        if project_config_dict and "ip_whitelist" in project_config_dict:
            orthanc_config["ipWhitelist"] = project_config_dict["ip_whitelist"]
        orthanc_config["serviceType"] = "LoadBalancer"
    if "nginx_cluster_issuer" in cluster_config:
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            orthanc_config["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            orthanc_config["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config["nginx_cluster_issuer"]
        orthanc_config["ingress_tls"]["secretName"] = "{}.{}-tls".format(user_config["group_subdomain"], cluster_config["domain"])
        orthanc_config["ingress_annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "8g"
        orthanc_config["ingress_annotations"]["nginx.ingress.kubernetes.io/proxy-read-timeout"] = "300"
        orthanc_config["ingress_annotations"]["nginx.ingress.kubernetes.io/proxy-send-timeout"] = "300"
    if "traefik_resolver" in cluster_config:
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            ...
        else:
            orthanc_config["ingress_annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        orthanc_config["ingress_annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        orthanc_config["ingress_annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = cluster_config[
            "traefik_resolver"
        ]
    orthanc_config["chart_version"] = maia_orthanc_chart_version
    if maia_orthanc_chart_type == "helm_repo":
        orthanc_config["chart_name"] = "maia-orthanc"
        orthanc_config["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
    else:
        orthanc_config["path"] = "charts/maia-orthanc"
        orthanc_config["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")

    Path(config_folder).joinpath(user_config["group_ID"], "orthanc_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(user_config["group_ID"], "orthanc_values", "orthanc_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(orthanc_config))

    return {
        "namespace": user_config["group_ID"].lower().replace("_", "-"),
        "release": user_config["group_ID"].lower().replace("_", "-") + "-orthanc",
        "chart": orthanc_config["chart_name"] if maia_orthanc_chart_type == "helm_repo" else orthanc_config["path"],
        "repo": orthanc_config["repo_url"],
        "version": orthanc_config["chart_version"],
        "values": str(Path(config_folder).joinpath(user_config["group_ID"], "orthanc_values", "orthanc_values.yaml")),
    }


def deploy_kubeflow_project(cluster_config, user_config, config_folder, project_config_dict=None, minimal=True):
    """
    Deploy a Kubeflow project using the provided configuration.
    Parameters
    ----------
    cluster_config : dict
        Dictionary containing the cluster configuration.
    user_config : dict
        Dictionary containing the user configuration.
    config_folder : str or Path
        Path to the configuration folder.
    project_config_dict : dict, optional
        Dictionary containing the project configuration.
    Returns
    -------
    dict
        A dictionary containing deployment details such as namespace, release, chart, repo, version, and values file path.
    """
    helm_template = create_jupyterhub_config_api(project_config_dict, cluster_config, config_folder, minimal=minimal)

    jh_template_file = helm_template["values"]
    with open(jh_template_file, "r") as f:
        jh_template = yaml.safe_load(f)

    extra_env = []
    for key, value in jh_template["singleuser"]["extraEnv"].items():
        extra_env.append({"name": key, "value": value})
    if "environment" in jh_template["singleuser"]["profileList"][0]["kubespawner_override"]:
        for k, v in jh_template["singleuser"]["profileList"][0]["kubespawner_override"]["environment"].items():
            extra_env.append({"name": k, "value": v})
    extra_resource_limits = {}
    for k, v in jh_template["singleuser"]["profileList"][0]["kubespawner_override"]["extra_resource_limits"].items():
        extra_resource_limits[k] = v

    namespace = user_config["group_ID"].lower().replace("_", "-")
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()
    podCIDR = []
    nodes = v1.list_node(watch=False)
    for node in nodes.items:
        podCIDR.append(node.spec.pod_cidr)
    podCIDR = list(set(podCIDR))

    ipList = []
    if project_config_dict and "ip_whitelist" in project_config_dict:
        ipList = project_config_dict["ip_whitelist"]
    ipList.extend(podCIDR)
    kubeflow_config = {
        "namespace": namespace,
        "owner": user_config["users"][0],
        "user_email": user_config["users"][0],
        "user_id": convert_username_to_jupyterhub_username(user_config["users"][0]),
        "podCIDR": podCIDR,
        "ipList": ipList,
        "cpu": jh_template["singleuser"]["cpu"],
        "memory": jh_template["singleuser"]["memory"],
        "extraEnv": extra_env,
        "extraResourceLimits": extra_resource_limits,
        "image": jh_template["singleuser"]["profileList"][0]["kubespawner_override"]["image"],
        "homeMountPath": jh_template["singleuser"]["storage"]["homeMountPath"],
        "homePVC": "claim-" + convert_username_to_jupyterhub_username(user_config["users"][0]),
        "extraVolumes": jh_template["singleuser"]["storage"]["extraVolumes"],
        "extraVolumeMounts": jh_template["singleuser"]["storage"]["extraVolumeMounts"],
    }
    kubeflow_config["chart_version"] = maia_kubeflow_chart_version
    if maia_kubeflow_chart_type == "helm_repo":
        kubeflow_config["chart_name"] = "maia-kubeflow-project"
        kubeflow_config["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
    else:
        kubeflow_config["path"] = "charts/maia-kubeflow-project"
        kubeflow_config["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")

    Path(config_folder).joinpath(user_config["group_ID"], "kubeflow_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(user_config["group_ID"], "kubeflow_values", "kubeflow_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(kubeflow_config))

    return {
        "namespace": user_config["group_ID"].lower().replace("_", "-"),
        "release": user_config["group_ID"].lower().replace("_", "-") + "-kubeflow",
        "chart": kubeflow_config["chart_name"] if maia_kubeflow_chart_type == "helm_repo" else kubeflow_config["path"],
        "repo": kubeflow_config["repo_url"],
        "version": kubeflow_config["chart_version"],
        "values": str(Path(config_folder).joinpath(user_config["group_ID"], "kubeflow_values", "kubeflow_values.yaml")),
    }


def gpu_list_from_nodes():
    """
    Retrieves a list of GPUs from the nodes in a Kubernetes cluster.

    This function loads the Kubernetes configuration from the environment,
    initializes the Kubernetes client, and retrieves the list of nodes.
    It then checks each node to see if it is ready and has GPU labels,
    and constructs a dictionary with the node names as keys and a list
    containing the GPU product and count as values.

    Returns
    -------
    dict
        A dictionary where the keys are node names and the values are lists
        containing the GPU product and GPU count.
    """

    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()

    nodes = v1.list_node(watch=False)
    gpu_dict = {}
    for node in nodes.items:
        for status in node.status.conditions:
            if status.type == "Ready" and status.status == "True":
                if "nvidia.com/gpu.product" in node.metadata.labels:
                    gpu_dict[node.metadata.name] = [
                        node.metadata.labels["nvidia.com/gpu.product"],
                        node.metadata.labels["nvidia.com/gpu.count"],
                    ]
    return gpu_dict


def edit_orthanc_configuration(orthanc_config_template, orthanc_edit_dict):
    with open(orthanc_config_template, "r") as f:
        orthanc_config = json.load(f)

    for key, value in orthanc_edit_dict.items():
        orthanc_config[key] = value

    return orthanc_config


def generate_minio_configs(namespace, project_config_dict=None):
    """
    Generate configuration settings for MinIO.

    Parameters
    ----------
    namespace : int or str
        The unique identifier for the project.
    project_config_dict : dict, optional
        A dictionary containing the custom configuration for the MinIO.
    Returns
    -------
    dict
        A dictionary with the following keys:
        - access_key (str): The access key for MinIO.
        - secret_key (str): A randomly generated secret key for MinIO.
        - console_access_key (str): A base64 encoded access key for console access.
        - console_secret_key (str): A base64 encoded secret key for console access.
    """

    existing_minio_configs = get_minio_config_if_exists(namespace)
    minio_configs = {
        "access_key": "admin",
        "secret_key": (
            existing_minio_configs["secret_key"]
            if "secret_key" in existing_minio_configs
            else token_urlsafe(16).replace("-", "_")
        ),
        "console_access_key": (
            base64.b64encode(existing_minio_configs["console_access_key"].encode("ascii")).decode("ascii")
            if "console_access_key" in existing_minio_configs
            else base64.b64encode(token_urlsafe(16).replace("-", "_").encode("ascii")).decode("ascii")
        ),
        "console_secret_key": (
            base64.b64encode(existing_minio_configs["console_secret_key"].encode("ascii")).decode("ascii")
            if "console_secret_key" in existing_minio_configs
            else base64.b64encode(token_urlsafe(16).replace("-", "_").encode("ascii")).decode("ascii")
        ),
    }

    if project_config_dict:
        for key, value in project_config_dict.items():
            if key == "minio_user":
                minio_configs["access_key"] = base64.b64encode(value.encode("ascii")).decode("ascii")
            if key == "minio_password":
                minio_configs["secret_key"] = base64.b64encode(value.encode("ascii")).decode("ascii")

        if key == "minio_console_access_key":
            minio_configs["console_access_key"] = base64.b64encode(value.encode("ascii")).decode("ascii")
        if key == "minio_console_secret_key":
            minio_configs["console_secret_key"] = base64.b64encode(value.encode("ascii")).decode("ascii")

    return minio_configs


def get_minio_config_if_exists(project_id):
    """
    Retrieves MinIO configuration if it exists for the given project ID.
    This function loads the Kubernetes configuration from the environment,
    accesses the Kubernetes API to list secrets in the specified namespace,
    and extracts MinIO-related configuration from the secrets.

    Parameters
    ----------
    project_id : str
        The ID of the project for which to retrieve the MinIO configuration.

    Returns
    -------
    dict
        A dictionary containing MinIO configuration keys and their corresponding values.
        The dictionary may contain the following keys:
        - "access_key": The default access key (always "admin").
        - "console_access_key": The console access key, if found.
        - "console_secret_key": The console secret key, if found.
        - "secret_key": The MinIO root password, if found.
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()
    minio_configs = {"access_key": "admin"}
    try:
        secrets = v1.list_namespaced_secret(namespace=project_id.lower().replace("_", "-"))
    except client.exceptions.ApiException as e:
        if e.status == 404 or e.status == 401 or e.status == 403:
            logger.error(f"Error listing namespaced secrets: {e}")
            return minio_configs
        else:
            raise e
    for secret in secrets.items:
        if secret.metadata.name == "storage-user":
            for item in secret.data:

                decoded_value = base64.b64decode(secret.data[item]).decode("ascii")
                if item == "CONSOLE_ACCESS_KEY":
                    minio_configs["console_access_key"] = decoded_value
                if item == "CONSOLE_SECRET_KEY":
                    minio_configs["console_secret_key"] = decoded_value
        if secret.metadata.name == "storage-configuration":
            for _, value in secret.data.items():
                decoded_value = base64.b64decode(value).decode("ascii")
                for line in decoded_value.split("\n"):
                    if line.startswith("export MINIO_ROOT_PASSWORD="):
                        minio_configs["secret_key"] = line[len("export MINIO_ROOT_PASSWORD=") :]

    return minio_configs


def generate_mlflow_configs(namespace, project_config_dict=None):
    """
    Generate MLflow configuration dictionary with encoded user and password.

    Parameters
    ----------
    namespace : str
        The namespace to be encoded as the MLflow user.

    project_config_dict : dict, optional
        A dictionary containing the custom configuration for the MLflow.
    Returns
    -------
    dict
        A dictionary containing the encoded MLflow user and password.
    """
    existing_mlflow_configs = get_mlflow_config_if_exists(namespace)

    mlflow_configs = {
        "mlflow_user": (
            base64.b64encode(existing_mlflow_configs["mlflow_user"].encode("ascii")).decode("ascii")
            if "mlflow_user" in existing_mlflow_configs
            else base64.b64encode(namespace.encode("ascii")).decode("ascii")
        ),
        "mlflow_password": (
            base64.b64encode(existing_mlflow_configs["mlflow_password"].replace("-", "_").encode("ascii")).decode("ascii")
            if "mlflow_password" in existing_mlflow_configs
            else base64.b64encode(token_urlsafe(16).replace("-", "_").encode("ascii")).decode("ascii")
        ),
    }
    if project_config_dict:
        for key, value in project_config_dict.items():
            if key == "mlflow_user":
                mlflow_configs["mlflow_user"] = base64.b64encode(value.encode("ascii")).decode("ascii")
            if key == "mlflow_password":
                mlflow_configs["mlflow_password"] = base64.b64encode(value.replace("-", "_").encode("ascii")).decode("ascii")

    return mlflow_configs


def get_mlflow_config_if_exists(project_id):
    """
    Retrieve MLflow configuration from Kubernetes secrets if they exist.

    Parameters
    ----------
    project_id : str
        The ID of the project for which to retrieve the MLflow configuration. This ID is used to
        locate the corresponding Kubernetes namespace and secrets.

    Returns
    -------
    dict
        A dictionary containing the MLflow configuration with keys "mlflow_user" and "mlflow_password"
        if they exist in the Kubernetes secrets. If the secrets are not found, an empty dictionary is returned.

    Raises
    ------
    KeyError
        If the "KUBECONFIG" environment variable is not set.
    yaml.YAMLError
        If there is an error parsing the Kubernetes configuration file.
    kubernetes.client.exceptions.ApiException
        If there is an error communicating with the Kubernetes API.
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()
    mlflow_configs = {}
    try:
        secrets = v1.list_namespaced_secret(namespace=project_id.lower().replace("_", "-"))
    except client.exceptions.ApiException as e:
        if e.status == 404 or e.status == 401 or e.status == 403:
            logger.error(f"Error listing namespaced secrets: {e}")
            return mlflow_configs
        else:
            raise e
    for secret in secrets.items:

        if secret.metadata.name == project_id.lower().replace("_", "-"):
            for item in secret.data:

                decoded_value = base64.b64decode(secret.data[item]).decode("ascii")
                if item == "user":
                    mlflow_configs["mlflow_user"] = decoded_value
                if item == "password":
                    mlflow_configs["mlflow_password"] = decoded_value

    return mlflow_configs


def generate_mysql_configs(namespace, project_config_dict=None):
    """
    Generate MySQL configuration dictionary.

    Parameters
    ----------
    namespace : str
        The namespace to be used as the MySQL user.

    project_config_dict : dict, optional
        A dictionary containing the custom configuration for the MySQL.

    Returns
    -------
    dict
        A dictionary containing MySQL user and password.
    """

    existing_mysql_configs = get_mysql_config_if_exists(namespace)

    mysql_configs = {
        "mysql_user": namespace,
        "mysql_password": (
            "".join(filter(str.isalnum, existing_mysql_configs["mysql_password"]))
            if "mysql_password" in existing_mysql_configs
            else "".join(filter(str.isalnum, token_urlsafe(16)))
        ),
    }

    if project_config_dict:
        for key, value in project_config_dict.items():
            if key == "mysql_user":
                mysql_configs["mysql_user"] = value
            if key == "mysql_password":
                mysql_configs["mysql_password"] = value

    return mysql_configs


def get_mysql_config_if_exists(project_id):
    """
    Retrieves MySQL configuration from Kubernetes environment variables if they exist.

    Parameters
    ----------
    project_id : str
        The ID of the project for which to retrieve the MySQL configuration. This ID is used to
        identify the namespace and the MySQL deployment within the Kubernetes cluster.

    Returns
    -------
    dict
        A dictionary containing the MySQL user and password if they exist in the environment
        variables of the MySQL deployment. The dictionary keys are:
        - "mysql_user": The MySQL user.
        - "mysql_password": The MySQL password.

    Notes
    -----
    This function assumes that the Kubernetes configuration file is specified in the environment
    variable "KUBECONFIG" and that the MySQL deployment name starts with the project ID followed
    by "-mysql-mkg".
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()
    mlflow_configs = {}
    try:
        deploy = v1.list_namespaced_pod(namespace=project_id.lower().replace("_", "-"))
    except client.exceptions.ApiException as e:
        if e.status == 404 or e.status == 401 or e.status == 403:
            logger.error(f"Error listing namespaced pods: {e}")
            return mlflow_configs
        else:
            raise e

    for deployment in deploy.items:
        if deployment.metadata.name.startswith(project_id.lower().replace("_", "-") + "-mysql-mkg"):
            envs = deployment.spec.containers[0].env
            for env in envs:
                if env.name == "MYSQL_USER":
                    mlflow_configs["mysql_user"] = env.value
                if env.name == "MYSQL_PASSWORD":
                    mlflow_configs["mysql_password"] = env.value

    return mlflow_configs


def get_orthanc_config_if_exists(project_id):
    """
    Retrieves Orthanc configuration from Kubernetes environment variables if they exist.
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()
    orthanc_configs = {}
    try:
        # Get ConfigMaps in the given namespace (from project_id)
        configmaps = v1.list_namespaced_config_map(namespace=project_id.lower().replace("_", "-"))
    except client.exceptions.ApiException as e:
        if e.status == 404 or e.status == 401 or e.status == 403:
            logger.error(f"Error listing namespaced pods: {e}")
            return orthanc_configs
        else:
            raise e

    for configmap in configmaps.items:
        if configmap.metadata.name.startswith(project_id.lower().replace("_", "-") + "-orthanc-orthanc-config"):
            for key, value in configmap.data.items():
                if key == "orthanc.json":
                    orthanc_configs["orthanc_config"] = value
    return orthanc_configs


def generate_orthanc_configs(project_id, project_config_dict=None):
    """
    Generates Orthanc configuration dictionary.
    """
    orthanc_configs = get_orthanc_config_if_exists(project_id)

    if "orthanc_config" in orthanc_configs:
        orthanc_config_str = orthanc_configs["orthanc_config"]
        orthanc_config_dict = json.loads(orthanc_config_str) if isinstance(orthanc_config_str, str) else orthanc_config_str
        ae_title = list(orthanc_config_dict["DicomModalities"].keys())[0]
        mysql_password = orthanc_config_dict["MySQL"]["Password"]
        orthanc_configs = {
            "ae_title": ae_title,
            "mysql_password": mysql_password,
        }
    else:
        mysql_password = generate_human_memorable_password(16)
        ae_title = generate_random_password(16)
        orthanc_configs = {
            "ae_title": ae_title,
            "mysql_password": mysql_password,
        }
    if project_config_dict:
        for key, value in project_config_dict.items():
            if key == "ae_title":
                orthanc_configs["ae_title"] = value
            if key == "mysql_password":
                orthanc_configs["mysql_password"] = value

    return orthanc_configs


def get_nvflare_dashboard_config_if_exists(project_id):
    """
    Retrieves NVFlare Dashboard configuration from Kubernetes environment variables if they exist.
    """
    if "KUBECONFIG_LOCAL" not in os.environ:
        os.environ["KUBECONFIG_LOCAL"] = os.environ["KUBECONFIG"]
    kubeconfig = yaml.safe_load(Path(os.environ["KUBECONFIG_LOCAL"]).read_text())
    config.load_kube_config_from_dict(kubeconfig)
    v1 = client.CoreV1Api()
    nvflare_dashboard_configs = {}
    try:
        deploy = v1.list_namespaced_pod(namespace=project_id.lower().replace("_", "-"))
    except client.exceptions.ApiException as e:
        if e.status == 404 or e.status == 401 or e.status == 403:
            logger.error(f"Error listing namespaced pods: {e}")
            return nvflare_dashboard_configs
        else:
            raise e
    for deploy in deploy.items:
        if deploy.metadata.name.startswith(project_id.lower().replace("_", "-") + "-nvflare-dashboard"):
            envs = deploy.spec.containers[0].env
            for env in envs:
                if env.name == "ADMIN_USERNAME":
                    nvflare_dashboard_configs["admin_username"] = env.value
                if env.name == "ADMIN_PASSWORD":
                    nvflare_dashboard_configs["admin_password"] = env.value
    return nvflare_dashboard_configs


def generate_nvflare_dashboard_configs(project_id, project_config_dict=None):
    """
    Generates NVFlare Dashboard configuration dictionary.
    """
    nvflare_dashboard_configs = get_nvflare_dashboard_config_if_exists(project_id)
    if "admin_username" in nvflare_dashboard_configs and "admin_password" in nvflare_dashboard_configs:
        return nvflare_dashboard_configs["admin_username"], nvflare_dashboard_configs["admin_password"]
    else:
        if project_config_dict:
            for key, value in project_config_dict.items():
                if key == "nvflare_dashboard_admin_username":
                    nvflare_dashboard_configs["admin_username"] = value
                if key == "nvflare_dashboard_admin_password":
                    nvflare_dashboard_configs["admin_password"] = value
        else:
            nvflare_dashboard_configs["admin_username"] = generate_random_password(16)
            nvflare_dashboard_configs["admin_password"] = generate_random_password(16)
    return nvflare_dashboard_configs["admin_username"], nvflare_dashboard_configs["admin_password"]


def create_maia_namespace_values(namespace_config, cluster_config, config_folder, minio_configs=None, mlflow_configs=None):
    """
    Create MAIA namespace values for deployment.

    Parameters
    ----------
    namespace_config : dict
        Configuration for the namespace, including group ID and users.
    cluster_config : dict
        Configuration for the cluster, including SSH port type, port range, and storage class.
    config_folder : str
        Path to the folder where configuration files will be saved.
    minio_configs : dict, optional
        Configuration for MinIO, including access keys and console keys. Defaults to None.
    mlflow_configs : dict, optional
        Configuration for MLflow, including user and password. Defaults to None.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values file.
    """

    maia_metallb_ip = cluster_config.get("maia_metallb_ip", None)
    ssh_ports = get_ssh_ports(
        len(namespace_config["users"]) + 1,
        cluster_config["ssh_port_type"],
        cluster_config["port_range"],
        maia_metallb_ip=maia_metallb_ip,
    )
    ssh_port_list = get_ssh_port_dict(
        cluster_config["ssh_port_type"],
        namespace_config["group_ID"].lower().replace("_", "-"),
        cluster_config["port_range"],
        maia_metallb_ip=maia_metallb_ip,
    )

    ssh_port_dict = {list(entry.keys())[0]: list(entry.values())[0] for entry in ssh_port_list}

    users = []

    if cluster_config["ssh_port_type"] == "LoadBalancer":
        for user in namespace_config["users"]:
            if "jupyter-" + convert_username_to_jupyterhub_username(user) in ssh_port_dict:
                users.append(
                    {
                        "jupyterhub_username": convert_username_to_jupyterhub_username(user),
                        "sshPort": ssh_port_dict["jupyter-" + convert_username_to_jupyterhub_username(user)],
                    }
                )
            else:
                users.append({"jupyterhub_username": convert_username_to_jupyterhub_username(user), "sshPort": ssh_ports.pop(0)})
    else:
        for ssh_port, user in zip(ssh_ports[:-1], namespace_config["users"]):
            if "jupyter-" + convert_username_to_jupyterhub_username(user) in ssh_port_dict:
                users.append(
                    {
                        "jupyterhub_username": convert_username_to_jupyterhub_username(user),
                        "sshPort": ssh_port_dict["jupyter-" + convert_username_to_jupyterhub_username(user)],
                    }
                )
            else:
                users.append({"jupyterhub_username": convert_username_to_jupyterhub_username(user), "sshPort": ssh_port})

    namespace = namespace_config["group_ID"].lower().replace("_", "-")

    if cluster_config["ssh_port_type"] == "LoadBalancer":
        if f"{namespace}-orthanc-svc-orthanc" in ssh_port_dict:
            orthanc_ssh_port = ssh_port_dict[f"{namespace}-orthanc-svc-orthanc"]
        else:
            orthanc_ssh_port = ssh_ports.pop(0)
    else:
        if f"{namespace}-orthanc-svc-orthanc" in ssh_port_dict:
            orthanc_ssh_port = ssh_port_dict[f"{namespace}-orthanc-svc-orthanc"]
        else:
            orthanc_ssh_port = ssh_ports[-1]

    maia_namespace_values = {
        "pvc": {"pvc_type": cluster_config["shared_storage_class"], "access_mode": "ReadWriteMany", "size": "10Gi"},
        "chart_version": maia_namespace_chart_version,
        "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
        "serviceType": cluster_config["ssh_port_type"],
        "users": users,
        "orthanc": {"port": orthanc_ssh_port},
        "metallbSharedIp": cluster_config.get("metallb_shared_ip", False),
        "metallbIpPool": cluster_config.get("metallb_ip_pool", False),
        "loadBalancerIp": cluster_config.get("maia_metallb_ip", False),
        "storageClass": cluster_config["storage_class"],
    }

    if cluster_config["shared_storage_class"] == "local-path":
        maia_namespace_values["pvc"]["access_mode"] = "ReadWriteOnce"

    if namespace_config.get("ip_whitelist", None) and cluster_config["ssh_port_type"] == "LoadBalancer":
        maia_namespace_values["ipWhitelist"] = namespace_config["ip_whitelist"]

    if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True" and maia_namespace_chart_type == "git_repo":
        raise ValueError("ARGOCD_DISABLED is set to True and maia_namespace_chart_type is set to git_repo, which is not allowed")

    if maia_namespace_chart_type == "helm_repo":
        if "MAIA_PRIVATE_REGISTRY_" + namespace in os.environ:
            repo_url = os.environ["MAIA_PRIVATE_REGISTRY_" + namespace]
        else:
            repo_url = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        maia_namespace_values["repo_url"] = repo_url
        maia_namespace_values["chart_name"] = "maia-namespace"
    elif maia_namespace_chart_type == "git_repo":
        maia_namespace_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
        maia_namespace_values["path"] = "charts/maia-namespace"

    if "imagePullSecrets" in os.environ:
        maia_namespace_values["dockerRegistrySecret"] = {
            "enabled": True,
            "dockerRegistrySecretName": os.environ["imagePullSecrets"],
            "dockerRegistrySecret": encode_docker_registry_secret(
                os.environ["registry_server"], os.environ["registry_username"], os.environ["registry_password"]
            ),
        }
    if "imagePullSecrets_" + namespace in os.environ:
        maia_namespace_values["dockerRegistrySecret"] = {
            "enabled": True,
            "dockerRegistrySecretName": os.environ["imagePullSecrets_" + namespace],
            "dockerRegistrySecret": encode_docker_registry_secret(
                os.environ["registry_server" + namespace],
                os.environ["registry_username" + namespace],
                os.environ["registry_password" + namespace],
            ),
        }

    if minio_configs:
        maia_namespace_values["minio"] = {
            "enabled": True,
            "inject_policies": True,
            "consoleDomain": "https://{}.{}/minio-console-{}".format(
                namespace_config["group_subdomain"], cluster_config["domain"], namespace_config["group_subdomain"]
            ),
            "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
            "storageClassName": cluster_config["storage_class"],
            "storageSize": "10Gi",
            "admin_group_ID": os.environ.get("admin_group_ID", "MAIA:admin"),
            "accessKey": minio_configs["access_key"],
            "secretKey": minio_configs["secret_key"],
            "clientId": os.environ["OIDC_RP_CLIENT_ID"],
            "clientSecret": os.environ["OIDC_RP_CLIENT_SECRET"],
            "openIdConfigUrl": os.environ["OIDC_ISSUER_URL"] + "/.well-known/openid-configuration",
            "consoleAccessKey": minio_configs["console_access_key"],
            "consoleSecretKey": minio_configs["console_secret_key"],
            "ingress": {
                "annotations": {},
                "host": "{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"]),
                "path": "minio-console-{}".format(namespace_config["group_subdomain"]),
                "port": 80,
                "serviceName": f"{namespace}-mlflow-mkg",
            },
        }

        if cluster_config.get("selfsigned", False):
            maia_namespace_values["minio"]["externalCA"] = {
                "name": "kubernetes-ca-minio",
            }

        if "nginx_cluster_issuer" in cluster_config:
            if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
                maia_namespace_values["minio"]["ingress"]["annotations"][
                    "cert-manager.io/cluster-issuer"
                ] = "kubernetes-ca-issuer"
            else:
                maia_namespace_values["minio"]["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config[
                    "nginx_cluster_issuer"
                ]
            maia_namespace_values["minio"]["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "10g"
            maia_namespace_values["minio"]["ingress"]["tlsSecretName"] = "{}.{}-tls".format(
                namespace_config["group_subdomain"], cluster_config["domain"]
            )
        if "traefik_resolver" in cluster_config:
            if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
                ...
            else:
                maia_namespace_values["minio"]["ingress"]["annotations"][
                    "traefik.ingress.kubernetes.io/router.tls.certresolver"
                ] = cluster_config["traefik_resolver"]
            maia_namespace_values["minio"]["ingress"]["annotations"][
                "traefik.ingress.kubernetes.io/router.entrypoints"
            ] = "websecure"
            maia_namespace_values["minio"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"

        if cluster_config["url_type"] == "subpath":
            maia_namespace_values["minio"]["consoleDomain"] = "https://{}/minio-console-{}".format(
                cluster_config["domain"], namespace_config["group_ID"].lower().replace("_", "-")
            )
            maia_namespace_values["minio"]["ingress"]["host"] = "{}".format(cluster_config["domain"])
            maia_namespace_values["minio"]["ingress"]["path"] = "minio-console-{}".format(
                namespace_config["group_ID"].lower().replace("_", "-")
            )

    if mlflow_configs:
        maia_namespace_values["mlflow"] = {
            "enabled": True,
            # "user": base64.b64decode(mlflow_configs["mlflow_user"]).decode("ascii"),
            "user": mlflow_configs["mlflow_user"],
            "password": mlflow_configs["mlflow_password"],
            # "password": base64.b64decode(mlflow_configs["mlflow_password"]).decode("ascii"),
        }

    enable_cifs = namespace_config.get("extra_configs", {}).get("enable_cifs", False)
    if enable_cifs and "CIFS_SERVER" in os.environ:
        maia_namespace_values["cifs"] = {
            "enabled": True,
            "encryption": {"publicKey": os.environ.get("CIFS_PUBLIC_KEY", "")},
        }  # base64 encoded}
    namespace_id = namespace_config["group_ID"].lower().replace("_", "-")
    Path(config_folder).joinpath(namespace_config["group_ID"], "maia_namespace_values").mkdir(parents=True, exist_ok=True)
    with open(
        Path(config_folder).joinpath(namespace_config["group_ID"], "maia_namespace_values", "namespace_values.yaml"), "w"
    ) as f:
        f.write(OmegaConf.to_yaml(maia_namespace_values))

    return {
        "namespace": maia_namespace_values["namespace"],
        "release": f"{namespace_id}-namespace",
        "chart": (
            maia_namespace_values["chart_name"] if maia_namespace_chart_type == "helm_repo" else maia_namespace_values["path"]
        ),
        "repo": maia_namespace_values["repo_url"],
        "version": maia_namespace_values["chart_version"],
        "values": str(
            Path(config_folder).joinpath(namespace_config["group_ID"], "maia_namespace_values", "namespace_values.yaml")
        ),
    }


def create_filebrowser_values(namespace_config, cluster_config, config_folder, mlflow_configs=None, mount_cifs=True):
    """
    Create and write configuration values for deploying the MAIA Filebrowser Helm chart.
    This function generates a dictionary of configuration values required to deploy the MAIA Filebrowser
    application in a Kubernetes namespace. It handles image configuration, environment variables, volume
    mounts, CIFS volume setup, and ingress settings for both NGINX and Traefik ingress controllers. The
    resulting configuration is written to a YAML file in the specified config folder.

    Parameters
    ----------
    namespace_config : dict
        Dictionary containing namespace-specific configuration, including group ID, subdomain, and users.
    cluster_config : dict
        Dictionary containing cluster-specific configuration, such as docker server, image pull secrets,
        domain, and optional ingress settings.
    config_folder : str or Path
        Path to the folder where the generated configuration YAML file will be saved.
    mlflow_configs : dict, optional
        Optional dictionary containing MLflow configuration, specifically the base64-encoded
        'mlflow_password'. If not provided, a new human-memorable password is generated.

    Returns
    -------
    dict
        A dictionary containing:
            - 'namespace': The Kubernetes namespace for deployment.
            - 'release': The Helm release name.
            - 'chart': The Helm chart name.
            - 'repo': The Helm chart repository URL.
            - 'version': The Helm chart version.
            - 'values': Path to the generated YAML values file.

    Notes
    -----
    - The function expects certain helper functions and environment variables to be available, such as
      `generate_human_memorable_password`, `convert_username_to_jupyterhub_username`, and `OmegaConf`.
    - The CIFS server address is read from the 'CIFS_SERVER' environment variable.
    """

    namespace_id = namespace_config["group_ID"].lower().replace("_", "-")

    maia_filebrowser_values = {
        "chart_version": maia_filebrowser_chart_version,
        "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
    }

    default_registry = os.environ.get("MAIA_REGISTRY", "ghcr.io/minnelab")
    maia_filebrowser_values["image"] = {
        "repository": f"{default_registry}/maia-filebrowser",
        "tag": maia_filebrowser_image_version,
    }

    if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True" and maia_filebrowser_chart_type == "git_repo":
        raise ValueError("ARGOCD_DISABLED is set to True and maia_namespace_chart_type is set to git_repo, which is not allowed")

    if maia_filebrowser_chart_type == "helm_repo":
        maia_filebrowser_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        maia_filebrowser_values["chart_name"] = "maia-filebrowser"
    elif maia_filebrowser_chart_type == "git_repo":
        maia_filebrowser_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
        maia_filebrowser_values["path"] = "charts/maia-filebrowser"

    # maia_filebrowser_values["imagePullSecrets"] = [{"name": os.environ["imagePullSecrets"]}]
    if mlflow_configs is None:
        pw = generate_human_memorable_password(16)
        username = "maia-admin"
    else:
        pw = base64.b64decode(mlflow_configs["mlflow_password"]).decode("ascii")
        username = base64.b64decode(mlflow_configs["mlflow_user"]).decode("ascii")
    maia_filebrowser_values["env"] = [
        {"name": "RUN_FILEBROWSER", "value": "True"},
        {"name": "n_users", "value": "1"},
        {"name": "user", "value": username},
        {"name": "password", "value": pw},
        {"name": "FILEBROWSER_PATH", "value": "/filebrowser-{}".format(namespace_id)},
    ]

    maia_filebrowser_values["volumeMounts"] = [
        {
            "name": "db-volume",
            "mountPath": "/database",
        }
    ]
    maia_filebrowser_values["volumes"] = [
        {
            "name": "db-volume",
            "persistentVolumeClaim": {
                "claimName": f"{namespace_id}-filebrowser-maia-filebrowser-pvc",
            },
        }
    ]
    maia_filebrowser_values["volumeMounts"].append({"name": "shared-volume", "mountPath": "/home/shared"})
    for user in namespace_config["users"]:
        maia_filebrowser_values["volumeMounts"].append(
            {"name": "claim-" + convert_username_to_jupyterhub_username(user), "mountPath": "/home/" + user}
        )

    cifs_user = convert_username_to_jupyterhub_username(namespace_config["users"][0])

    maia_filebrowser_values["volumes"].append(
        {
            "name": "shared-volume",
            "persistentVolumeClaim": {
                "claimName": "shared",
            },
        }
    )

    for user in namespace_config["users"]:
        maia_filebrowser_values["volumes"].append(
            {
                "name": "claim-" + convert_username_to_jupyterhub_username(user),
                "persistentVolumeClaim": {
                    "claimName": "claim-" + convert_username_to_jupyterhub_username(user),
                },
            }
        )

    if mount_cifs:
        maia_filebrowser_values["volumes"].append(
            {
                "name": "cifs",
                "flexVolume": {
                    "driver": "fstab/cifs",
                    "fsType": "cifs",
                    "secretRef": {"name": cifs_user + "-cifs"},
                    "options": {
                        "mountOptions": "dir_mode=0777,file_mode=0777,iocharset=utf8,noperm,nounix,rw",
                        "networkPath": os.environ.get("CIFS_SERVER", "N/A"),
                    },
                },
            }
        )
        maia_filebrowser_values["volumeMounts"].append({"name": "cifs", "mountPath": "/home/cifs"})
    maia_filebrowser_values["ingress"] = {
        "enabled": True,
        "annotations": {},
        "hosts": [
            {
                "host": "drive.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"]),
                "paths": [{"path": f"/filebrowser-{namespace_id}", "pathType": "ImplementationSpecific"}],
            }
        ],
        "tls": [{"hosts": ["drive.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"])]}],
    }
    if "nginx_cluster_issuer" in cluster_config:
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            maia_filebrowser_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            maia_filebrowser_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config[
                "nginx_cluster_issuer"
            ]
        maia_filebrowser_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "10g"
        maia_filebrowser_values["ingress"]["tls"][0]["secretName"] = "{}.{}-tls".format(
            namespace_config["group_subdomain"], cluster_config["domain"]
        )
    if "traefik_resolver" in cluster_config:
        maia_filebrowser_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        maia_filebrowser_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            ...
        else:
            maia_filebrowser_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config["traefik_resolver"]
            )

    maia_filebrowser_values["storageClass"] = cluster_config["storage_class"]
    Path(config_folder).joinpath(namespace_config["group_ID"], "maia_filebrowser_values").mkdir(parents=True, exist_ok=True)
    with open(
        Path(config_folder).joinpath(namespace_config["group_ID"], "maia_filebrowser_values", "maia_filebrowser_values.yaml"), "w"
    ) as f:
        f.write(OmegaConf.to_yaml(maia_filebrowser_values))

    return {
        "namespace": maia_filebrowser_values["namespace"],
        "release": f"{namespace_id}-filebrowser",
        "chart": (
            maia_filebrowser_values["chart_name"]
            if maia_filebrowser_chart_type == "helm_repo"
            else maia_filebrowser_values["path"]
        ),
        "repo": maia_filebrowser_values["repo_url"],
        "version": maia_filebrowser_values["chart_version"],
        "values": str(
            Path(config_folder).joinpath(namespace_config["group_ID"], "maia_filebrowser_values", "maia_filebrowser_values.yaml")
        ),
    }


def create_nvflare_dashboard_values(namespace_config, cluster_config, config_folder):
    """
    Create and write configuration values for deploying the MAIA NVFlare Dashboard Helm chart.
    This function generates a dictionary of configuration values required to deploy the MAIA NVFlare Dashboard
    application in a Kubernetes namespace. It handles image configuration, environment variables, volume
    mounts, CIFS volume setup, and ingress settings for both NGINX and Traefik ingress controllers. The
    resulting configuration is written to a YAML file in the specified config folder.
    """
    namespace_id = namespace_config["group_ID"].lower().replace("_", "-")
    maia_nvflare_dashboard_values = {
        "chart_version": maia_nvflare_dashboard_chart_version,
        "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
    }
    default_registry = os.environ.get("MAIA_REGISTRY", "ghcr.io/minnelab")
    maia_nvflare_dashboard_values["image"] = {
        "repository": f"{default_registry}/maia-nvflare-dashboard",
        "tag": maia_nvflare_dashboard_image_version,
    }
    if (
        "ARGOCD_DISABLED" in os.environ
        and os.environ["ARGOCD_DISABLED"] == "True"
        and maia_nvflare_dashboard_chart_type == "git_repo"
    ):
        raise ValueError(
            "ARGOCD_DISABLED is set to True and maia_nvflare_dashboard_chart_type is set to git_repo, which is not allowed"
        )
    if maia_nvflare_dashboard_chart_type == "helm_repo":
        maia_nvflare_dashboard_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        maia_nvflare_dashboard_values["chart_name"] = "maia-nvflare-dashboard"
    elif maia_nvflare_dashboard_chart_type == "git_repo":
        maia_nvflare_dashboard_values["repo_url"] = os.environ.get(
            "MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git"
        )
        maia_nvflare_dashboard_values["path"] = "charts/maia-nvflare-dashboard"

    admin_username, admin_password = generate_nvflare_dashboard_configs(namespace_config["group_ID"], namespace_config)
    maia_nvflare_dashboard_values["env"] = [
        {"name": "ADMIN_USERNAME", "value": admin_username},
        {"name": "ADMIN_PASSWORD", "value": admin_password},
        {"name": "NVFL_CREDENTIAL", "value": f"{admin_username}:{admin_password}"},
        #{"name": "INGRESS_PATH", "value": "/nvflare-{}".format(namespace_id)},
    ]
    maia_nvflare_dashboard_values["ingress"] = {
        "enabled": True,
        "annotations": {},
        "hosts": [
            {
                "host": "nvflare.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"]),
                "paths": [{"path": "/", "pathType": "ImplementationSpecific"}],
            }
        ],
        "tls": [{"hosts": ["nvflare.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"])]}],
    }
    if "nginx_cluster_issuer" in cluster_config:
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            maia_nvflare_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            maia_nvflare_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config[
                "nginx_cluster_issuer"
            ]
        maia_nvflare_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "10g"
        maia_nvflare_dashboard_values["ingress"]["tls"][0]["secretName"] = "{}.{}-tls".format(
            namespace_config["group_subdomain"], cluster_config["domain"]
        )
    if "traefik_resolver" in cluster_config:
        maia_nvflare_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        maia_nvflare_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config and cluster_config["selfsigned"]:
            ...
        else:
            maia_nvflare_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config["traefik_resolver"]
            )

    Path(config_folder).joinpath(namespace_config["group_ID"], "maia_nvflare_dashboard_values").mkdir(parents=True, exist_ok=True)
    with open(
        Path(config_folder).joinpath(
            namespace_config["group_ID"], "maia_nvflare_dashboard_values", "maia_nvflare_dashboard_values.yaml"
        ),
        "w",
    ) as f:
        f.write(OmegaConf.to_yaml(maia_nvflare_dashboard_values))

    return {
        "namespace": maia_nvflare_dashboard_values["namespace"],
        "release": f"{namespace_id}-nvflare-dashboard",
        "chart": (
            maia_nvflare_dashboard_values["chart_name"]
            if maia_nvflare_dashboard_chart_type == "helm_repo"
            else maia_nvflare_dashboard_values["path"]
        ),
        "repo": maia_nvflare_dashboard_values["repo_url"],
        "version": maia_nvflare_dashboard_values["chart_version"],
        "values": str(
            Path(config_folder).joinpath(
                namespace_config["group_ID"], "maia_nvflare_dashboard_values", "maia_nvflare_dashboard_values.yaml"
            )
        ),
    }
