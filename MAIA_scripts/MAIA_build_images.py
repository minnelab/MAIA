#!/usr/bin/env python

from __future__ import annotations

import asyncio
import datetime
import json
import os
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent

import click
import requests
import yaml
from hydra import compose as hydra_compose
from hydra import initialize_config_dir
from kubernetes import config
from omegaconf import OmegaConf

import MAIA
from MAIA.kubernetes_utils import create_helm_repo_secret_from_context
from MAIA.maia_admin import install_maia_project
from MAIA.maia_docker_images import deploy_maia_kaniko

version = MAIA.__version__


TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())

DESC = dedent(
    """
    Script to Build MAIA Docker Images using Kaniko. The specific MAIA configuration is specified
    by setting the corresponding ``--maia-config-file``, and the cluster configuration is specified by setting
    the corresponding ``--cluster-config``.
    """  # noqa: E501
)
EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --cluster-config /PATH/TO/cluster_config.yaml --config-folder /PATH/TO/config_folder
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--cluster-config",
        type=str,
        required=True,
        help="YAML configuration file used to extract the cluster configuration.",
    )

    pars.add_argument(
        "--config-folder",
        type=str,
        required=True,
        help="Configuration Folder where to locate (and temporarily store) the MAIA configuration files.",
    )
    pars.add_argument(
        "--registry-path",
        type=str,
        required=False,
        default="",
        help="Optional path to the Docker registry. If not provided, the default is empty.",
    )
    pars.add_argument(
        "--project-id",
        type=str,
        required=True,
        help="Project ID to use for ArgoCD. This is used to identify the project in the cluster.",
    )
    pars.add_argument(
        "--build-version-file",
        type=str,
        required=False,
        default="https://raw.githubusercontent.com/minnelab/MAIA/master/MAIA/configs/docker_versions.yaml",
        help="Optional file containing the version of the Docker Images to build. If not provided, the default version is 1.0",
    )
    pars.add_argument(
        "--cluster-address",
        type=str,
        required=False,
        default="https://kubernetes.default.svc",
        help="Optional address of the cluster. If not provided, the default is https://kubernetes.default.svc",
    )

    pars.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return pars


@click.command()
@click.option("--cluster-config", type=str)
@click.option("--config-folder", type=str)
@click.option("--registry-path", type=str, default="")
@click.option("--project-id", required=True, type=str)
@click.option("--cluster-address", type=str, default="https://kubernetes.default.svc")
@click.option(
    "--build-version-file",
    type=str,
    default="https://raw.githubusercontent.com/minnelab/MAIA/master/MAIA/configs/docker_versions.yaml",
)
def main(
    cluster_config,
    config_folder,
    project_id,
    build_version_file,
    registry_path,
    cluster_address,
):
    build_maia_images(
        cluster_config,
        config_folder,
        project_id,
        build_version_file,
        registry_path,
        cluster_address,
    )


def build_maia_images(
    cluster_config,
    config_folder,
    project_id,
    build_version_file="https://raw.githubusercontent.com/minnelab/MAIA/master/MAIA/configs/docker_versions.yaml",
    registry_path="",
    cluster_address="https://kubernetes.default.svc",
):
    cluster_config_dict = yaml.safe_load(Path(cluster_config).read_text())
    dev_distros = ["microk8s", "k0s"]

    if "storage_class" not in cluster_config_dict:
        if "k8s_distribution" in cluster_config_dict and cluster_config_dict["k8s_distribution"] in dev_distros:
            if cluster_config_dict["k8s_distribution"] == "microk8s":
                cluster_config_dict["storage_class"] = "microk8s-hostpath"
            elif cluster_config_dict["k8s_distribution"] == "k0s":
                cluster_config_dict["storage_class"] = "local-path"
        else:
            cluster_config_dict["storage_class"] = "local-path"
    # Docker Registry configuration where the images will be pushed
    registry_username = os.environ["docker_username"]
    registry_password = os.environ["docker_password"]
    registry_email = cluster_config_dict["ingress_resolver_email"]
    if "registry_server" in os.environ:
        registry_server = os.environ["registry_server"]
    else:
        registry_server = "registry." + cluster_config_dict["domain"]

    admin_group_id = os.environ["admin_group_ID"]
    docker_secret_name = f"{registry_server}{registry_path}".replace(".", "-").replace("/", "-").replace(":", "-")
    if docker_secret_name.endswith("-"):
        docker_secret_name = docker_secret_name[:-1]

    if build_version_file is not None:
        if build_version_file.startswith("https"):
            build_versions = yaml.safe_load(requests.get(build_version_file).text)
        else:
            build_versions = yaml.safe_load(Path(build_version_file).read_text())
    else:
        build_versions = {}

    xnat_env_vars = [
        "XNAT_VERSION=1.8.10",
        "XNAT_MIN_HEAP=256m",
        "XNAT_MAX_HEAP=4g",
        "XNAT_SMTP_ENABLED=false",
        "XNAT_SMTP_HOSTNAME=maia.se",
        "XNAT_SMTP_PORT=",
        "XNAT_SMTP_AUTH=",
        "XNAT_SMTP_USERNAME=",
        "XNAT_SMTP_PASSWORD=",
        "XNAT_DATASOURCE_ADMIN_PASSWORD=xnat123456789abcdef0",
        "XNAT_DATASOURCE_DRIVER=org.postgresql.Driver",
        "XNAT_DATASOURCE_NAME=xnat",
        "XNAT_DATASOURCE_USERNAME=xnat",
        "XNAT_DATASOURCE_PASSWORD=xnat",
        "XNAT_DATASOURCE_URL=jdbc:postgresql://xnat-db/xnat",
        "XNAT_ACTIVEMQ_URL=tcp://xnat-activemq:61616",
        "XNAT_ACTIVEMQ_USERNAME=write",
        "XNAT_ACTIVEMQ_PASSWORD=password",
        "TOMCAT_XNAT_FOLDER=ROOT",
        "XNAT_ROOT=/data/xnat",
        "XNAT_HOME=/data/xnat/home",
        "XNAT_EMAIL=maia-user@maia.se",
    ]

    registry_credentials = {
        "username": registry_username,
        "password": registry_password,
        "server": registry_server,
        "email": registry_email,
    }
    json_key_path = os.environ.get("JSON_KEY_PATH", None)

    if json_key_path is not None and "minnelab.github.io/MAIA" not in os.environ["MAIA_HELM_REPO_URL"]:
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

        config.load_config()
        create_helm_repo_secret_from_context(
            repo_name=f"maia-registry-{project_id}",
            argocd_namespace="argocd",
            helm_repo_config={
                "username": username,
                "password": password,
                "project": project_id,
                "url": os.environ["MAIA_HELM_REPO_URL"],
                "type": "helm",
                "name": f"maia-registry-{project_id}",
                "enableOCI": "true",
            },
        )
    helm_commands = []

    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-kube",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-kube",
            build_versions["maia-kube"],
            "docker/MAIA-Kube",
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-dashboard",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-dashboard",
            build_versions["maia-dashboard"],
            "dashboard",
            [f"BASE_IMAGE={registry_server}{registry_path}/maia-kube:{build_versions['maia-kube']}"],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace",
            build_versions["maia-workspace"],
            "docker/MAIA-Workspace",
            [f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace-base:{build_versions['maia-workspace-base']}"],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace-notebook",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace-notebook",
            build_versions["maia-workspace-notebook"],
            "docker/Notebooks/Base",
            [f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace:{build_versions['maia-workspace']}"],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace-notebook-ssh",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace-notebook-ssh",
            build_versions["maia-workspace-notebook-ssh"],
            "docker/Notebooks/SSH",
            [f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace-notebook:{build_versions['maia-workspace-notebook']}"],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-lab-pro",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-lab-pro",
            build_versions["maia-lab-pro"],
            "docker/Notebooks/Lab",
            [
                f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace-notebook-ssh-addons:{build_versions['maia-workspace-notebook-ssh-addons']}"
            ],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace-notebook-ssh-addons",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace-notebook-ssh-addons",
            build_versions["maia-workspace-notebook-ssh-addons"],
            "docker/Notebooks/Addons",
            [
                f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace-notebook-ssh:{build_versions['maia-workspace-notebook-ssh']}"
            ],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "monai-toolkit",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "monai-toolkit",
            build_versions["monai-toolkit"],
            "docker/Notebooks/MONAI-Toolkit",
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-xnat",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-xnat",
            build_versions["maia-xnat"],
            "docker/xnat",
            xnat_env_vars,
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-orthanc",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-orthanc",
            build_versions["maia-orthanc"],
            "docker/MAIA-Orthanc",
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-mlflow",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-mlflow",
            build_versions["maia-mlflow"],
            "docker/base",
            ["RUN_MLFLOW_SERVER=True"],
            registry_credentials=registry_credentials,
        )
    )

    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-filebrowser",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-filebrowser",
            build_versions["maia-filebrowser"],
            "docker/base",
            ["RUN_FILEBROWSER=True"],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace-base",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace-base",
            build_versions["maia-workspace-base"],
            "docker/MAIA-Workspace",
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-gpu-booking-admission-controller",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-gpu-booking-admission-controller",
            build_versions["maia-gpu-booking-admission-controller"],
            "docker/GPU_Booking_Admission_Controller",
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-gpu-booking-pod-terminator",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-gpu-booking-pod-terminator",
            build_versions["maia-gpu-booking-pod-terminator"],
            "docker/GPU_Booking_Pod_Terminator",
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace-base-notebook",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace-base-notebook",
            build_versions["maia-workspace-base-notebook"],
            "docker/Notebooks/Base",
            [f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace-base:{build_versions['maia-workspace-base']}"],
            registry_credentials=registry_credentials,
        )
    )
    helm_commands.append(
        deploy_maia_kaniko(
            "mkg-kaniko",
            config_folder,
            cluster_config_dict,
            "maia-workspace-base-notebook-ssh",
            project_id,
            registry_server + registry_path,
            docker_secret_name,
            "maia-workspace-base-notebook-ssh",
            build_versions["maia-workspace-base-notebook-ssh"],
            "docker/Notebooks/SSH",
            [
                f"BASE_IMAGE={registry_server}{registry_path}/maia-workspace-base-notebook:{build_versions['maia-workspace-base-notebook']}"
            ],
            registry_credentials=registry_credentials,
        )
    )

    for helm_command in helm_commands:
        cmd = [
            "helm",
            "upgrade",
            "--install",
            "--wait",
            "-n",
            helm_command["namespace"],
            helm_command["release"],
            helm_command["chart"],
            "--repo",
            helm_command["repo"],
            "--version",
            helm_command["version"],
            "--values",
            helm_command["values"],
        ]
        print(" ".join(cmd))

    if "MAIA_HELM_REPO_URL" not in os.environ:
        raise ValueError(
            "MAIA_HELM_REPO_URL environment variable not set. Please set this variable to the URL of the MAIA Helm repository for mkg-kaniko. Example: https://minnelab.github.io/MAIA/"  # noqa: B950
        )

    values = {
        "defaults": ["_self_"],
        "argo_namespace": os.environ["argocd_namespace"],
        "namespace": "mkg-kaniko",
        "admin_group_ID": admin_group_id,
        "destination_server": f"{cluster_address}",
        "sourceRepos": [os.environ["MAIA_HELM_REPO_URL"]],
        "dockerRegistryServer": "https://" + registry_server if "registry_server" not in os.environ else registry_server,
        "dockerRegistryUsername": registry_username,
        "dockerRegistryPassword": registry_password,
        "dockerRegistryEmail": registry_email,
        "dockerRegistrySecretName": docker_secret_name,
    }

    values["defaults"].extend(
        [
            {"maia_kube_values": "maia_kube_values"},
            {"maia_dashboard_values": "maia_dashboard_values"},
            {"maia_workspace_values": "maia_workspace_values"},
            {"maia_workspace_notebook_values": "maia_workspace_notebook_values"},
            {"maia_workspace_notebook_ssh_values": "maia_workspace_notebook_ssh_values"},
            {"maia_workspace_notebook_ssh_addons_values": "maia_workspace_notebook_ssh_addons_values"},
            {"maia_lab_pro_values": "maia_lab_pro_values"},
            {"monai_toolkit_values": "monai_toolkit_values"},
            {"maia_xnat_values": "maia_xnat_values"},
            {"maia_orthanc_values": "maia_orthanc_values"},
            {"maia_mlflow_values": "maia_mlflow_values"},
        ]
    )
    values["defaults"].extend(
        [
            {"maia_workspace_base_values": "maia_workspace_base_values"},
            {"maia_filebrowser_values": "maia_filebrowser_values"},
            {"maia_workspace_base_notebook_values": "maia_workspace_base_notebook_values"},
            {"maia_workspace_base_notebook_ssh_values": "maia_workspace_base_notebook_ssh_values"},
            {"maia_gpu_booking_admission_controller_values": "maia_gpu_booking_admission_controller_values"},
            {"maia_gpu_booking_pod_terminator_values": "maia_gpu_booking_pod_terminator_values"},
        ]
    )
    Path(config_folder).joinpath(project_id).mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(project_id, "values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(values))

    if not os.path.isabs(config_folder):
        config_folder = os.path.abspath(config_folder)
    initialize_config_dir(config_dir=str(Path(config_folder).joinpath(project_id)), job_name=project_id)
    cfg = hydra_compose("values.yaml")
    OmegaConf.save(
        cfg,
        str(Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml")),
        resolve=True,
    )

    print("Installing MAIA Build Docker")

    project_chart = os.environ["docker_build_project_chart"]
    project_repo = os.environ["docker_build_project_repo"]
    project_version = os.environ["docker_build_project_version"]
    cmd = [
        "helm",
        "upgrade",
        "--install",
        "--wait",
        "-n",
        os.environ["argocd_namespace"],
        project_id,
        project_chart,
        "--repo",
        project_repo,
        "--version",
        project_version,
        "--values",
        str(Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml")),
    ]
    print(" ".join(cmd))

    asyncio.run(
        install_maia_project(
            project_id,
            Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml"),
            os.environ["argocd_namespace"],
            project_chart,
            project_repo=project_repo,
            project_version=project_version,
            json_key_path=json_key_path,
        )
    )


if __name__ == "__main__":
    main()
