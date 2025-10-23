from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
from pathlib import Path
from secrets import token_urlsafe

import argocd_client
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from loguru import logger
from omegaconf import OmegaConf
from pyhelm3 import Client

from MAIA.maia_fn import (
    convert_username_to_jupyterhub_username,
    encode_docker_registry_secret,
    generate_human_memorable_password,
    get_ssh_port_dict,
    get_ssh_ports,
)


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


def generate_mlflow_configs(namespace):
    """
    Generate MLflow configuration dictionary with encoded user and password.

    Parameters
    ----------
    namespace : str
        The namespace to be encoded as the MLflow user.

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

    minimal_deployment = False
    if minio_configs is None or mlflow_configs is None:
        minimal_deployment = True

    maia_namespace_values = {
        "pvc": {"pvc_type": cluster_config["shared_storage_class"], "access_mode": "ReadWriteMany", "size": "10Gi"},
        "chart_name": "maia-namespace",
        "chart_version": "1.7.2",
        "repo_url": os.environ.get("MAIA_PRIVATE_REGISTRY", None),
        "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
        "serviceType": cluster_config["ssh_port_type"],
        "users": users,
        "orthanc": {"port": orthanc_ssh_port},
        "metallbSharedIp": cluster_config.get("metallb_shared_ip", False),
        "metallbIpPool": cluster_config.get("metallb_ip_pool", False),
        "loadBalancerIp": cluster_config.get("maia_metallb_ip", False),
    }
    if minimal_deployment:
        maia_namespace_values["chart_name"] = "maia-namespace"
        maia_namespace_values["chart_version"] = "1.7.2"
        maia_namespace_values["repo_url"] = "https://minnelab.github.io/MAIA/"

    if "imagePullSecrets" in cluster_config:
        maia_namespace_values["dockerRegistrySecret"] = {
            "enabled": True,
            "dockerRegistrySecretName": cluster_config["imagePullSecrets"],
            "dockerRegistrySecret": encode_docker_registry_secret(
                cluster_config["docker_server"], cluster_config["docker_username"], cluster_config["docker_password"]
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
            "clientId": cluster_config["keycloak"]["client_id"],
            "clientSecret": cluster_config["keycloak"]["client_secret"],
            "openIdConfigUrl": cluster_config["keycloak"]["issuer_url"] + "/.well-known/openid-configuration",
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
            #"user": base64.b64decode(mlflow_configs["mlflow_user"]).decode("ascii"),
            "user": mlflow_configs["mlflow_user"],
            "password": mlflow_configs["mlflow_password"]
            #"password": base64.b64decode(mlflow_configs["mlflow_password"]).decode("ascii"),
        }

    enable_cifs = namespace_config.get("extra_configs", {}).get("enable_cifs", False)
    if enable_cifs:
        maia_namespace_values["cifs"] = {"enabled": True, "encryption": {"publicKey": ""}}  # base64 encoded}
    namespace_id = namespace_config["group_ID"].lower().replace("_", "-")
    Path(config_folder).joinpath(namespace_config["group_ID"], "maia_namespace_values").mkdir(parents=True, exist_ok=True)
    with open(
        Path(config_folder).joinpath(namespace_config["group_ID"], "maia_namespace_values", "namespace_values.yaml"), "w"
    ) as f:
        f.write(OmegaConf.to_yaml(maia_namespace_values))

    return {
        "namespace": maia_namespace_values["namespace"],
        "release": f"{namespace_id}-namespace",
        "chart": maia_namespace_values["chart_name"],
        "repo": maia_namespace_values["repo_url"],
        "version": maia_namespace_values["chart_version"],
        "values": str(
            Path(config_folder).joinpath(namespace_config["group_ID"], "maia_namespace_values", "namespace_values.yaml")
        ),
    }


def create_filebrowser_values(namespace_config, cluster_config, config_folder, mlflow_configs=None):
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
        "chart_name": "maia-filebrowser",
        "chart_version": "1.0.0",
        "repo_url": "https://minnelab.github.io/MAIA/",
        "namespace": namespace_config["group_ID"].lower().replace("_", "-"),
    }

    maia_filebrowser_values["image"] = {"repository": cluster_config["docker_server"] + "/maia/maia-filebrowser", "tag": "1.0"}

    maia_filebrowser_values["imagePullSecrets"] = [{"name": cluster_config["imagePullSecrets"]}]
    if mlflow_configs is None:
        pw = generate_human_memorable_password(16)
    else:
        pw = base64.b64decode(mlflow_configs["mlflow_password"]).decode("ascii")
    maia_filebrowser_values["env"] = [
        {"name": "RUN_FILEBROWSER", "value": "True"},
        {"name": "n_users", "value": "1"},
        {"name": "user", "value": "maia-admin"},
        {"name": "password", "value": pw},
    ]

    maia_filebrowser_values["volumeMounts"] = [{"name": "cifs", "mountPath": "/home/cifs"}]

    cifs_user = convert_username_to_jupyterhub_username(namespace_config["users"][0])
    maia_filebrowser_values["volumes"] = [
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
    ]

    maia_filebrowser_values["ingress"] = {
        "enabled": True,
        "annotations": {},
        "hosts": [
            {
                "host": "cifs.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"]),
                "paths": [{"path": "/", "pathType": "ImplementationSpecific"}],
            }
        ],
        "tls": [{"hosts": ["cifs.{}.{}".format(namespace_config["group_subdomain"], cluster_config["domain"])]}],
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

    Path(config_folder).joinpath(namespace_config["group_ID"], "maia_filebrowser_values").mkdir(parents=True, exist_ok=True)
    with open(
        Path(config_folder).joinpath(namespace_config["group_ID"], "maia_filebrowser_values", "maia_filebrowser_values.yaml"), "w"
    ) as f:
        f.write(OmegaConf.to_yaml(maia_filebrowser_values))

    return {
        "namespace": maia_filebrowser_values["namespace"],
        "release": f"{namespace_id}-namespace",
        "chart": maia_filebrowser_values["chart_name"],
        "repo": maia_filebrowser_values["repo_url"],
        "version": maia_filebrowser_values["chart_version"],
        "values": str(
            Path(config_folder).joinpath(namespace_config["group_ID"], "maia_filebrowser_values", "maia_filebrowser_values.yaml")
        ),
    }


async def get_maia_toolkit_apps(group_id, token, argo_cd_host):
    """
    Retrieve and print information about a specific project and its associated applications from Argo CD.

    Parameters
    ----------
    group_id : str
        The group identifier used to construct project and application names.
    token : str
        The authorization token for accessing the Argo CD API.
    argo_cd_host : str
        The host URL of the Argo CD server.

    Returns
    -------
    None

    Raises
    ------
    ApiException
        If there is an error when calling the Argo CD API.
    """
    configuration = argocd_client.Configuration(host=argo_cd_host)
    with argocd_client.ApiClient(configuration) as api_client:
        api_client.default_headers["Authorization"] = f"Bearer {token}"
        api_instance = argocd_client.ProjectServiceApi(api_client)
        api_instance_apps = argocd_client.ApplicationServiceApi(api_client)
        name = group_id.lower().replace("_", "-")

        try:
            api_response = api_instance.get_mixin6(name)
            logger.debug(f"Project info: {api_response}")
        except ApiException as e:
            logger.error(f"Exception when calling ProjectServiceApi->get_mixin6: {e}")

        names = [
            f'{group_id.lower().replace("_", "-")}-namespace',
            f'{group_id.lower().replace("_", "-")}-jupyterhub',
            f'{group_id.lower().replace("_", "-")}-oauth2-proxy',
        ]
        project = [group_id.lower().replace("_", "-")]
        for name in names:
            try:
                api_response = api_instance_apps.get_mixin9(name, project=project)
                logger.debug(f"Application info: {api_response}")
            except ApiException as e:
                logger.error(f"Exception when calling ApplicationServiceApi->get_mixin9: {e}")


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

    Example
    -------
    await install_maia_project(
        group_id="example_group",
        values_file="/path/to/values.yaml",
        argo_cd_namespace="default",
        project_chart="example_chart",
        project_repo="https://example.com/charts",
        project_version="1.0.0"
    )
    """
    client = Client(kubeconfig=os.environ["KUBECONFIG"])

    if not project_repo.startswith("http"):
        chart = str("/tmp/" + project_chart + "-" + project_version + ".tgz")
        project_chart = "oci://" + project_repo + "/" + project_chart

        try:
            try:
                with open(json_key_path, "r") as f:
                    docker_credentials = json.load(f)
                    username = docker_credentials.get("harbor_username")
                    password = docker_credentials.get("harbor_password")
            except Exception:
                with open(json_key_path, "r") as f:
                    docker_credentials = f.read()
                    username = "_json_key"
                    password = docker_credentials
            result = subprocess.run(
                ["helm", "registry", "login", project_repo, "-u", username, "--password-stdin"],
                input=password.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            logger.info("✅ Helm registry login successful.")
            logger.debug(result.stdout.decode())
        except subprocess.CalledProcessError as e:
            logger.error("❌ Helm registry login failed.")
            logger.error(f"STDOUT: {e.stdout.decode()}")
            logger.error(f"STDERR: {e.stderr.decode()}")
            await asyncio.sleep(1)
            return "Deployment failed: Helm registry login failed."
        subprocess.run(["helm", "pull", project_chart, "-d", "/tmp", "--version", project_version], check=True)

        subprocess.run(
            [
                "helm",
                "upgrade",
                "--install",
                group_id.lower().replace("_", "-"),
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

    chart = await client.get_chart(project_chart, repo=project_repo, version=project_version)

    with open(values_file) as f:
        values = yaml.safe_load(f)

    revision = await client.install_or_upgrade_release(
        group_id.lower().replace("_", "-"), chart, values, namespace=argo_cd_namespace, wait=True
    )
    logger.info(
        f"Release: {revision.release.name}, Namespace: {revision.release.namespace}, "
        f"Revision: {revision.revision}, Status: {revision.status}"
    )

    return ""


def create_maia_admin_toolkit_values(config_folder, project_id, cluster_config_dict, maia_config_dict):
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
    maia_config_dict : dict
        Dictionary containing MAIA configuration values.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values YAML file.
    """
    admin_group_id = maia_config_dict["admin_group_ID"]

    admin_toolkit_values = {
        "namespace": "maia-admin-toolkit",
        "repo_url": "https://minnelab.github.io/MAIA/",
        "chart_name": "maia-admin-toolkit",
        "chart_version": "1.2.6",
    }

    admin_toolkit_values.update(
        {
            "argocd": {
                "enabled": True,
                "argocd_namespace": "argocd",
                "argocd_domain": "argocd." + cluster_config_dict["domain"],
                "keycloak_issuer_url": "https://iam." + cluster_config_dict["domain"] + "/realms/maia",
                "keycloak_client_id": "maia",
                "keycloak_client_secret": cluster_config_dict["keycloak"]["client_secret"],
            },
            "certResolver": cluster_config_dict["traefik_resolver"],
            "admin_group_ID": admin_group_id,
            "harbor": {
                "enabled": True,
                "values": {"namespace": "harbor", "storageClassName": cluster_config_dict["storage_class"]},
            },
            "dashboard": {"enabled": True, "dashboard_domain": "dashboard." + cluster_config_dict["domain"]},
        }
    )

    Path(config_folder).joinpath(project_id, "maia_admin_toolkit_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(project_id, "maia_admin_toolkit_values", "maia_admin_toolkit_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(admin_toolkit_values))

    return {
        "namespace": admin_toolkit_values["namespace"],
        "release": f"{project_id}-toolkit",
        "chart": admin_toolkit_values["chart_name"],
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
        "chart_version": "1.16.0",
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
        harbor_values["expose"]["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
            cluster_config_dict["traefik_resolver"]
        )
    elif cluster_config_dict["ingress_class"] == "nginx":
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
        "chart_version": "24.2.0",
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
            "extraVolumeMounts": [{"name": "keycloak-import", "mountPath": "/opt/bitnami/keycloak/data/import"}],
            "extraVolumes": [{"name": "keycloak-import", "configMap": {"name": "maia-realm-import"}}],
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        keycloak_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        keycloak_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        keycloak_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = cluster_config_dict[
            "traefik_resolver"
        ]
    elif cluster_config_dict["ingress_class"] == "nginx":
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
        "chart_version": "1.3.0",
    }

    secret = token_urlsafe(16).replace("-", "_")
    client_id = "maia"
    client_secret = cluster_config_dict["keycloak"]["client_secret"]
    issuer_url = "https://iam." + cluster_config_dict["domain"] + "/realms/maia"
    cluster_server_address = "https://" + cluster_config_dict["domain"] + ":16443"
    ca_file = "/var/snap/microk8s/current/certs/ca.crt"

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
        loginapp_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = cluster_config_dict[
            "traefik_resolver"
        ]
    elif cluster_config_dict["ingress_class"] == "nginx":
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


def create_minio_operator_values(config_folder, project_id, cluster_config_dict):
    """
    Creates and writes MinIO operator values to a YAML file and returns a dictionary with deployment details.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder.
    project_id : str
        The unique identifier for the project.
    cluster_config_dict : dict
        A dictionary containing cluster configuration details.

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
        "chart_version": "6.0.4",
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


def create_maia_dashboard_values(config_folder, project_id, cluster_config_dict, maia_config_dict):
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
    maia_config_dict : dict
        Dictionary containing MAIA configuration details.

    Returns
    -------
    dict
        A dictionary containing the namespace, release name, chart name, repository URL, chart version,
        and the path to the generated values YAML file.
    """

    maia_dashboard_values = {
        "namespace": "maia-dashboard",
        "repo_url": "https://minnelab.github.io/MAIA/",
        "chart_name": "maia-dashboard",
        "chart_version": "0.1.6",
    }

    maia_dashboard_values.update(
        {
            "image": {
                "repository": maia_config_dict["dashboard_image"],
                "pullPolicy": "IfNotPresent",
                "tag": maia_config_dict["dashboard_version"],
            },
            "imagePullSecrets": [{"name": "registry." + cluster_config_dict["domain"]}],  # TODO: Update
            "storageClass": cluster_config_dict["storage_class"],
            "ingress": {
                "enabled": True,
                "className": cluster_config_dict["ingress_class"],
                "annotations": {},
                "hosts": [
                    {
                        "host": cluster_config_dict["domain"],
                        "paths": [
                            {"path": "/maia/", "pathType": "Prefix"},
                            {"path": "/maia-api/", "pathType": "Prefix"},
                            {"path": "/", "pathType": "Prefix"},
                        ],
                    }
                ],
                "tls": [{"hosts": [cluster_config_dict["domain"]]}],
            },
            "gpuList": maia_config_dict["gpu_list"],
            "dashboard": {
                "host": cluster_config_dict["domain"],
                "openwebai_api_key": "",
                "api_secret_key": maia_config_dict["dashboard_api_secret"],
                "keycloak": {
                    "client_id": "maia",
                    "client_secret": cluster_config_dict["keycloak"]["client_secret"],
                    "url": "https://iam." + cluster_config_dict["domain"] + "/",
                    "realm": "maia",
                    "username": "admin",
                },
                "argocd_server": "https://argocd." + cluster_config_dict["domain"],
                "argocd_cluster_name": cluster_config_dict["cluster_name"],
                "local_db_path": "/etc/MAIA-Dashboard/db",
            },
            "argocd_namespace": maia_config_dict["argocd_namespace"],
            "admin_group_ID": maia_config_dict["admin_group_ID"],
            "core_project_chart": maia_config_dict["core_project_chart"],
            "core_project_repo": maia_config_dict["core_project_repo"],
            "core_project_version": maia_config_dict["core_project_version"],
            "admin_project_chart": maia_config_dict["admin_project_chart"],
            "admin_project_repo": maia_config_dict["admin_project_repo"],
            "admin_project_version": maia_config_dict["admin_project_version"],
            "maia_project_chart": maia_config_dict["maia_project_chart"],
            "maia_project_repo": maia_config_dict["maia_project_repo"],
            "maia_project_version": maia_config_dict["maia_project_version"],
            "maia_pro_project_chart": maia_config_dict["maia_pro_project_chart"],
            "maia_pro_project_repo": maia_config_dict["maia_pro_project_repo"],
            "maia_pro_project_version": maia_config_dict["maia_pro_project_version"],
            "maia_workspace_version": maia_config_dict["maia_workspace_version"],
            "maia_workspace_image": maia_config_dict["maia_workspace_image"],
            "maia_workspace_pro_version": maia_config_dict["maia_workspace_pro_version"],
            "maia_workspace_pro_image": maia_config_dict["maia_workspace_pro_image"],
            "maia_orthanc_version": maia_config_dict["maia_orthanc_version"],
            "maia_orthanc_image": maia_config_dict["maia_orthanc_image"],
            "maia_monai_toolkit_image": maia_config_dict["maia_monai_toolkit_image"],
            "name": "maia-dashboard",
            "dockerRegistrySecretName": "registry." + cluster_config_dict["domain"],
            "dockerRegistryUsername": cluster_config_dict["docker_username"],
            "dockerRegistryPassword": cluster_config_dict["docker_password"],
            "dockerRegistryEmail": cluster_config_dict["docker_email"],
            "dockerRegistryServer": "registry." + cluster_config_dict["domain"],
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
            cluster_config_dict["traefik_resolver"]
        )
    elif cluster_config_dict["ingress_class"] == "nginx":
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "8g"
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-read-timeout"] = "300"
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-send-timeout"] = "300"
        maia_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"
        maia_dashboard_values["ingress"]["tls"][0]["secretName"] = cluster_config_dict["domain"]

    maia_dashboard_values["clusters"] = [cluster_config_dict]

    if "discord_url" in maia_config_dict:
        maia_dashboard_values["dashboard"]["discord_url"] = maia_config_dict["discord_url"]
    #if "discord_signup_url" in maia_config_dict:
    #    maia_dashboard_values["dashboard"]["discord_signup_url"] = maia_config_dict["discord_signup_url"]
    if "discord_support_url" in maia_config_dict:
        maia_dashboard_values["dashboard"]["discord_support_url"] = maia_config_dict["discord_support_url"]

    debug = False

    if debug:

        maia_dashboard_values["env"] = [
            {"name": "DEBUG", "value": "True"},
            {"name": "CLUSTER_CONFIG_PATH", "value": "/etc/MAIA-Dashboard/config"},
            {"name": "CONFIG_PATH", "value": "/etc/MAIA-Dashboard/config"},
            {"name": "MAIA_CONFIG_PATH", "value": "/etc/MAIA-Dashboard/config/maia_config.yaml"},
            {"name": "GLOBAL_NAMESPACES", "value": "xnat,kubeflow,istio-system"},
        ]
        maia_dashboard_values["dashboard"]["local_config_path"] = "/etc/MAIA-Dashboard/config"
    else:

        if "mysql_dashboard_password" in maia_config_dict:
            db_password = maia_config_dict["mysql_dashboard_password"]
        else:
            db_password = generate_human_memorable_password()
        maia_dashboard_values["dashboard"]["local_config_path"] = "/mnt/dashboard-config"
        cifs_server = ""
        maia_dashboard_values["env"] = [
            {"name": "DEBUG", "value": "False"},
            {"name": "CLUSTER_CONFIG_PATH", "value": "/mnt/dashboard-config"},
            {"name": "CONFIG_PATH", "value": "/mnt/dashboard-config"},
            {"name": "MAIA_CONFIG_PATH", "value": "/mnt/dashboard-config/maia_config.yaml"},
            {"name": "DB_ENGINE", "value": "mysql"},
            {"name": "DB_NAME", "value": "mysql"},
            {"name": "DB_HOST", "value": "maia-admin-maia-dashboard-mysql"},
            {"name": "DB_PORT", "value": "3306"},
            {"name": "DB_USERNAME", "value": "maia-admin"},
            {"name": "DB_PASS", "value": db_password},
            {"name": "GLOBAL_NAMESPACES", "value": "xnat,kubeflow,istio-system"},
            {"name": "POD_TERMINATOR_ADDRESS", "value": ""},
            {"name": "MINIO_CONSOLE_URL", "value": ""},
            {"name": "MAIA_SEGMENTATION_PORTAL_NAMESPACE_ID", "value": "maia-segmentation"},
        ]
        if maia_config_dict["cifs_server"]:
            cifs_server = maia_config_dict["cifs_server"]
            maia_dashboard_values["env"].append({"name": "CIFS_SERVER", "value": cifs_server})
        maia_dashboard_values["mysql"] = {
            "enabled": True,
            "mysqlRootPassword": db_password,
            "mysqlUser": "maia-admin",
            "mysqlPassword": db_password,
            "mysqlDatabase": "mysql",
        }

    if maia_config_dict["email_server_credentials"]:
        maia_dashboard_values["env"].extend(
            [
                {"name": "email_account", "value": maia_config_dict["email_server_credentials"]["email_account"]},
                {"name": "email_password", "value": maia_config_dict["email_server_credentials"]["email_password"]},
                {"name": "email_smtp_server", "value": maia_config_dict["email_server_credentials"]["email_smtp_server"]},
            ]
        )
    maia_dashboard_values["env"].append({"name": "MAIA_PRIVATE_REGISTRY", "value": maia_config_dict["maia_private_registry"]})
    if "minio" in maia_config_dict:
        maia_dashboard_values["dashboard"]["minio"] = {
            "url": maia_config_dict["minio"]["url"],
            "access_key": maia_config_dict["minio"]["access_key"],
            "secret_key": maia_config_dict["minio"]["secret_key"],
            "secure": maia_config_dict["minio"]["secure"],
            "bucket_name": maia_config_dict["minio"]["bucket_name"],
        }
    Path(config_folder).joinpath(project_id, "maia_dashboard_values").mkdir(parents=True, exist_ok=True)
    with open(Path(config_folder).joinpath(project_id, "maia_dashboard_values", "maia_dashboard_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(maia_dashboard_values))

    return {
        "namespace": maia_dashboard_values["namespace"],
        "release": f"{project_id}-dashboard",
        "chart": maia_dashboard_values["chart_name"],
        "repo": maia_dashboard_values["repo_url"],
        "version": maia_dashboard_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "maia_dashboard_values", "maia_dashboard_values.yaml")),
    }
