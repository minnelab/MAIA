from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
import requests
from loguru import logger
import yaml
from omegaconf import OmegaConf
from pyhelm3 import Client

from MAIA.maia_fn import generate_human_memorable_password
from MAIA.maia_k8s_distros import get_api_port
from MAIA.versions import (
    define_maia_admin_versions,
    define_maia_project_versions,
    define_docker_image_versions,
)

maia_workspace_notebook_ssh_addons_image_version = define_docker_image_versions()["maia-workspace-notebook-ssh-addons"]
maia_workspace_notebook_ssh_addons_image_name = define_docker_image_versions()["maia-workspace-notebook-ssh-addons-image-name"]
maia_workspace_base_notebook_ssh_image_version = define_docker_image_versions()["maia-workspace-base-notebook-ssh"]
maia_workspace_base_notebook_ssh_image_name = define_docker_image_versions()["maia-workspace-base-notebook-ssh-image-name"]
maia_project_chart_version = define_maia_project_versions()["maia_project_chart_version"]
maia_orthanc_image_version = define_docker_image_versions()["maia-orthanc"]
admin_toolkit_chart_version = define_maia_admin_versions()["admin_toolkit_chart_version"]
admin_toolkit_chart_type = define_maia_admin_versions()["admin_toolkit_chart_type"]
rancher_chart_version = define_maia_admin_versions()["rancher_chart_version"]
harbor_chart_version = define_maia_admin_versions()["harbor_chart_version"]
keycloak_chart_version = define_maia_admin_versions()["keycloak_chart_version"]
maia_dashboard_chart_version = define_maia_admin_versions()["maia_dashboard_chart_version"]
maia_dashboard_image_version = define_maia_admin_versions()["maia_dashboard_image_version"]
maia_dashboard_dev_tag_suffix = define_maia_admin_versions()["maia_dashboard_dev_tag_suffix"]
maia_dashboard_chart_type = define_maia_admin_versions()["maia_dashboard_chart_type"]
mysql_image = define_docker_image_versions()["mysql_image"]
mysql_image_version = define_docker_image_versions()["mysql"]


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

    realm_name = os.environ.get("KEYCLOAK_REALM_NAME", "maia")
    keycloak_domain = cluster_config_dict["domain"]
    if "KEYCLOAK_DOMAIN" in os.environ:
        keycloak_domain = os.environ["KEYCLOAK_DOMAIN"]
    admin_toolkit_values.update(
        {
            "argocd": {
                "enabled": True,
                "argocd_namespace": "argocd",
                "argocd_domain": "argocd." + cluster_config_dict["domain"],
                "keycloak_issuer_url": "https://iam." + keycloak_domain + "/realms/" + realm_name,
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
    
    if "CLUSTER_YAML_CONFIGS" in os.environ:
        clusters = []
        cluster_files = os.environ["CLUSTER_YAML_CONFIGS"].split(",")
        for cluster_file in cluster_files:
            if not os.path.isabs(cluster_file):
                cluster_file = str(Path(config_folder).joinpath(cluster_file).resolve())
            with open(cluster_file, "r") as f:
                cluster_config_dict_temp = yaml.safe_load(f)
                clusters.append({
                    "name": cluster_config_dict_temp["cluster_name"],
                    "server": cluster_config_dict_temp["api"],
                    "token": cluster_config_dict_temp.get("maia_dashboard", {}).get("token", ""),
                })

    admin_toolkit_values["argocd"]["additional_clusters"] = clusters

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
                "adminPassword": os.environ.get("keycloak_admin_password", ""),
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

    default_registry = os.environ.get("MAIA_REGISTRY", "ghcr.io/minnelab")
    dashboard_domain = cluster_config_dict["domain"]
    if "DASHBOARD_DOMAIN" in os.environ:
        dashboard_domain = os.environ["DASHBOARD_DOMAIN"]
    keycloak_domain = cluster_config_dict["domain"]
    if "KEYCLOAK_DOMAIN" in os.environ:
        keycloak_domain = os.environ["KEYCLOAK_DOMAIN"]
    argocd_domain = cluster_config_dict["domain"]
    if "ARGOCD_DOMAIN" in os.environ:
        argocd_domain = os.environ["ARGOCD_DOMAIN"]
    maia_dashboard_values.update(
        {
            "ingress": {
                "enabled": True,
                "className": cluster_config_dict["ingress_class"],
                "annotations": {},
                "hosts": [
                    {
                        "host": "maia." + dashboard_domain,
                        "paths": [
                            {"path": "/", "pathType": "ImplementationSpecific"},
                            {"path": "/maia-api/", "pathType": "ImplementationSpecific"},
                            {"path": "/maia/", "pathType": "ImplementationSpecific"},
                        ],
                    }
                ],
                "tls": [{"hosts": ["maia." + dashboard_domain]}],
            },
            "env": [
                {"name": "DEBUG", "value": "False"},
                {"name": "LOCAL_DB_PATH", "value": "/etc/MAIA-Dashboard/db"},
            ],
            "storageClass": cluster_config_dict["storage_class"],
            "image": {"repository": f"{default_registry}/maia-dashboard", "tag": maia_dashboard_image_version},
            "dashboard": {"local_config_path": "/mnt/dashboard-config"},
            "mysql": {"enabled": True, "image": mysql_image, "tag": mysql_image_version},
        }
    )
    if cluster_config_dict["url_type"] == "subpath":
        maia_dashboard_values["ingress"]["hosts"][0]["host"] = dashboard_domain
        maia_dashboard_values["ingress"]["tls"][0]["hosts"][0] = dashboard_domain
        maia_dashboard_values["env"].append({"name": "SERVER", "value": dashboard_domain})
    else:
        maia_dashboard_values["env"].append({"name": "SERVER", "value": "maia." + dashboard_domain})

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        maia_dashboard_values["ingress"]["annotations_redirect"] = {"traefik.ingress.kubernetes.io/router.entrypoints": "web"}
        maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            maia_dashboard_values["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
    elif cluster_config_dict["ingress_class"] == "nginx":
        cluster_issuer_name = cluster_config_dict.get("nginx_cluster_issuer", "cluster-issuer")
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "8g"
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-read-timeout"] = "300"
        maia_dashboard_values["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-send-timeout"] = "300"
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            maia_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = "kubernetes-ca-issuer"
        else:
            maia_dashboard_values["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = cluster_issuer_name
        maia_dashboard_values["ingress"]["tls"][0]["secretName"] = dashboard_domain

    # Authentication
    realm_name = os.environ.get("KEYCLOAK_REALM_NAME", "maia")
    maia_dashboard_values["env"].extend(
        [
            {"name": "OIDC_RP_CLIENT_ID", "value": "maia"},
            {"name": "OIDC_RP_PUBLIC_CLIENT_ID", "value": "maia-public"},
            {"name": "OIDC_RP_CLIENT_SECRET", "value": os.environ["keycloak_client_secret"]},
            {"name": "OIDC_SERVER_URL", "value": "https://iam." + keycloak_domain},
            {"name": "OIDC_REALM_NAME", "value": realm_name},
            {"name": "OIDC_USERNAME", "value": "admin"},
            {"name": "OIDC_ISSUER_URL", "value": "https://iam." + keycloak_domain + f"/realms/{realm_name}"},
            {
                "name": "OIDC_OP_AUTHORIZATION_ENDPOINT",
                "value": "https://iam." + keycloak_domain + f"/realms/{realm_name}/protocol/openid-connect/auth",
            },
            {
                "name": "OIDC_OP_TOKEN_ENDPOINT",
                "value": "https://iam." + keycloak_domain + f"/realms/{realm_name}/protocol/openid-connect/token",
            },
            {
                "name": "OIDC_OP_USER_ENDPOINT",
                "value": "https://iam." + keycloak_domain + f"/realms/{realm_name}/protocol/openid-connect/userinfo",
            },
            {
                "name": "OIDC_OP_JWKS_ENDPOINT",
                "value": "https://iam." + keycloak_domain + f"/realms/{realm_name}/protocol/openid-connect/certs",
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
            "maia_dashboard": {"enabled": True, "token": os.environ.get("rancher_token", "")},
        }
    ]

    if os.environ.get("MAIA_DASHBOARD_OIDC_AUTHENTICATION", False):

        port = get_api_port(os.environ["K8S_DISTRIBUTION"])
        maia_dashboard_values["clusters"][0]["api"] = f"https://{cluster_config_dict['domain']}:{port}"
        maia_dashboard_values["clusters"][0]["maia_dashboard"]["token"] = ""
        maia_dashboard_values["env"].extend(
            [
                {"name": "MAIA_DASHBOARD_OIDC_AUTHENTICATION", "value": "True"},
            ]
        )

    argocd_cluster = cluster_config_dict["cluster_name"]
    if os.environ.get("ARGOCD_CLUSTER") is not None:
        argocd_cluster = os.environ["ARGOCD_CLUSTER"]
    maia_dashboard_values["env"].extend(
        [
            {"name": "ARGOCD_CLUSTER", "value": argocd_cluster},
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

        maia_dashboard_values["ca_crt"] = open(Path(cluster_config_dict["rootCA"])).read()

        maia_dashboard_values["clusters"][0]["selfsigned"] = True
    elif "staging_certificates" in cluster_config_dict and cluster_config_dict["staging_certificates"]:
        maia_dashboard_values["env"].extend(
            [
                {"name": "OIDC_CA_BUNDLE", "value": "/mnt/dashboard-config/ca.crt"},
            ]
        )
        maia_dashboard_values["ca_crt"] = open(Path(cluster_config_dict["externalCA"]["cert"])).read()
        maia_dashboard_values["clusters"][0]["selfsigned"] = True
        if "traefik_resolver" in cluster_config_dict:
            maia_dashboard_values["clusters"][0]["traefik_resolver"] = cluster_config_dict["traefik_resolver"]
        elif "nginx_cluster_issuer" in cluster_config_dict:
            maia_dashboard_values["clusters"][0]["nginx_cluster_issuer"] = cluster_config_dict["nginx_cluster_issuer"]
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
            {"name": "admin_group_ID", "value": os.environ.get("admin_group_ID", "MAIA:admin")},
            {"name": "USERS_GROUP", "value": cluster_config_dict.get("users_group", "users")},
            {"name": "argocd_namespace", "value": "argocd"},
            {"name": "ARGOCD_SERVER", "value": "https://argocd." + argocd_domain},
            {"name": "ARGOCD_PASSWORD", "value": os.environ["ARGOCD_PASSWORD"]},
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
        maia_dashboard_values["image"]["repository"] = f"{default_registry}/maia-dashboard-dev"

    if os.environ.get("DEV_TAG") is not None:
        maia_dashboard_values["env"].extend(
            [
                {"name": "DEV_TAG", "value": os.environ["DEV_TAG"]},
            ]
        )
        maia_dashboard_values["env"].extend(
            [
                {"name": "MAIA_VERSION", "value": os.environ["DEV_TAG"]},
            ]
        )
    if os.environ.get("CIFS_SERVER") is not None:
        maia_dashboard_values["env"].extend(
            [
                {"name": "CIFS_SERVER", "value": os.environ["CIFS_SERVER"]},
            ]
        )
    if os.environ.get("CIFS_PUBLIC_KEY") is not None:
        if "CIFS_PUBLIC_KEY" in os.environ:
            if Path(os.environ["CIFS_PUBLIC_KEY"]).exists():
                public_key = open(os.environ["CIFS_PUBLIC_KEY"], "r").read()
            else:
                public_key = open(Path(config_folder).joinpath(os.environ["CIFS_PUBLIC_KEY"]), "r").read()
        else:
            public_key = ""
        maia_dashboard_values["cifs_public_key"] = public_key
        maia_dashboard_values["env"].extend(
            [
                {"name": "CIFS_PUBLIC_KEY", "value": "/var/cifs/public-key.pem"},
            ]
        )
    ### MinIO Configuration
    minio_console_url = f"https://minio.{dashboard_domain}/browser/maia-envs"
    if os.environ.get("MINIO_CONSOLE_URL") is not None:
        minio_console_url = os.environ["MINIO_CONSOLE_URL"]
    minio_url = "minio:80"
    if os.environ.get("MINIO_URL") is not None:
        minio_url = os.environ["MINIO_URL"]
    maia_dashboard_values["env"].extend(
        [
            {"name": "MINIO_URL", "value": minio_url},
            {"name": "MINIO_ACCESS_KEY", "value": "maia-admin"},
            {"name": "MINIO_SECRET_KEY", "value": os.environ["minio_admin_password"]},
            {"name": "BUCKET_NAME", "value": "maia-envs"},
            {"name": "MINIO_CONSOLE_URL", "value": minio_console_url},
        ]
    )
    if "MINIO_SECURE" in os.environ:
        maia_dashboard_values["env"].extend(
            [
                {"name": "MINIO_SECURE", "value": os.environ["MINIO_SECURE"]},
            ]
        )
    else:
        maia_dashboard_values["env"].extend(
            [
                {"name": "MINIO_SECURE", "value": "False"},
            ]
        )
    if "MINIO_PUBLIC_SECURE" in os.environ:
        maia_dashboard_values["env"].extend(
            [
                {"name": "MINIO_PUBLIC_SECURE", "value": os.environ["MINIO_PUBLIC_SECURE"]},
            ]
        )
    else:
        maia_dashboard_values["env"].extend(
            [
                {"name": "MINIO_PUBLIC_SECURE", "value": "False"},
            ]
        )
    if "MINIO_PUBLIC_URL" in os.environ:
        maia_dashboard_values["env"].extend(
            [
                {"name": "MINIO_PUBLIC_URL", "value": os.environ["MINIO_PUBLIC_URL"]},
            ]
        )

    ## MONAI Toolkit Image and Orthanc
    maia_dashboard_values["env"].extend(
        [
            {"name": "MONAI_TOOLKIT_IMAGE", "value": f"{default_registry}/monai-toolkit"},
        ]
    )

    ## MAIA Registry where  the MAIA images can be pulled from, can also be maiacloudai, default is ghcr.io/minnelab
    maia_dashboard_values["env"].extend(
        [
            {"name": "MAIA_REGISTRY", "value": os.environ.get("MAIA_REGISTRY", "ghcr.io/minnelab")},
        ]
    )

    ## MySQL Configuration

    if "mysql_dashboard_password" in os.environ:
        db_password = os.environ["mysql_dashboard_password"]
    else:
        db_password = generate_human_memorable_password()

    maia_dashboard_values["env"].extend(
        [
            {"name": "DB_ENGINE", "value": "mysql"},
            {"name": "DB_NAME", "value": "mysql"},
            {"name": "DB_HOST", "value": "maia-admin-maia-dashboard-mysql"},
            {"name": "DB_PORT", "value": "3306"},
            {"name": "DB_USERNAME", "value": "maia-admin"},
            {"name": "DB_PASS", "value": db_password},
        ]
    )
    maia_dashboard_values["mysql"].update(
        {
            "mysqlRootPassword": db_password,
            "mysqlUser": "maia-admin",
            "mysqlPassword": db_password,
            "mysqlDatabase": "mysql",
        }
    )

    # Email Notification Systen

    if (
        "SMTP_SENDER_EMAIL" in os.environ
        and "SMTP_SERVER" in os.environ
        and "SMTP_PORT" in os.environ
        and "SMTP_PASSWORD" in os.environ
    ):
        maia_dashboard_values["env"].extend(
            [
                {"name": "SMTP_SENDER_EMAIL", "value": os.environ["SMTP_SENDER_EMAIL"]},
                {"name": "SMTP_SERVER", "value": os.environ["SMTP_SERVER"]},
                {"name": "SMTP_PORT", "value": os.environ["SMTP_PORT"]},
                {"name": "SMTP_PASSWORD", "value": os.environ["SMTP_PASSWORD"]},
            ]
        )

    # Webhook and Support URL
    if "WEBHOOK_URL" in os.environ and "SUPPORT_URL" in os.environ:
        maia_dashboard_values["env"].extend(
            [
                {"name": "WEBHOOK_URL", "value": os.environ["WEBHOOK_URL"]},
                {"name": "SUPPORT_URL", "value": os.environ["SUPPORT_URL"]},
            ]
        )

    # MAIA-Chatbot Configuration
    if "OPENWEBAI_API_KEY" in os.environ and "OPENWEBAI_URL" in os.environ and "OPENWEBAI_MODEL" in os.environ:
        maia_dashboard_values["env"].extend(
            [
                {"name": "OPENWEBAI_API_KEY", "value": os.environ["OPENWEBAI_API_KEY"]},
                {"name": "OPENWEBAI_URL", "value": os.environ["OPENWEBAI_URL"]},
                {"name": "OPENWEBAI_MODEL", "value": os.environ["OPENWEBAI_MODEL"]},
            ]
        )

    # GPU Configuration
    maia_dashboard_values["gpuList"] = os.environ.get("gpu_list", [])

    # MAIA Projects Configuration
    if "maia_projects" in os.environ:
        projects = os.environ["maia_projects"].split(",")
        maia_dashboard_values["maia_projects"] = []
        for project in projects:
            # If the project path is not absolute, expand it relative to the config_folder
            if not os.path.isabs(project):
                project = str(Path(config_folder).joinpath(project).resolve())
            with open(project, "r") as f:
                project_dict = json.load(f)
            maia_dashboard_values["maia_projects"].append(project_dict)

    aliases_env_string = os.environ.get("HOST_ALIASES", "[]")

    # 2. Parse the string back into a list
    try:
        host_aliases = json.loads(aliases_env_string)
    except json.JSONDecodeError:
        print("Error: HOST_ALIASES is not valid JSON.")
        host_aliases = []

    maia_dashboard_values["hostAliases"] = host_aliases

    if "CLUSTER_YAML_CONFIGS" in os.environ:
        maia_dashboard_values["clusters"] = []
        cluster_files = os.environ["CLUSTER_YAML_CONFIGS"].split(",")
        for cluster_file in cluster_files:
            if not os.path.isabs(cluster_file):
                cluster_file = str(Path(config_folder).joinpath(cluster_file).resolve())
            with open(cluster_file, "r") as f:
                cluster_config_dict = yaml.safe_load(f)
                maia_dashboard_values["clusters"].append(cluster_config_dict)

    # CIFS
    # MAIA Segmentation Portal
    # GPU Booking
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


def create_rancher_values(config_folder, project_id, cluster_config_dict):
    """
    Generates Rancher values configuration and writes it to a YAML file.

    Parameters
    ----------
    config_folder : str
        The path to the configuration folder.
    project_id : str
        The project identifier.
    cluster_config_dict : dict
        A dictionary containing cluster configuration details.

    Returns
    -------
    dict
        A dictionary containing Rancher deployment details including namespace, repo URL,
        chart version, values file path, release name, and chart name.
    """

    rancher_values = {
        "namespace": "cattle-system",
        "repo_url": "https://releases.rancher.com/server-charts/latest",
        "chart_name": "rancher",
        "chart_version": rancher_chart_version,
    }  # TODO: Change this to updated values

    rancher_values.update(
        {
            "hostname": "mgmt." + cluster_config_dict["domain"],
            "ingress": {"extraAnnotations": {}, "tls": {"source": "letsEncrypt"}},
            "letsEncrypt": {
                "email": cluster_config_dict["ingress_resolver_email"],
                "ingress": {"class": cluster_config_dict["ingress_class"]},
            },
            "bootstrapPassword": os.environ.get("rancher_password", ""),
        }
    )

    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        rancher_values["ingress"]["extraAnnotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        rancher_values["ingress"]["extraAnnotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"
        rancher_values["ingress"]["tls"]["secretName"] = None

        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            rancher_values["ingress"]["extraAnnotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = (
                cluster_config_dict["traefik_resolver"]
            )
    elif cluster_config_dict["ingress_class"] == "nginx":
        if "selfsigned" in cluster_config_dict and cluster_config_dict["selfsigned"]:
            ...
        else:
            rancher_values["ingress"]["extraAnnotations"]["cert-manager.io/cluster-issuer"] = "cluster-issuer"

    Path(config_folder).joinpath(project_id, "rancher_values").mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(project_id, "rancher_values", "rancher_values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(rancher_values))

    return {
        "namespace": rancher_values["namespace"],
        "repo": rancher_values["repo_url"],
        "version": rancher_values["chart_version"],
        "values": str(Path(config_folder).joinpath(project_id, "rancher_values", "rancher_values.yaml")),
        "release": f"{project_id}-rancher",
        "chart": rancher_values["chart_name"],
    }
