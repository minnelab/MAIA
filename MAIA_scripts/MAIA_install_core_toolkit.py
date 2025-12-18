#!/usr/bin/env python
from __future__ import annotations

import asyncio
import datetime
import json
import os
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent

import click
import yaml
from hydra import compose as hydra_compose
from hydra import initialize_config_dir
from omegaconf import OmegaConf
from pyhelm3 import Client

import MAIA
from MAIA.kubernetes_utils import create_helm_repo_secret_from_context
from MAIA.maia_admin import (
    create_loginapp_values,
    create_minio_operator_values,
    install_maia_project,
)
from MAIA.maia_core import (
    create_cert_manager_values,
    create_core_toolkit_values,
    create_gpu_booking_values,
    create_gpu_operator_values,
    create_ingress_nginx_values,
    create_loki_values,
    create_metallb_values,
    create_nfs_server_provisioner_values,
    create_prometheus_values,
    create_tempo_values,
    create_traefik_values,
    create_metrics_server_values,
)
from loguru import logger

version = MAIA.__version__


TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())

DESC = dedent(
    """
    Script to Install MAIA Core Toolkit to a Kubernetes cluster from ArgoCD. The specific MAIA configuration
    is specified by setting the corresponding ``--maia-config-file``, and the cluster configuration is specified
    by setting the corresponding ``--cluster-config``.
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

    pars.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return pars


async def verify_installed_maia_core_toolkit(project_id, namespace):
    client = Client(kubeconfig=os.environ["KUBECONFIG"])

    try:
        revision = await client.get_current_revision(project_id, namespace=namespace)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.error("Project not found")
        return -1
    chart_metadata = await revision.chart_metadata()
    logger.debug(
        revision.release.name,
        revision.release.namespace,
        revision.revision,
        str(revision.status),
        chart_metadata.name,
        chart_metadata.version,
    )
    return revision.revision


@click.command()
@click.option("--cluster-config", type=str)
@click.option("--config-folder", type=str)
def main(cluster_config, config_folder):
    install_maia_core_toolkit(cluster_config, config_folder)


def install_maia_core_toolkit(cluster_config, config_folder):
    private_maia_registry = os.environ.get("MAIA_PRIVATE_REGISTRY", None)

    cluster_config_dict = yaml.safe_load(Path(cluster_config).read_text())

    admin_group_id = os.environ["admin_group_ID"]
    project_id = "maia-core"

    if "argocd_destination_cluster_address" in cluster_config_dict and not cluster_config_dict[
        "argocd_destination_cluster_address"
    ].endswith("/k8s/clusters/local"):
        cluster_address = cluster_config_dict["argocd_destination_cluster_address"]
        if cluster_config_dict["argocd_destination_cluster_address"] != "https://kubernetes.default.svc":
            project_id += f"-{cluster_config_dict['cluster_name']}"
    else:
        cluster_address = "https://kubernetes.default.svc"

    dev_distros = ["microk8s", "k0s"]
    if "ingress_class" not in cluster_config_dict:
        if "k8s_distribution" in cluster_config_dict and cluster_config_dict["k8s_distribution"] in dev_distros:
            cluster_config_dict["ingress_class"] = "maia-core-traefik"
        else:
            cluster_config_dict["ingress_class"] = "nginx"

    helm_commands = []
    helm_commands.append(create_prometheus_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_metrics_server_values(config_folder, project_id))
    helm_commands.append(create_loki_values(config_folder, project_id))
    helm_commands.append(create_tempo_values(config_folder, project_id))
    helm_commands.append(create_core_toolkit_values(config_folder, project_id, cluster_config_dict))

    # Allow either traefik or nginx ingress controller
    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        helm_commands.append(create_traefik_values(config_folder, project_id, cluster_config_dict))
    else:
        helm_commands.append(create_ingress_nginx_values(config_folder, project_id))

    helm_commands.append(create_metallb_values(config_folder, project_id))
    helm_commands.append(create_cert_manager_values(config_folder, project_id))
    helm_commands.append(create_gpu_operator_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_nfs_server_provisioner_values(config_folder, project_id, cluster_config_dict))

    helm_commands.append(create_loginapp_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_minio_operator_values(config_folder, project_id))

    if "MAIA_DASHBOARD_DOMAIN" in os.environ and "dashboard_api_secret" in os.environ:
        helm_commands.append(create_gpu_booking_values(config_folder, project_id))
    json_key_path = os.environ.get("JSON_KEY_PATH", None)
    for helm_command in helm_commands:
        if (
            not helm_command["repo"].startswith("http") and not Path(helm_command["repo"]).exists()
        ):  # If the repo is not a HTTP URL, it is an OCI registry (i.e. Harbor)
            original_repo = helm_command["repo"]
            helm_command["repo"] = f"oci://{helm_command['repo']}"
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

            subprocess.run(
                [
                    "helm",
                    "registry",
                    "login",
                    original_repo,
                    "--username",
                    username,
                    "--password-stdin",
                ],
                input=password.encode(),
                check=True,
            )
            logger.debug(
                " ".join(
                    [
                        "helm",
                        "registry",
                        "login",
                        original_repo,
                        "--username",
                        username,
                        "--password-stdin",
                    ]
                )
            )
            subprocess.run(
                [
                    "helm",
                    "pull",
                    helm_command["repo"] + "/" + helm_command["chart"],
                    "--version",
                    helm_command["version"],
                    "--destination",
                    "/tmp",
                ]
            )
            logger.debug(
                " ".join(
                    [
                        "helm",
                        "pull",
                        helm_command["repo"] + "/" + helm_command["chart"],
                        "--version",
                        helm_command["version"],
                        "--destination",
                        "/tmp",
                    ]
                )
            )
            cmd = [
                "helm",
                "upgrade",
                "--install",
                # "--wait",
                "-n",
                helm_command["namespace"],
                helm_command["release"],
                "/tmp/" + helm_command["chart"] + "-" + helm_command["version"] + ".tgz",
                "--values",
                helm_command["values"],
            ]
            logger.debug(" ".join(cmd))
        else:
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
            logger.debug(" ".join(cmd))

    values = {
        "defaults": [
            "_self_",
            {"prometheus_values": "prometheus_values"},
            {"metrics_server_values": "metrics_server_values"},
            {"loki_values": "loki_values"},
            {"tempo_values": "tempo_values"},
            {"core_toolkit_values": "core_toolkit_values"},
            {"metallb_values": "metallb_values"},
            {"cert_manager_values": "cert_manager_values"},
            {"loginapp_values": "loginapp_values"},
            {"minio_operator_values": "minio_operator_values"},
            {"gpu_operator_values": "gpu_operator_values"},
            {"nfs_provisioner_values": "nfs_provisioner_values"},
            {"cert_manager_chart_info": "cert_manager_chart_info"},
            {"gpu_booking_values": "gpu_booking_values"},
        ],
        "argo_namespace": os.environ["argocd_namespace"],
        "admin_group_ID": admin_group_id,
        "destination_server": f"{cluster_address}",
        "sourceRepos": [
            "https://prometheus-community.github.io/helm-charts",
            "https://grafana.github.io/helm-charts",
            "https://minnelab.github.io/MAIA/",
            "https://traefik.github.io/charts",
            "https://metallb.github.io/metallb",
            "https://charts.jetstack.io",
            "https://helm.ngc.nvidia.com/nvidia",
            "https://kubernetes.github.io/ingress-nginx",
            "https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/",
            "https://storage.googleapis.com/loginapp-releases/charts/",
            "https://operator.min.io",
            "https://kubernetes-sigs.github.io/metrics-server/",
        ],
    }
    if private_maia_registry is not None:
        values["sourceRepos"].append(private_maia_registry)
    if cluster_config_dict["ingress_class"] == "maia-core-traefik":
        values["defaults"].append({"traefik_values": "traefik_values"})
    else:
        values["defaults"].append({"ingress_nginx_values": "ingress_nginx_values"})
    Path(config_folder).joinpath(project_id).mkdir(parents=True, exist_ok=True)

    with open(Path(config_folder).joinpath(project_id, "values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(values))

    initialize_config_dir(config_dir=str(Path(config_folder).joinpath(project_id)), job_name=project_id)
    cfg = hydra_compose("values.yaml")
    OmegaConf.save(
        cfg,
        str(Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml")),
        resolve=True,
    )

    revision = asyncio.run(verify_installed_maia_core_toolkit(project_id, os.environ["argocd_namespace"]))

    if json_key_path is not None:
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
        create_helm_repo_secret_from_context(
            repo_name=f"maia-private-registry-{project_id}",
            argocd_namespace=os.environ["argocd_namespace"],
            helm_repo_config={
                "username": username,
                "password": password,
                "project": project_id,
                "url": private_maia_registry,
                "type": "helm",
                "name": f"maia-private-registry-{project_id}",
                "enableOCI": "true",
            },
        )
    if revision == -1:
        logger.info("Installing MAIA Core Toolkit")

        project_chart = os.environ["core_project_chart"]
        project_repo = os.environ["core_project_repo"]
        project_version = os.environ["core_project_version"]

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
        logger.debug(" ".join(cmd))
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
    else:
        logger.info("Upgrading MAIA Core Toolkit")

        project_chart = os.environ["core_project_chart"]
        project_repo = os.environ["core_project_repo"]
        project_version = os.environ["core_project_version"]
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

    # for app in get_maia_toolkit_apps(project_id, os.environ["ARGOCD_PASSWORD"], os.environ["argocd_host"]):
    #    sync_argocd_app(project_id, app["name"], app["version"], os.environ["argocd_host"], os.environ["ARGOCD_PASSWORD"])


if __name__ == "__main__":
    main()
