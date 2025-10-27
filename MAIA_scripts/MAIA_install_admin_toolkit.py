#!/usr/bin/env python
from __future__ import annotations

import asyncio
import datetime
import os
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent

import click
import yaml
from hydra import compose as hydra_compose
from hydra import initialize_config_dir
from loguru import logger
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
        {filename} --maia-config-file /PATH/TO/maia_config.yaml --cluster-config /PATH/TO/clusyer_config.yaml
        --config-folder /PATH/TO/config_folder
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--maia-config-file", type=str, required=True, help="YAML configuration file used to extract MAIA configuration."
    )

    pars.add_argument(
        "--cluster-config", type=str, required=True, help="YAML configuration file used to extract the cluster configuration."
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

    logger.info(f"KUBECONFIG: {os.environ['KUBECONFIG']}")
    client = Client(kubeconfig=os.environ["KUBECONFIG"])

    try:
        revision = await client.get_current_revision(project_id, namespace=namespace)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return -1
    chart_metadata = await revision.chart_metadata()
    logger.info(
        f"Release: {revision.release.name}, Namespace: {revision.release.namespace}, "
        f"Revision: {revision.revision}, Status: {revision.status}, "
        f"Chart: {chart_metadata.name}, Version: {chart_metadata.version}"
    )
    return revision.revision


@click.command()
@click.option("--maia-config-file", type=str)
@click.option("--cluster-config", type=str)
@click.option("--config-folder", type=str)
def main(maia_config_file, cluster_config, config_folder):
    install_maia_admin_toolkit(maia_config_file, cluster_config, config_folder)


def install_maia_admin_toolkit(maia_config_file, cluster_config, config_folder):

    maia_config_dict = yaml.safe_load(Path(maia_config_file).read_text())

    cluster_config_dict = yaml.safe_load(Path(cluster_config).read_text())

    admin_group_id = maia_config_dict["admin_group_ID"]
    project_id = "maia-admin"

    cluster_address = "https://kubernetes.default.svc"  # TODO: Change this to make it configurable

    helm_commands = []

    helm_commands.append(create_harbor_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_keycloak_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(create_rancher_values(config_folder, project_id, cluster_config_dict))
    helm_commands.append(
        create_maia_admin_toolkit_values(config_folder, project_id, cluster_config_dict, maia_config_dict=maia_config_dict)
    )
    helm_commands.append(
        create_maia_dashboard_values(config_folder, project_id, cluster_config_dict, maia_config_dict=maia_config_dict)
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
        logger.debug(f"Helm command: {' '.join(cmd)}")

    values = {
        "defaults": [
            "_self_",
            {"harbor_values": "harbor_values"},
            {"keycloak_values": "keycloak_values"},
            {"maia_admin_toolkit_values": "maia_admin_toolkit_values"},
            {"maia_dashboard_values": "maia_dashboard_values"},
            {"rancher_values": "rancher_values"},
        ],
        "argo_namespace": maia_config_dict["argocd_namespace"],
        "admin_group_ID": admin_group_id,
        "destination_server": f"{cluster_address}",
        "sourceRepos": [
            "https://kthcloud.github.io/MAIA/",
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
    OmegaConf.save(cfg, str(Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml")), resolve=True)

    revision = asyncio.run(verify_installed_maia_admin_toolkit(project_id, maia_config_dict["argocd_namespace"]))

    if revision == -1:
        logger.info("Installing MAIA Admin Toolkit")

        project_chart = maia_config_dict["admin_project_chart"]
        project_repo = maia_config_dict["admin_project_repo"]
        project_version = maia_config_dict["admin_project_version"]
        asyncio.run(
            install_maia_project(
                project_id,
                Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml"),
                maia_config_dict["argocd_namespace"],
                project_chart,
                project_repo=project_repo,
                project_version=project_version,
            )
        )
    else:
        logger.info("Upgrading MAIA Admin Toolkit")

        project_chart = maia_config_dict["admin_project_chart"]
        project_repo = maia_config_dict["admin_project_repo"]
        project_version = maia_config_dict["admin_project_version"]
        asyncio.run(
            install_maia_project(
                project_id,
                Path(config_folder).joinpath(project_id, f"{project_id}_values.yaml"),
                maia_config_dict["argocd_namespace"],
                project_chart,
                project_repo=project_repo,
                project_version=project_version,
            )
        )


if __name__ == "__main__":
    main()
