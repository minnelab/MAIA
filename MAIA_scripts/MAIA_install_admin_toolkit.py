#!/usr/bin/env python
from __future__ import annotations

import asyncio
import datetime
import os
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent

import click
import json
import subprocess
from MAIA.kubernetes_utils import create_helm_repo_secret_from_context
import yaml
from hydra import compose as hydra_compose
from hydra import initialize_config_dir
from omegaconf import OmegaConf
from pyhelm3 import Client

import MAIA
from MAIA.maia_admin import (
    create_harbor_values,
    create_keycloak_values,
    create_maia_admin_toolkit_values,
    create_maia_dashboard_values,
    install_maia_project,
)
from MAIA.maia_core import create_rancher_values
from loguru import logger

version = MAIA.__version__


TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())

DESC = dedent(
    """
    Script to Install MAIA Admin Toolkit to a Kubernetes cluster from ArgoCD. The specific MAIA configuration
    is specified by setting the corresponding ``--maia-config-file``, and the cluster configuration is
    specified by setting the corresponding ``--cluster-config``.
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


async def verify_installed_maia_admin_toolkit(project_id, namespace):
    print(os.environ["KUBECONFIG"])
    client = Client(kubeconfig=os.environ["KUBECONFIG"])

    try:
        revision = await client.get_current_revision(project_id, namespace=namespace)
    except Exception as e:
        print(f"An error occurred: {e}")
        return -1
    chart_metadata = await revision.chart_metadata()
    print(
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
    install_maia_admin_toolkit(cluster_config, config_folder)


def install_maia_admin_toolkit(cluster_config, config_folder):
    cluster_config_dict = yaml.safe_load(Path(cluster_config).read_text())
    private_maia_registry = os.environ.get("MAIA_PRIVATE_REGISTRY", None)
    admin_group_id = os.environ["admin_group_ID"]
    project_id = "maia-admin"

    cluster_address = "https://kubernetes.default.svc"  # TODO: Change this to make it configurable

    dev_distros = ["microk8s", "k0s"]
    if "ingress_class" not in cluster_config_dict:
        if "k8s_distribution" in cluster_config_dict and cluster_config_dict["k8s_distribution"] in dev_distros:
            cluster_config_dict["ingress_class"] = "maia-core-traefik"
        else:
            cluster_config_dict["ingress_class"] = "nginx"

    if "storage_class" not in cluster_config_dict:
        if "k8s_distribution" in cluster_config_dict and cluster_config_dict["k8s_distribution"] in dev_distros:
            if cluster_config_dict["k8s_distribution"] == "microk8s":
                cluster_config_dict["storage_class"] = "microk8s-hostpath"
            elif cluster_config_dict["k8s_distribution"] == "k0s":
                cluster_config_dict["storage_class"] = "local-path"
        else:
            cluster_config_dict["storage_class"] = "local-path"

    helm_commands = []

    helm_commands.append(create_harbor_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_keycloak_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_rancher_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_maia_admin_toolkit_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_maia_dashboard_values(config_folder, project_id, cluster_config_dict))

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
            print(" ".join(cmd))

    values = {
        "defaults": [
            "_self_",
            {"harbor_values": "harbor_values"},
            {"keycloak_values": "keycloak_values"},
            {"maia_admin_toolkit_values": "maia_admin_toolkit_values"},
            {"maia_dashboard_values": "maia_dashboard_values"},
            {"rancher_values": "rancher_values"},
        ],
        "argo_namespace": os.environ["argocd_namespace"],
        "admin_group_ID": admin_group_id,
        "destination_server": f"{cluster_address}",
        "sourceRepos": [
            "https://minnelab.github.io/MAIA/",
            "https://helm.goharbor.io",
            "https://charts.bitnami.com/bitnami",
            "https://releases.rancher.com/server-charts/latest",
        ],
    }
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

    revision = asyncio.run(verify_installed_maia_admin_toolkit(project_id, os.environ["argocd_namespace"]))

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
        print("Installing MAIA Admin Toolkit")

        project_chart = os.environ["admin_project_chart"]
        project_repo = os.environ["admin_project_repo"]
        project_version = os.environ["admin_project_version"]
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
        print("Upgrading MAIA Admin Toolkit")

        project_chart = os.environ["admin_project_chart"]
        project_repo = os.environ["admin_project_repo"]
        project_version = os.environ["admin_project_version"]
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
