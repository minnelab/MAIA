from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
from pathlib import Path
from secrets import token_urlsafe
import requests
from loguru import logger
import yaml
from kubernetes import client, config
from omegaconf import OmegaConf
from pyhelm3 import Client

from MAIA.maia_fn import (
    convert_username_to_jupyterhub_username,
    encode_docker_registry_secret,
    generate_human_memorable_password,
    get_ssh_port_dict,
    get_ssh_ports,
)

from MAIA.versions import (
    define_maia_admin_versions,
    define_maia_core_versions,
    define_maia_project_versions,
    define_docker_image_versions,
)

maia_namespace_chart_version = define_maia_project_versions()["maia_namespace_chart_version"]
maia_namespace_chart_type = define_maia_project_versions()["maia_namespace_chart_type"]
maia_workspace_notebook_ssh_addons_image_version = define_docker_image_versions()["maia-workspace-notebook-ssh-addons"]
maia_workspace_notebook_ssh_addons_image_name = define_docker_image_versions()["maia-workspace-notebook-ssh-addons-image-name"]
maia_workspace_base_notebook_ssh_image_version = define_docker_image_versions()["maia-workspace-base-notebook-ssh"]
maia_workspace_base_notebook_ssh_image_name = define_docker_image_versions()["maia-workspace-base-notebook-ssh-image-name"]
maia_project_chart_version = define_maia_project_versions()["maia_project_chart_version"]
maia_filebrowser_image_version = define_docker_image_versions()["maia-filebrowser"]
maia_filebrowser_chart_version = define_maia_project_versions()["maia_filebrowser_chart_version"]
maia_filebrowser_chart_type = define_maia_project_versions()["maia_filebrowser_chart_type"]
maia_orthanc_image_version = define_docker_image_versions()["maia-orthanc"]
admin_toolkit_chart_version = define_maia_admin_versions()["admin_toolkit_chart_version"]
admin_toolkit_chart_type = define_maia_admin_versions()["admin_toolkit_chart_type"]
harbor_chart_version = define_maia_admin_versions()["harbor_chart_version"]
keycloak_chart_version = define_maia_admin_versions()["keycloak_chart_version"]
loginapp_chart_version = define_maia_core_versions()["loginapp_chart_version"]
minio_operator_chart_version = define_maia_core_versions()["minio_operator_chart_version"]
maia_dashboard_chart_version = define_maia_admin_versions()["maia_dashboard_chart_version"]
maia_dashboard_image_version = define_maia_admin_versions()["maia_dashboard_image_version"]
maia_dashboard_dev_tag_suffix = define_maia_admin_versions()["maia_dashboard_dev_tag_suffix"]
maia_dashboard_chart_type = define_maia_admin_versions()["maia_dashboard_chart_type"]
mysql_image = define_docker_image_versions()["mysql_image"]
mysql_image_version = define_docker_image_versions()["mysql"]


def generate_minio_configs(namespace):
    """
    Generate configuration settings for MinIO.

    Parameters
    ----------
    namespace : int or str
        The unique identifier for the project.

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
    secrets = v1.list_namespaced_secret(namespace=project_id.lower().replace("_", "-"))
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


def generate_mlflow_configs(namespace, config_dict=None):
    """
    Generate MLflow configuration dictionary with encoded user and password.

    Parameters
    ----------
    namespace : str
        The namespace to be encoded as the MLflow user.

    config_dict : dict, optional
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
    if config_dict:
        for key, value in config_dict.items():
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
    secrets = v1.list_namespaced_secret(namespace=project_id.lower().replace("_", "-"))
    for secret in secrets.items:

        if secret.metadata.name == project_id.lower().replace("_", "-"):
            for item in secret.data:

                decoded_value = base64.b64decode(secret.data[item]).decode("ascii")
                if item == "user":
                    mlflow_configs["mlflow_user"] = decoded_value
                if item == "password":
                    mlflow_configs["mlflow_password"] = decoded_value

    return mlflow_configs


def generate_mysql_configs(namespace):
    """
    Generate MySQL configuration dictionary.

    Parameters
    ----------
    namespace : str
        The namespace to be used as the MySQL user.

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
    deploy = v1.list_namespaced_pod(namespace=project_id.lower().replace("_", "-"))

    for deployment in deploy.items:
        if deployment.metadata.name.startswith(project_id.lower().replace("_", "-") + "-mysql-mkg"):
            envs = deployment.spec.containers[0].env
            for env in envs:
                if env.name == "MYSQL_USER":
                    mlflow_configs["mysql_user"] = env.value
                if env.name == "MYSQL_PASSWORD":
                    mlflow_configs["mysql_password"] = env.value

    return mlflow_configs


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

    if cluster_config.get("ip_whitelist", None) and cluster_config["ssh_port_type"] == "LoadBalancer":
        maia_namespace_values["ipWhitelist"] = cluster_config["ip_whitelist"]

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
            "consoleDomain": "https://{}.{}/minio-console".format(namespace_config["group_subdomain"], cluster_config["domain"]),
            "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
            "storageClassName": cluster_config["storage_class"],
            "storageSize": "10Gi",
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
                "path": "minio-console",
                "port": 80,
                "serviceName": f"{namespace}-mlflow-mkg",
            },
        }

        if cluster_config.get("selfsigned", False):
            maia_namespace_values["minio"]["externalCA"] = {
                "name": "kubernetes-ca-minio",
            }

        if "nginx_cluster_issuer" in cluster_config:
            maia_namespace_values["minio"]["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_config[
                "nginx_cluster_issuer"
            ]
            maia_namespace_values["minio"]["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "10g"
            maia_namespace_values["minio"]["ingress"]["tlsSecretName"] = "{}.{}-tls".format(
                namespace_config["group_subdomain"], cluster_config["domain"]
            )
        if "traefik_resolver" in cluster_config:
            maia_namespace_values["minio"]["ingress"]["annotations"][
                "traefik.ingress.kubernetes.io/router.entrypoints"
            ] = "websecure"
            maia_namespace_values["minio"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
            maia_namespace_values["minio"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config["traefik_resolver"]
            )
        if cluster_config["url_type"] == "subpath":
            maia_namespace_values["minio"]["consoleDomain"] = "https://{}/{}-minio-console".format(
                cluster_config["domain"], namespace_config["group_ID"].lower().replace("_", "-")
            )
            maia_namespace_values["minio"]["ingress"]["host"] = "{}".format(cluster_config["domain"])
            maia_namespace_values["minio"]["ingress"]["path"] = "{}-minio-console".format(
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

    maia_filebrowser_values["image"] = {"repository": "ghcr.io/minnelab/maia-filebrowser", "tag": maia_filebrowser_image_version}

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
                "paths": [{"path": "/", "pathType": "ImplementationSpecific"}],
            }
        ],
        "tls": [{"hosts": ["drive.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"])]}],
    }
    if "nginx_cluster_issuer" in cluster_config:
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
        "release": f"{namespace_id}-namespace",
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


def get_maia_toolkit_apps(group_id, password, argo_cd_host):
    """
    Retrieve and print information about a specific project and its associated applications from Argo CD.

    Parameters
    ----------
    group_id : str
        The group identifier used to construct project and application names.
    password : str
        The authorization token for accessing the Argo CD API.
    argo_cd_host : str
        The host URL of the Argo CD server.

    Returns
    -------
    list
        A list of dictionaries containing the name and version of each application.
        Each dictionary has the following keys:
        - name (str): The name of the application.
        - version (str): The version of the application.

    Example
    -------
    apps = get_maia_toolkit_apps("maia-core", "password", "http://localhost:8080")
    logger.info(f"Apps: {apps}")

    """

    response = requests.post(f"{argo_cd_host}/api/v1/session", json={"username": "admin", "password": password}, verify=False)
    if response.status_code == 200:
        cookies = {"argocd.token": response.json()["token"]}  # <- session cookie
    else:
        logger.error(f"Failed to get token: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return

    apps_url = f"{argo_cd_host}/api/v1/applications?projects={group_id}"
    resp = requests.get(apps_url, cookies=cookies, verify=False)

    apps = []
    if resp.status_code == 200:
        data = resp.json()
        if "items" in data and data["items"] is not None:
            app_names = [app["metadata"]["name"] for app in data.get("items", [])]
            logger.info(f"✅ Applications in project: {group_id}")
            for name in app_names:
                logger.info(f" - {name}")
                item = next((item for item in data.get("items", []) if item["metadata"]["name"] == name), None)
                apps.append(
                    {
                        "name": name,
                        "version": item["spec"]["source"]["targetRevision"],
                        "repo": item["spec"]["source"]["repoURL"],
                    }
                )
                if "chart" in item["spec"]["source"]:
                    apps[-1]["chart"] = item["spec"]["source"]["chart"]
                elif "path" in item["spec"]["source"]:
                    apps[-1]["path"] = item["spec"]["source"]["path"]
        return apps
    else:
        logger.error(f"❌ Failed to fetch apps: {resp.status_code}")
        logger.error(f"Response: {resp.text}")
        return []


async def install_maia_project(
    group_id, values_file, argo_cd_namespace, project_chart, project_repo=None, project_version=None, json_key_path=None
):
    """
    Installs or upgrades a MAIA project using the specified Helm chart and values file.

    Parameters
    ----------
    group_id : str
        The group ID for the project. This will be used as the release name.
    values_file : str
        Path to the YAML file containing the values for the Helm chart.
    argo_cd_namespace : str
        The namespace in which to install the project.
    project_chart : str
        The name of the Helm chart to use for the project.
    project_repo : str, optional
        The repository URL where the Helm chart is located. Defaults to None.
    project_version : str, optional
        The version of the Helm chart to use. Defaults to None.
    json_key_path : str, optional
        Path to the JSON key file for authentication with the Helm registry. Defaults to None.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If the values file does not exist.
    yaml.YAMLError
        If there is an error parsing the values file.
    Exception
        If there is an error during the installation or upgrade process.
    """
    client = Client(kubeconfig=os.environ["KUBECONFIG"])
    chart_name = group_id.lower().replace("_", "-")
    if chart_name[-1] == "-":
        chart_name = chart_name[:-1]
    if chart_name[0] == "-":
        chart_name = chart_name[1:]

    if not project_repo.startswith("http") and not Path(project_repo).exists() and not project_repo.startswith("git+"):
        chart = str("/tmp/" + project_chart + "-" + project_version + ".tgz")
        project_chart = "oci://" + project_repo + "/" + project_chart

        try:
            try:
                with open(json_key_path, "r") as f:
                    docker_credentials = json.load(f)
                    username = docker_credentials.get("username")
                    password = docker_credentials.get("password")
            except Exception:
                with open(json_key_path, "r") as f:
                    docker_credentials = f.read()
                    username = "_json_key"
                    password = docker_credentials
            logger.debug(f"helm registry login {project_repo} --insecure -u {username} --password-stdin")
            result = subprocess.run(
                ["helm", "registry", "login", project_repo, "--insecure", "-u", username, "--password-stdin"],
                input=password.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            logger.info("✅ Helm registry login successful.")
            logger.debug(result.stdout.decode())
        except subprocess.CalledProcessError as e:
            logger.error("❌ Helm registry login failed.")
            logger.error("STDOUT:", e.stdout.decode())
            logger.error("STDERR:", e.stderr.decode())
            await asyncio.sleep(1)
            return "Deployment failed: Helm registry login failed."
        subprocess.run(
            ["helm", "pull", project_chart, "-d", "/tmp", "--insecure-skip-tls-verify", "--version", project_version], check=True
        )
        subprocess.run(
            [
                "helm",
                "upgrade",
                "--install",
                chart_name,
                chart,
                "--namespace",
                argo_cd_namespace,
                "--values",
                str(values_file),
                "--wait",
            ],
            check=True,
        )
        await asyncio.sleep(1)
        return ""
    if Path(project_repo).exists():
        chart = await client.get_chart(project_repo, version=project_version)
    elif project_repo.startswith("git+"):
        ...
    elif not project_repo.startswith("http"):
        chart = await client.get_chart(project_chart, repo=project_repo, version=project_version, insecure=True)
    else:
        chart = await client.get_chart(project_chart, repo=project_repo, version=project_version)
    with open(values_file) as f:
        values = yaml.safe_load(f)

    if project_repo.startswith("git+"):
        subprocess.run(
            [
                "helm",
                "upgrade",
                "--install",
                chart_name,
                project_repo,
                "--namespace",
                argo_cd_namespace,
                "--values",
                str(values_file),
                "--wait",
            ],
            check=True,
        )
    else:
        revision = await client.install_or_upgrade_release(chart_name, chart, values, namespace=argo_cd_namespace, wait=True)
        logger.debug(revision.release.name, revision.release.namespace, revision.revision, str(revision.status))

    return ""


def create_maia_admin_toolkit_values(config_folder, project_id, cluster_config_dict):
    """
    Creates and writes the MAIA admin toolkit values to a YAML file.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder.
    project_id : str
        The project identifier.
    cluster_config_dict : dict
        Dictionary containing cluster configuration values.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values YAML file.
    """
    admin_group_id = os.environ["admin_group_ID"]

    admin_toolkit_values = {
        "namespace": "maia-admin-toolkit",
        "chart_version": admin_toolkit_chart_version,
    }

    if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True" and admin_toolkit_chart_type == "git_repo":
        raise ValueError("ARGOCD_DISABLED is set to True and core_toolkit_chart_type is set to git_repo, which is not allowed")

    if admin_toolkit_chart_type == "helm_repo":
        admin_toolkit_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        admin_toolkit_values["chart_name"] = "maia-admin-toolkit"
    elif admin_toolkit_chart_type == "git_repo":
        admin_toolkit_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
        admin_toolkit_values["path"] = "charts/maia-admin-toolkit"

    admin_toolkit_values.update(
        {
            "argocd": {
                "enabled": True,
                "argocd_namespace": "argocd",
                "argocd_domain": "argocd." + cluster_config_dict["domain"],
                "keycloak_issuer_url": "https://iam." + cluster_config_dict["domain"] + "/realms/maia",
                "keycloak_client_id": "maia",
                "keycloak_client_secret": os.environ["keycloak_client_secret"],
            },
            "admin_group_ID": admin_group_id,
            "harbor": {
                "enabled": True,
                "values": {"namespace": "harbor", "storageClassName": cluster_config_dict["storage_class"]},
            },
            "keycloak": {
                "enabled": True,
                "values": {"namespace": "keycloak", "storageClassName": cluster_config_dict["storage_class"]},
            },
            "minio": {
                "enabled": True,
                "namespace": "maia-dashboard",
                "adminAccessKey": "maia-admin",
                "adminSecretKey": os.environ["minio_admin_password"],
                "image": "quay.io/minio/minio:RELEASE.2025-04-08T15-41-24Z",
                "storageSize": "10Gi",
                "storageClassName": cluster_config_dict["storage_class"],
                "consoleDomain": "minio." + cluster_config_dict["domain"],
                "apiDomain": "minio-api." + cluster_config_dict["domain"],
                "rootAccessKey": "root",
                "rootSecretKey": os.environ["minio_root_password"],
                "openIdClientId": "maia",
                "openIdClientSecret": os.environ["keycloak_client_secret"],
                "openIdConfigUrl": "https://iam."
                + cluster_config_dict["domain"]
                + "/realms/maia/.well-known/openid-configuration",
                "ingress": {
                    "annotations": {},
                },
            },
        }
    )

    if "externalCA" in cluster_config_dict:
        admin_toolkit_values["minio"]["externalCA"] = {}
        admin_toolkit_values["minio"]["externalCA"]["name"] = cluster_config_dict["externalCA"]["name"]
        admin_toolkit_values["minio"]["externalCA"]["cert"] = open(Path(cluster_config_dict["externalCA"]["cert"])).read()
        admin_toolkit_values["argocd"]["rootCA"] = open(Path(cluster_config_dict["externalCA"]["cert"])).read()

    if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
        admin_toolkit_values["argocd"]["rootCA"] = open(Path(cluster_config_dict["rootCA"])).read()

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        admin_toolkit_values["minio"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        admin_toolkit_values["minio"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            admin_toolkit_values["minio"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
            admin_toolkit_values["certResolver"] = cluster_config_dict["traefik_resolver"]
    elif cluster_config_dict["ingress_class"] == "nginx":
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            admin_toolkit_values["minio"]["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            admin_toolkit_values["minio"]["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"
        admin_toolkit_values["minio"]["ingress"]["tlsSecretName"] = f"{project_id}-tls"
        admin_toolkit_values["minio"]["ingress"]["tlsSecretNameApi"] = f"{project_id}-tls-api"

    Path(config_folder).joinpath(project_id, "maia_admin_toolkit_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(project_id, "maia_admin_toolkit_values", "maia_admin_toolkit_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(admin_toolkit_values))

    return {
        "namespace": admin_toolkit_values["namespace"],
        "release": f"{project_id}-toolkit",
        "chart": admin_toolkit_values["chart_name"] if admin_toolkit_chart_type == "helm_repo" else admin_toolkit_values["path"],
        "repo": admin_toolkit_values["repo_url"],
        "version": admin_toolkit_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "maia_admin_toolkit_values", "maia_admin_toolkit_values.yaml")),
    }


def create_harbor_values(config_folder, project_id, cluster_config_dict):
    """
    Create and save Harbor values configuration for a given project and cluster configuration.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder where the Harbor values file will be saved.
    project_id : str
        The unique identifier for the project.
    cluster_config_dict : dict
        A dictionary containing cluster configuration details, including:
            - domain (str): The domain name for the Harbor registry.
            - ingress_class (str): The ingress class to be used (e.g., "maia-core-traefik", "nginx").
            - traefik_resolver (str, optional): The Traefik resolver to be used if ingress_class is "maia-core-traefik".

    Returns
    -------
    dict
        A dictionary containing the following keys:
        - namespace (str): The Kubernetes namespace for Harbor.
        - release (str): The release name for the Harbor Helm chart.
        - chart (str): The name of the Harbor Helm chart.
        - repo (str): The URL of the Harbor Helm chart repository.
        - version (str): The version of the Harbor Helm chart.
        - values (str): The path to the generated Harbor values YAML file.
    """
    domain = cluster_config_dict["domain"]
    harbor_values = {
        "namespace": "harbor",
        "repo_url": "https://helm.goharbor.io",
        "chart_name": "harbor",
        "chart_version": harbor_chart_version,
    }

    harbor_values.update(
        {
            "expose": {
                "type": "ingress",
                "tls": {"enabled": True},
                "ingress": {
                    "hosts": {"core": f"registry.{domain}"},
                    "annotations": {},
                    "controller": "default",
                    "className": cluster_config_dict["ingress_class"],
                },
            },
            "externalURL": f"https://registry.{domain}",
            "persistence": {
                "enabled": True,
                "resourcePolicy": "keep",
                "persistentVolumeClaim": {
                    "registry": {
                        "existingClaim": "pvc-harbor",
                        "subPath": "registry",
                        "storageClass": cluster_config_dict["storage_class"],
                        "accessMode": "ReadWriteMany",
                    },
                    "jobservice": {
                        "jobLog": {
                            "existingClaim": "pvc-harbor",
                            "subPath": "job_logs",
                            "storageClass": cluster_config_dict["storage_class"],
                            "accessMode": "ReadWriteMany",
                        }
                    },
                    "database": {
                        "existingClaim": "pvc-harbor",
                        "subPath": "database",
                        "storageClass": cluster_config_dict["storage_class"],
                        "accessMode": "ReadWriteMany",
                    },
                    "redis": {
                        "existingClaim": "pvc-harbor",
                        "subPath": "redis",
                        "storageClass": cluster_config_dict["storage_class"],
                        "accessMode": "ReadWriteMany",
                    },
                    "trivy": {
                        "existingClaim": "pvc-harbor",
                        "subPath": "trivy",
                        "storageClass": cluster_config_dict["storage_class"],
                        "accessMode": "ReadWriteMany",
                    },
                },
                "imageChartStorage": {"type": "filesystem"},
            },
            "database": {"internal": {"password": "harbor"}},
            "metrics": {
                "enabled": True,
                "core": {"path": "/metrics", "port": 8001},
                "registry": {"path": "/metrics", "port": 8001},
                "jobservice": {"path": "/metrics", "port": 8001},
                "exporter": {"path": "/metrics", "port": 8001},
            },
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        harbor_values["expose"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        harbor_values["expose"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        harbor_values["expose"]["tls"]["certSource"] = "none"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            harbor_values["expose"]["ingress"]["annotations"][
                "traefik.ingress.kubernetes.io/router.tls.certresolver"
            ] = "kubernetes-ca-issuer"
        else:
            harbor_values["expose"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
    elif cluster_config_dict["ingress_class"] == "nginx":
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            harbor_values["expose"]["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"

    Path(config_folder).joinpath(project_id, "harbor_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "harbor_values", "harbor_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(harbor_values))

    return {
        "namespace": harbor_values["namespace"],
        "release": f"{project_id}-harbor",
        "chart": harbor_values["chart_name"],
        "repo": harbor_values["repo_url"],
        "version": harbor_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "harbor_values", "harbor_values.yaml")),
    }


def create_keycloak_values(config_folder, project_id, cluster_config_dict):
    """
    Generates Keycloak Helm chart values and writes them to a YAML file.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder where the YAML file will be saved.
    project_id : str
        The project identifier used to create a unique namespace and release name.
    cluster_config_dict : dict
        A dictionary containing cluster configuration details such as domain, ingress class, and traefik resolver.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values YAML file.
    """
    keycloak_values = {
        "namespace": "keycloak",
        "repo_url": "https://charts.bitnami.com/bitnami",
        "chart_name": "keycloak",
        "chart_version": keycloak_chart_version,
    }

    keycloak_values.update(
        {
            "extraEnvVars": [
                {"name": "KEYCLOAK_EXTRA_ARGS", "value": "--import-realm"},
                {"name": "PROXY_ADDRESS_FORWARDING", "value": "true"},
                {"name": "KEYCLOAK_HOSTNAME", "value": "iam." + cluster_config_dict["domain"]},
            ],
            "proxy": "edge",
            "ingress": {
                "enabled": True,
                "tls": True,
                "ingressClassName": cluster_config_dict["ingress_class"],
                "hostname": "iam." + cluster_config_dict["domain"],
                "annotations": {},
            },
            "auth": {
                "adminPassword": cluster_config_dict["keycloak_admin_password"],
            },
            "extraVolumeMounts": [
                {
                    "name": "keycloak-import",
                    "mountPath": "/opt/bitnami/keycloak/data/import",
                },
                {"name": "keycloak-themes", "mountPath": "/opt/bitnami/keycloak/themes"},
            ],
            "extraVolumes": [
                {"name": "keycloak-import", "configMap": {"name": "maia-realm-import"}},
                {"name": "keycloak-themes", "persistentVolumeClaim": {"claimName": "pvc-keycloak-themes"}},
            ],
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        keycloak_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        keycloak_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            keycloak_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
    elif cluster_config_dict["ingress_class"] == "nginx":
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            keycloak_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            keycloak_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"

    Path(config_folder).joinpath(project_id, "keycloak_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "keycloak_values", "keycloak_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(keycloak_values))

    return {
        "namespace": keycloak_values["namespace"],
        "release": f"{project_id}-keycloak",
        "chart": keycloak_values["chart_name"],
        "repo": keycloak_values["repo_url"],
        "version": keycloak_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "keycloak_values", "keycloak_values.yaml")),
    }


def create_loginapp_values(config_folder, project_id, cluster_config_dict):
    """
    Creates and writes the loginapp values configuration file for a given project and cluster configuration.

    Parameters
    ----------
    config_folder : str
        The base directory where the configuration files will be stored.
    project_id : str
        The unique identifier for the project.
    cluster_config_dict : dict
        A dictionary containing cluster configuration details, including:
            - keycloak.client_secret (str): The client secret for Keycloak.
            - domain (str): The domain name for the cluster.
            - ingress_class (str): The ingress class to be used (e.g., "maia-core-traefik" or "nginx").
            - traefik_resolver (str, optional): The Traefik resolver to be used if ingress_class is "maia-core-traefik".

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values file.

    Raises
    ------
    KeyError
        If required keys are missing from the cluster_config_dict.
    OSError
        If there is an error creating directories or writing the configuration file.
    """
    loginapp_values = {
        "namespace": "authentication",
        "repo_url": "https://storage.googleapis.com/loginapp-releases/charts/",
        "chart_name": "loginapp",
        "chart_version": loginapp_chart_version,
    }

    secret = token_urlsafe(16).replace("-", "_")
    client_id = "maia"
    client_secret = os.environ["keycloak_client_secret"]
    issuer_url = "https://iam." + cluster_config_dict["domain"] + "/realms/maia"
    cluster_server_address = "https://" + cluster_config_dict["domain"] + ":16443"

    ca_file = None
    if "rootCA" in cluster_config_dict:
        ca_text = Path(cluster_config_dict["rootCA"]).read_text()
        ca_file = ca_text  # .base64.b64encode(ca_text.encode()).decode()

    loginapp_values.update(
        {
            "env": {"LOGINAPP_NAME": "MAIA Login"},
            "configOverwrites": {"oidc": {"scopes": ["openid", "profile", "email"]}, "service": {"type": "ClusterIP"}},
            "ingress": {
                "enabled": True,
                "annotations": {},
                "tls": [{"hosts": ["login." + cluster_config_dict["domain"]]}],
                "hosts": [{"host": "login." + cluster_config_dict["domain"], "paths": [{"path": "/", "pathType": "Prefix"}]}],
            },
            "config": {
                "tls": {"enabled": False},
                "issuerInsecureSkipVerify": True,
                "refreshToken": True,
                "clientRedirectURL": "https://login." + cluster_config_dict["domain"] + "/callback",
                "secret": secret,
                "clientID": client_id,
                "clientSecret": client_secret,
                "issuerURL": issuer_url,
                "clusters": [
                    {
                        "server": cluster_server_address,
                        "name": "MAIA",
                        "insecure-skip-tls-verify": True,
                        "certificate-authority": ca_file,
                    }
                ],
            },
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        loginapp_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        loginapp_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            loginapp_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
    elif cluster_config_dict["ingress_class"] == "nginx":
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            loginapp_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            loginapp_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"
        loginapp_values["ingress"]["tls"][0]["secretName"] = "loginapp." + cluster_config_dict["domain"]

    Path(config_folder).joinpath(project_id, "loginapp_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "loginapp_values", "loginapp_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(loginapp_values))

    return {
        "namespace": loginapp_values["namespace"],
        "release": f"{project_id}-loginapp",
        "chart": loginapp_values["chart_name"],
        "repo": loginapp_values["repo_url"],
        "version": loginapp_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "loginapp_values", "loginapp_values.yaml")),
    }


def create_minio_operator_values(config_folder, project_id):
    """
    Creates and writes MinIO operator values to a YAML file and returns a dictionary with deployment details.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder.
    project_id : str
        The unique identifier for the project.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated YAML values file.
    """
    minio_operator_values = {
        "namespace": "minio-operator",
        "repo_url": "https://operator.min.io",
        "chart_name": "operator",
        "chart_version": minio_operator_chart_version,
    }

    Path(config_folder).joinpath(project_id, "minio_operator_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "minio_operator_values", "minio_operator_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(minio_operator_values))

    return {
        "namespace": minio_operator_values["namespace"],
        "release": f"{project_id}-minio-operator",
        "chart": minio_operator_values["chart_name"],
        "repo": minio_operator_values["repo_url"],
        "version": minio_operator_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "minio_operator_values", "minio_operator_values.yaml")),
    }


def create_maia_dashboard_values(config_folder, project_id, cluster_config_dict):
    """
    Create MAIA dashboard values for Helm chart deployment.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder.
    project_id : str
        The project identifier.
    cluster_config_dict : dict
        Dictionary containing cluster configuration details.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values YAML file.
    """
    maia_dashboard_values = {
        "namespace": "maia-dashboard",
        "chart_version": maia_dashboard_chart_version,
    }

    if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True" and maia_dashboard_chart_type == "git_repo":
        raise ValueError("ARGOCD_DISABLED is set to True and maia_dashboard_chart_type is set to git_repo, which is not allowed")

    if maia_dashboard_chart_type == "helm_repo":
        maia_dashboard_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        maia_dashboard_values["chart_name"] = "maia-dashboard"
    elif maia_dashboard_chart_type == "git_repo":
        maia_dashboard_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
        maia_dashboard_values["path"] = "charts/maia-dashboard"

    maia_dashboard_values.update(
        {
            "ingress": {
                "enabled": True,
                "annotations": {},
                "hosts": [
                    {
                        "host": "maia." + cluster_config_dict["domain"],
                        "paths": [
                            {"path": "/", "pathType": "ImplementationSpecific"},
                            {"path": "/maia-api/", "pathType": "ImplementationSpecific"},
                            {"path": "/maia/", "pathType": "ImplementationSpecific"},
                        ],
                    }
                ],
                "tls": [{"hosts": ["maia." + cluster_config_dict["domain"]]}],
            },
            "env": [
                {"name": "DEBUG", "value": "False"},
                {"name": "SERVER", "value": "maia." + cluster_config_dict["domain"]},
                {"name": "LOCAL_DB_PATH", "value": "/etc/MAIA-Dashboard/db"},
            ],
            "storageClass": cluster_config_dict["storage_class"],
            "image": {"repository": "ghcr.io/minnelab/maia-dashboard", "tag": maia_dashboard_image_version},
            "dashboard": {"local_config_path": "/mnt/dashboard-config"},
            "mysql": {"enabled": True, "image": mysql_image, "tag": mysql_image_version},
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
    elif cluster_config_dict["ingress_class"] == "nginx":
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "8g"
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-read-timeout"] = "300"
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-send-timeout"] = "300"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            maia_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            maia_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"
        maia_dashboard_values["ingress"]["tls"][0]["secretName"] = cluster_config_dict["domain"]

    # Authentication
    maia_dashboard_values["env"].extend(
        [
            {"name": "OIDC_RP_CLIENT_ID", "value": "maia"},
            {"name": "OIDC_RP_CLIENT_SECRET", "value": os.environ["keycloak_client_secret"]},
            {"name": "OIDC_SERVER_URL", "value": "https://iam." + cluster_config_dict["domain"]},
            {"name": "OIDC_REALM_NAME", "value": "maia"},
            {"name": "OIDC_USERNAME", "value": "admin"},
            {"name": "OIDC_ISSUER_URL", "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia"},
            {
                "name": "OIDC_OP_AUTHORIZATION_ENDPOINT",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/auth",
            },
            {
                "name": "OIDC_OP_TOKEN_ENDPOINT",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/token",
            },
            {
                "name": "OIDC_OP_USER_ENDPOINT",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/userinfo",
            },
            {
                "name": "OIDC_OP_JWKS_ENDPOINT",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/certs",
            },
            {"name": "OIDC_RP_SIGN_ALGO", "value": "RS256"},
            {"name": "OIDC_RP_SCOPES", "value": "openid email profile"},
        ]
    )

    # Cluster Access
    maia_dashboard_values["clusters"] = [
        {
            "api": "https://mgmt." + cluster_config_dict["domain"] + "/k8s/clusters/local",
            "cluster_name": cluster_config_dict["cluster_name"],
            "ssh_hostname": (
                cluster_config_dict["ssh_hostname"] if "ssh_hostname" in cluster_config_dict else cluster_config_dict["domain"]
            ),
            "maia_dashboard": {"enabled": True, "token": cluster_config_dict["rancher_token"]},
        }
    ]

    maia_dashboard_values["env"].extend(
        [
            {"name": "ARGOCD_CLUSTER", "value": cluster_config_dict["cluster_name"]},
        ]
    )

    # Access Project Pages

    maia_dashboard_values["env"].extend(
        [
            {"name": "CLUSTER_CONFIG_PATH", "value": "/mnt/dashboard-config"},
        ]
    )

    # Access KubeFlow and XNAT
    maia_dashboard_values["env"].extend(
        [
            {"name": "GLOBAL_NAMESPACES", "value": "xnat,istio-system"},
        ]
    )

    # Self Signed Certificate
    if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
        maia_dashboard_values["env"].extend(
            [
                {"name": "OIDC_CA_BUNDLE", "value": "/mnt/dashboard-config/ca.crt"},
            ]
        )

        maia_dashboard_values["ca.crt"] = open(Path(cluster_config_dict["rootCA"])).read()

        maia_dashboard_values["clusters"][0]["selfsigned"] = True
    elif "staging_certificates" in cluster_config_dict and cluster_config_dict["staging_certificates"]:
        maia_dashboard_values["env"].extend(
            [
                {"name": "OIDC_CA_BUNDLE", "value": "/mnt/dashboard-config/ca.crt"},
            ]
        )
        maia_dashboard_values["ca.crt"] = open(Path(cluster_config_dict["externalCA"]["cert"])).read()
        maia_dashboard_values["clusters"][0]["selfsigned"] = True
    else:
        if "traefik_resolver" in cluster_config_dict:
            maia_dashboard_values["clusters"][0]["traefik_resolver"] = cluster_config_dict["traefik_resolver"]
        elif "nginx_cluster_issuer" in cluster_config_dict:
            maia_dashboard_values["clusters"][0]["nginx_cluster_issuer"] = cluster_config_dict["nginx_cluster_issuer"]

    # Deploy with ArgoCD

    maia_dashboard_values["clusters"][0].update(
        {
            "ssh_port_type": cluster_config_dict["ssh_port_type"],
            "port_range": cluster_config_dict["port_range"],
            "shared_storage_class": cluster_config_dict["shared_storage_class"],
            "storage_class": cluster_config_dict["storage_class"],
            "domain": cluster_config_dict["domain"],
            "url_type": cluster_config_dict["url_type"],
            "argocd_destination_cluster_address": (
                cluster_config_dict["argocd_destination_cluster_address"]
                if "argocd_destination_cluster_address" in cluster_config_dict
                else "https://kubernetes.default.svc"
            ),
        }
    )
    if "metallb_ip_pool" in cluster_config_dict:
        maia_dashboard_values["clusters"][0]["metallb_ip_pool"] = cluster_config_dict["metallb_ip_pool"]
    if "maia_metallb_ip" in cluster_config_dict:
        maia_dashboard_values["clusters"][0]["maia_metallb_ip"] = cluster_config_dict["maia_metallb_ip"]
    if "metallb_shared_ip" in cluster_config_dict:
        maia_dashboard_values["clusters"][0]["metallb_shared_ip"] = cluster_config_dict["metallb_shared_ip"]

    maia_dashboard_values["env"].extend(
        [
            {"name": "maia_project_chart", "value": os.environ.get("maia_project_chart", "maia-project")},
            {"name": "maia_project_repo", "value": os.environ.get("maia_project_repo", "https://minnelab.github.io/MAIA/")},
            {"name": "maia_project_version", "value": os.environ.get("maia_project_version", maia_project_chart_version)},
            {"name": "ADMIN_GROUP", "value": cluster_config_dict.get("admin_group", "admin")},
            {"name": "USERS_GROUP", "value": cluster_config_dict.get("users_group", "users")},
            {"name": "argocd_namespace", "value": "argocd"},
            {"name": "ARGOCD_SERVER", "value": "https://argocd." + cluster_config_dict["domain"]},
        ]
    )

    # Dev Branch
    if os.environ.get("DEV_BRANCH") is not None:
        maia_dashboard_values["env"].extend(
            [
                {"name": "DEV_BRANCH", "value": os.environ["DEV_BRANCH"]},
            ]
        )
    if os.environ.get("GIT_EMAIL") is not None:
        maia_dashboard_values["env"].extend(
            [
                {"name": "GIT_EMAIL", "value": os.environ["GIT_EMAIL"]},
            ]
        )
    if os.environ.get("GIT_NAME") is not None:
        maia_dashboard_values["env"].extend(
            [
                {"name": "GIT_NAME", "value": os.environ["GIT_NAME"]},
            ]
        )
    if os.environ.get("GPG_KEY") is not None:
        maia_dashboard_values["env"].extend(
            [
                {"name": "GPG_KEY", "value": "/var/keys/gpg.key"},
            ]
        )
        with open(os.environ["GPG_KEY"], "r") as f:
            maia_dashboard_values["gpg_key"] = f.read()

    if (
        os.environ.get("DEV_BRANCH") is not None
        or os.environ.get("GIT_EMAIL") is not None
        or os.environ.get("GIT_NAME") is not None
        or os.environ.get("GPG_KEY") is not None
    ):
        maia_dashboard_values["image"]["tag"] = maia_dashboard_image_version + maia_dashboard_dev_tag_suffix
        maia_dashboard_values["image"]["repository"] = "ghcr.io/minnelab/maia-dashboard-dev"

    Path(config_folder).joinpath(project_id, "maia_dashboard_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "maia_dashboard_values", "maia_dashboard_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(maia_dashboard_values))

    return {
        "namespace": maia_dashboard_values["namespace"],
        "release": f"{project_id}-dashboard",
        "chart": (
            maia_dashboard_values["chart_name"] if maia_dashboard_chart_type == "helm_repo" else maia_dashboard_values["path"]
        ),
        "repo": maia_dashboard_values["repo_url"],
        "version": maia_dashboard_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "maia_dashboard_values", "maia_dashboard_values.yaml")),
    }


def create_maia_dashboard_values_old(config_folder, project_id, cluster_config_dict):
    """
    Create MAIA dashboard values for Helm chart deployment.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder.
    project_id : str
        The project identifier.
    cluster_config_dict : dict
        Dictionary containing cluster configuration details.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values YAML file.
    """

    maia_dashboard_values = {}
    maia_dashboard_values.update(
        {
            "image": {"pullPolicy": "IfNotPresent"},
            "ingress": {
                "className": cluster_config_dict["ingress_class"],
            },
            "gpuList": cluster_config_dict["gpu_list"] if "gpu_list" in cluster_config_dict else [],
            "dashboard": {
                "local_db_path": "/etc/MAIA-Dashboard/db",
            },
            "clusters": [
                {
                    "services": {
                        "argocd": "https://argocd." + cluster_config_dict["domain"],
                        "dashboard": "https://dashboard." + cluster_config_dict["domain"],
                        "traefik": "https://traefik." + cluster_config_dict["domain"],
                        "grafana": "https://grafana." + cluster_config_dict["domain"],
                        "keycloak": "https://iam." + cluster_config_dict["domain"] + "/admin/maia/console/",
                        "login": "https://login." + cluster_config_dict["domain"],
                        "rancher": "https://mgmt." + cluster_config_dict["domain"],
                        "registry": "https://registry." + cluster_config_dict["domain"],
                        "minio": "https://minio." + cluster_config_dict["domain"],
                    },
                }
            ],
            "name": "maia-dashboard",
        }
    )
    if (
        "MAIA_PRIVATE_REGISTRY" in os.environ
        and "registry_username" in os.environ
        and "registry_password" in os.environ
        and "registry_email" in os.environ
    ):
        maia_dashboard_values["image"]["repository"] = os.environ["MAIA_PRIVATE_REGISTRY"] + "/maia-dashboard"
        maia_dashboard_values["imagePullSecrets"] = [{"name": os.environ["MAIA_PRIVATE_REGISTRY"].replace("/", "-")}]
        maia_dashboard_values["dockerRegistrySecretName"] = os.environ["MAIA_PRIVATE_REGISTRY"].replace("/", "-")
        maia_dashboard_values["dockerRegistryUsername"] = os.environ["registry_username"]
        maia_dashboard_values["dockerRegistryPassword"] = os.environ["registry_password"]
        maia_dashboard_values["dockerRegistryEmail"] = os.environ["registry_email"]
        maia_dashboard_values["dockerRegistryServer"] = os.environ["MAIA_PRIVATE_REGISTRY"]
    else:
        maia_dashboard_values["image"]["repository"] = "ghcr.io/minnelab/maia-dashboard"
        maia_dashboard_values["imagePullSecrets"] = []

    # maia_dashboard_values["clusters"] = [cluster_config_dict]

    # Variables for Namespace Deployment
    maia_dashboard_values["clusters"][0]["bucket_name"] = cluster_config_dict["bucket_name"]
    maia_dashboard_values["clusters"][0]["registry_server"] = "ghcr.io/minnelab"

    if "projects" in cluster_config_dict:
        for project in cluster_config_dict["projects"]:
            maia_dashboard_values["clusters"][0][project + "-cluster-config"] = cluster_config_dict[project + "-cluster-config"]
    maia_dashboard_values["clusters"][0]
    debug = False

    if debug:
        ...
    else:

        if "mysql_dashboard_password" in os.environ:
            db_password = os.environ["mysql_dashboard_password"]
        else:
            db_password = generate_human_memorable_password()
        maia_dashboard_values["dashboard"]["local_config_path"] = "/mnt/dashboard-config"
        cifs_server = ""
        maia_dashboard_values["env"] = [
            {"name": "DEBUG", "value": "False"},
            {"name": "DB_ENGINE", "value": "mysql"},
            {"name": "DB_NAME", "value": "mysql"},
            {"name": "DB_HOST", "value": "maia-admin-maia-dashboard-mysql"},
            {"name": "DB_PORT", "value": "3306"},
            {"name": "DB_USERNAME", "value": "maia-admin"},
            {"name": "DB_PASS", "value": db_password},
        ]

        maia_dashboard_values["mysql"] = {
            "enabled": True,
            "mysqlRootPassword": db_password,
            "mysqlUser": "maia-admin",
            "mysqlPassword": db_password,
            "mysqlDatabase": "mysql",
        }

    if "CIFS_SERVER" in os.environ:
        cifs_server = os.environ["CIFS_SERVER"]
        maia_dashboard_values["env"].append({"name": "CIFS_SERVER", "value": cifs_server})

    # DISCORD_URL
    # DISCORD_SUPPORT_URL
    # DEFAULT_INGRESS_HOST
    # OPENWEBAI_API_KEY
    # OPENWEBAI_URL
    # BACKEND
    # MAIA_PRIVATE_REGISTRY registry.maia-cloud.com/maia-private needed when deploying PRO projects
    # ARGOCD_DISABLED
    # email_account:  <SMTP email address>
    # email_smtp_server: <SMTP server address>
    # email_password: <SMTP server password>
    domain = cluster_config_dict["domain"]
    maia_dashboard_values["env"].extend(
        [
            {"name": "MINIO_URL", "value": "minio:80"},
            {"name": "MINIO_PUBLIC_URL", "value": "minio:80"},
            {"name": "MINIO_ACCESS_KEY", "value": "maia-admin"},
            {"name": "MINIO_SECRET_KEY", "value": os.environ["minio_admin_password"]},
            {"name": "MINIO_SECURE", "value": "False"},
            {"name": "MINIO_PUBLIC_SECURE", "value": "True"},
            {"name": "BUCKET_NAME", "value": "maia-envs"},
            {"name": "SECRET_KEY", "value": os.environ["dashboard_api_secret"]},
            {"name": "POD_TERMINATOR_ADDRESS", "value": "http://pod-terminator.gpu-booking:8080"},
            {"name": "MINIO_CONSOLE_URL", "value": f"https://minio.{domain}/browser/maia-envs"},
            {"name": "MAIA_SEGMENTATION_PORTAL_NAMESPACE_ID", "value": "maia-segmentation"},
            {"name": "keycloak_client_id", "value": "maia"},
            {"name": "keycloak_client_secret", "value": os.environ["keycloak_client_secret"]},
            {"name": "keycloak_issuer_url", "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia"},
            {
                "name": "keycloak_authorize_url",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/auth",
            },
            {
                "name": "keycloak_token_url",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/token",
            },
            {
                "name": "keycloak_userdata_url",
                "value": "https://iam." + cluster_config_dict["domain"] + "/realms/maia/protocol/openid-connect/userinfo",
            },
            {
                "name": "maia_workspace_version",
                "value": os.environ.get("maia_workspace_version", maia_workspace_base_notebook_ssh_image_version),
            },
            {
                "name": "maia_workspace_image",
                "value": os.environ.get(
                    "maia_workspace_image", "ghcr.io/minnelab/" + maia_workspace_base_notebook_ssh_image_name
                ),
            },
            {
                "name": "maia_workspace_pro_version",
                "value": os.environ.get("maia_workspace_pro_version", maia_workspace_notebook_ssh_addons_image_version),
            },
            {
                "name": "maia_workspace_pro_image",
                "value": os.environ.get(
                    "maia_workspace_pro_image", "ghcr.io/minnelab/" + maia_workspace_notebook_ssh_addons_image_name
                ),
            },
            {
                "name": "maia_orthanc_image",
                "value": os.environ.get("maia_orthanc_image", "ghcr.io/minnelab/maia-orthanc"),
            },
            {
                "name": "maia_orthanc_version",
                "value": os.environ.get("maia_orthanc_version", maia_orthanc_image_version),
            },
        ]
    )

    if (
        "MAIA_PRIVATE_REGISTRY" in os.environ
        and "registry_username" in os.environ
        and "registry_password" in os.environ
        and "registry_email" in os.environ
    ):
        maia_dashboard_values["env"].extend(
            [
                {"name": "imagePullSecrets", "value": os.environ["MAIA_PRIVATE_REGISTRY"].replace("/", "-")},
            ]
        )

    Path(config_folder).joinpath(project_id, "maia_dashboard_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "maia_dashboard_values", "maia_dashboard_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(maia_dashboard_values))

    return {
        "namespace": maia_dashboard_values["namespace"],
        "release": f"{project_id}-dashboard",
        "chart": (
            maia_dashboard_values["chart_name"] if maia_dashboard_chart_type == "helm_repo" else maia_dashboard_values["path"]
        ),
        "repo": maia_dashboard_values["repo_url"],
        "version": maia_dashboard_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "maia_dashboard_values", "maia_dashboard_values.yaml")),
    }
