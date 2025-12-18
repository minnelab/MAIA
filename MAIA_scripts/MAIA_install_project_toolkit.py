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
import hydra
import yaml
from hydra import compose as hydra_compose
from hydra import initialize_config_dir
from omegaconf import OmegaConf
from pyhelm3 import Client

import MAIA
from MAIA.maia_admin import (
    create_filebrowser_values,
    create_maia_namespace_values,
    generate_minio_configs,
    generate_mlflow_configs,
    generate_mysql_configs,
    get_maia_toolkit_apps,
    install_maia_project,
)
from MAIA.maia_fn import (
    deploy_mlflow,
    deploy_mysql,
    deploy_orthanc,
    copy_certificate_authority_secret,
)
from MAIA_scripts.MAIA_create_JupyterHub_config import create_jupyterhub_config_api

version = MAIA.__version__


TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())

DESC = dedent(
    """
    Script to deploy a MAIA Project Toolkit to a Kubernetes cluster. The target cluster is specified by setting
    the corresponding ``--cluster-config``, while the project-related configuration is specified with
    ``--project-config-file``. The necessary MAIA Configuration files should be found in ``--config-folder``.
    """  # noqa: E501
)
EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --project-config-file /PATH/TO/form.yaml --cluster-config /PATH/TO/cluster.yaml
        --config-folder /PATH/TO/config_folder
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--project-config-file",
        type=str,
        required=True,
        help="YAML configuration file used to extract the project configuration.",
    )

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
        "--minimal",
        type=str,
        required=False,
        help="Optional flag to only deploy JupyterHub in the MAIA namespace.",
    )

    pars.add_argument("--no-argocd", action="store_true", help="Do not deploy with ArgoCD.")

    pars.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return pars


async def verify_installed_maia_toolkit(project_id, namespace, get_chart_metadata=True):
    client = Client(kubeconfig=os.environ["KUBECONFIG"])

    try:
        revision = await client.get_current_revision(project_id, namespace=namespace)
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Project not found")
        return -1
    if get_chart_metadata:
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
    return {
        "revision": revision.revision,
        "release_name": revision.release.name,
        "release_namespace": revision.release.namespace,
        "status": str(revision.status),
    }


@click.command()
@click.option("--project-config-file", type=str)
@click.option("--cluster-config", type=str)
@click.option("--no-minimal", is_flag=True)
@click.option("--config-folder", type=str)
@click.option("--no-argocd", is_flag=True)
def main(
    project_config_file,
    cluster_config,
    config_folder,
    no_minimal=False,
    no_argocd=False,
):
    deploy_maia_toolkit(project_config_file, cluster_config, config_folder, no_minimal, no_argocd)


def deploy_maia_toolkit(
    project_config_file,
    cluster_config,
    config_folder,
    no_minimal=False,
    no_argocd=False,
):
    project_form_dict = yaml.safe_load(Path(project_config_file).read_text())

    cluster_config_dict = yaml.safe_load(Path(cluster_config).read_text())

    deploy_maia_toolkit_api(project_form_dict, cluster_config_dict, config_folder, not no_minimal, no_argocd)


def deploy_maia_toolkit_api(
    project_form_dict,
    cluster_config_dict,
    config_folder,
    minimal=True,
    no_argocd=False,
    redeploy_enabled=True,
    return_values_only=False,
):
    # Override cluster config with project-specific configuration, if found
    namespace_id = project_form_dict["group_ID"].lower().replace("_", "-")
    if f"{namespace_id}-cluster-config" in cluster_config_dict:
        for key, value in cluster_config_dict[f"{namespace_id}-cluster-config"].items():
            cluster_config_dict[key] = value
            if key == "env":
                for env_key, env_value in value.items():
                    os.environ[env_key + "_" + namespace_id] = env_value
    project_form_dict["extra_configs"] = {}
    if "enable_cifs_" + namespace_id in os.environ:
        project_form_dict["extra_configs"]["enable_cifs"] = os.environ["enable_cifs_" + namespace_id]
    else:
        project_form_dict["extra_configs"]["enable_cifs"] = False

    if "MAIA_PRIVATE_REGISTRY_" + namespace_id in os.environ:
        private_maia_registry = os.environ["MAIA_PRIVATE_REGISTRY_" + namespace_id]
    else:
        private_maia_registry = os.environ.get("MAIA_PRIVATE_REGISTRY", None)

    group_id = project_form_dict["group_ID"]
    Path(config_folder).joinpath(project_form_dict["group_ID"]).mkdir(parents=True, exist_ok=True)

    namespace = project_form_dict["group_ID"].lower().replace("_", "-")

    helm_commands = []

    mlflow_configs = generate_mlflow_configs(namespace=group_id.lower().replace("_", "-"))

    if not minimal:
        minio_configs = generate_minio_configs(namespace=group_id.lower().replace("_", "-"))

        mysql_configs = generate_mysql_configs(namespace=group_id.lower().replace("_", "-"))

        project_form_dict["minio_access_key"] = minio_configs["console_access_key"]
        project_form_dict["minio_secret_key"] = minio_configs["console_secret_key"]
    else:
        minio_configs = None
        mysql_configs = None
        project_form_dict["minio_access_key"] = "N/A"
        project_form_dict["minio_secret_key"] = "N/A"

    print("Creating MAIA Project Namespace")
    if no_argocd:
        print("No ArgoCD deployment")
    else:
        print("ArgoCD deployment")

    helm_commands.append(
        create_maia_namespace_values(
            project_form_dict,
            cluster_config_dict,
            config_folder,
            minio_configs=minio_configs,
            mlflow_configs=mlflow_configs,
        )
    )

    with open(Path(config_folder).joinpath(group_id, "maia_namespace_values", "namespace_values.yaml")) as f:
        maia_namespace_values = yaml.safe_load(f)
        project_form_dict["ssh_users"] = []
        for user in maia_namespace_values["users"]:
            project_form_dict["ssh_users"].append(
                {
                    "username": user["jupyterhub_username"].replace("-2d", "-").replace("-40", "@").replace("-2e", "."),
                    "ssh_port": user["sshPort"],
                }
            )

    copy_certificate_authority_secret(namespace)

    helm_commands.append(create_jupyterhub_config_api(project_form_dict, cluster_config_dict, config_folder, minimal=minimal))

    helm_commands.append(
        create_filebrowser_values(
            project_form_dict,
            cluster_config_dict,
            config_folder,
            mlflow_configs=mlflow_configs,
            mount_cifs=project_form_dict["extra_configs"]["enable_cifs"],
        )
    )
    if not minimal:
        # helm_commands.append(deploy_oauth2_proxy(cluster_config_dict, project_form_dict, config_folder))

        helm_commands.append(
            deploy_mysql(
                cluster_config_dict,
                project_form_dict,
                config_folder,
                mysql_configs=mysql_configs,
            )
        )
        helm_commands.append(
            deploy_mlflow(
                cluster_config_dict,
                project_form_dict,
                config_folder,
                mysql_config=mysql_configs,
                minio_config=minio_configs,
            )
        )

        helm_commands.append(deploy_orthanc(cluster_config_dict, project_form_dict, config_folder))

    if "JSON_KEY_PATH_" + namespace_id in os.environ:
        json_key_path = os.environ["JSON_KEY_PATH_" + namespace_id]
    else:
        json_key_path = os.environ.get("JSON_KEY_PATH", None)
    for helm_command in helm_commands:
        if not helm_command["repo"].startswith("http") and not Path(helm_command["repo"]).exists() and not return_values_only:
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
                input=password,
                text=True,
            )

            print(
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
            print(
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
            print(" ".join(cmd))
        else:
            cmd = [
                "helm",
                "upgrade",
                "--install",
                # "--wait",
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
        if no_argocd and not return_values_only:
            subprocess.Popen(cmd)

    destination_cluster_address = cluster_config_dict["argocd_destination_cluster_address"]

    values = {
        "defaults": [
            "_self_",
            {"maia_namespace_values": "namespace_values"},
            {"jupyterhub_values": "jupyterhub_values"},
            {"jupyterhub_chart_info": "jupyterhub_chart_info"},
        ],
        "argo_namespace": os.environ["argocd_namespace"],
        "group_ID": f"MAIA:{group_id}",
        "destination_server": f"{destination_cluster_address}",
        "sourceRepos": [
            "https://minnelab.github.io/MAIA/",
            "https://hub.jupyter.org/helm-chart/",
            "https://oauth2-proxy.github.io/manifests",
        ],
    }
    values["defaults"].append({"maia_filebrowser_values": "maia_filebrowser_values"})
    if private_maia_registry:
        values["sourceRepos"].append(private_maia_registry)
    if not minimal:
        values["defaults"].append({"mlflow_values": "mlflow_values"})
        values["defaults"].append({"mysql_values": "mysql_values"})
        # values["defaults"].append({"oauth2_proxy_values": "oauth2_proxy_values"})
        values["defaults"].append({"orthanc_values": "orthanc_values"})

    with open(Path(config_folder).joinpath(group_id, "values.yaml"), "w") as f:
        f.write(OmegaConf.to_yaml(values))

    try:
        initialize_config_dir(config_dir=str(Path(config_folder).joinpath(group_id)), job_name=group_id)
    except Exception as e:
        print(f"An error occurred: {e}")
        hydra.core.global_hydra.GlobalHydra.instance().clear()
        initialize_config_dir(config_dir=str(Path(config_folder).joinpath(group_id)), job_name=group_id)
    cfg = hydra_compose("values.yaml")
    OmegaConf.save(
        cfg,
        str(Path(config_folder).joinpath(group_id, f"{group_id}_values.yaml")),
        resolve=True,
    )

    project_id = namespace

    if no_argocd:
        if return_values_only:
            with open(Path(config_folder).joinpath(group_id, f"{group_id}_values.yaml")) as f:
                return yaml.safe_load(f)
        else:
            return
    revision = asyncio.run(verify_installed_maia_toolkit(project_id, os.environ["argocd_namespace"]))

    if revision == -1 or redeploy_enabled:
        print("Installing MAIA Workspace")

        project_chart = os.environ["maia_project_chart"]
        project_repo = os.environ["maia_project_repo"]
        project_version = os.environ["maia_project_version"]
        json_key_path = os.environ.get("JSON_KEY_PATH", None)

        print(f"Installing MAIA Project Toolkit {project_chart} from {project_repo} version {project_version}")
        print(f"Using JSON key path: {json_key_path}")
        msg = asyncio.run(
            install_maia_project(
                group_id,
                Path(config_folder).joinpath(group_id, f"{group_id}_values.yaml"),
                os.environ["argocd_namespace"],
                project_chart,
                project_repo=project_repo,
                project_version=project_version,
                json_key_path=json_key_path,
            )
        )
        return msg
    else:
        argocd_host = os.environ["argocd_host"]
        password = os.environ["ARGOCD_PASSWORD"]
        print("MAIA Workspace already installed")
        get_maia_toolkit_apps(group_id, password, argocd_host)


# The `if __name__ == "__main__":` block in Python is used to check whether the current script is
# being run directly by the Python interpreter or if it is being imported as a module into another
# script.
if __name__ == "__main__":
    main()
