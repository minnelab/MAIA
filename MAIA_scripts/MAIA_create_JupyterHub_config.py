#!/usr/bin/env python


from __future__ import annotations

import base64
import datetime
import os
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from textwrap import dedent

import click
import yaml
from minio import Minio
from omegaconf import OmegaConf
from types import SimpleNamespace

from MAIA.kubernetes_utils import get_minio_shareable_link
import MAIA

version = MAIA.__version__

TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())

DESC = dedent(
    """
    Script to deploy the JupyterHub helm chart to a Kubernetes cluster. The target cluster is specified by setting the correspondin
    ``--cluster--config-file``, while the namespace-related configuration is specified with ``--form``.
    """  # noqa: E501
)
EPILOG = dedent(
    """
    Example call:
    ::
        {filename}  --form /PATH/TO/form.yaml --cluster-config-file /PATH/TO/cluster.yaml
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def get_arg_parser():
    pars = ArgumentParser(description=DESC, epilog=EPILOG, formatter_class=RawTextHelpFormatter)

    pars.add_argument(
        "--form",
        type=str,
        required=True,
        help="YAML configuration file used to extract the namespace configuration.",
    )
    pars.add_argument(
        "--cluster-config-file",
        type=str,
        required=True,
        help="YAML configuration file used to extract the cluster configuration.",
    )

    pars.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return pars


@click.command()
@click.option("--form", type=str)
@click.option("--cluster-config-file", type=str)
@click.option("--no-minimal", is_flag=True, default=False)
def create_jupyterhub_config(form, cluster_config_file, no_minimal):
    create_jupyterhub_config_api(form, cluster_config_file, minimal=not no_minimal)


def create_jupyterhub_config_api(form, cluster_config_file, config_folder=None, minimal=True):
    if isinstance(cluster_config_file, dict):
        cluster_config = cluster_config_file
    else:
        with open(cluster_config_file, "r") as f:
            cluster_config = yaml.safe_load(f)

    if isinstance(form, dict):
        user_form = form
    else:
        with open(form, "r") as f:
            user_form = yaml.safe_load(f)

    storage_class = cluster_config["storage_class"]

    traefik_resolver = None
    if "traefik_resolver" in cluster_config:
        traefik_resolver = cluster_config["traefik_resolver"]

    nginx_cluster_issuer = None
    if "nginx_cluster_issuer" in cluster_config:
        nginx_cluster_issuer = cluster_config["nginx_cluster_issuer"]

    hub_storage_class = None
    if "hub_storage_class" in cluster_config:
        hub_storage_class = cluster_config["hub_storage_class"]
    else:
        hub_storage_class = cluster_config["shared_storage_class"]

    hub_image = None
    hub_tag = None
    if "hub_image" in os.environ:
        hub_image = os.environ["hub_image"]
        hub_tag = os.environ["hub_tag"]
    namespace = user_form["group_ID"].lower().replace("_", "-")
    if "hub_image_" + namespace in os.environ:
        hub_image = os.environ["hub_image_" + namespace]
        hub_tag = os.environ["hub_tag_" + namespace]

    base_url = None
    if "base_url" in os.environ:
        base_url = os.environ["base_url"]
    if "base_url_" + namespace in os.environ:
        base_url = os.environ["base_url_" + namespace]

    keycloak = None

    if (
        "keycloak_client_id" in os.environ
        and "keycloak_client_secret" in os.environ
        and "keycloak_authorize_url" in os.environ
        and "keycloak_token_url" in os.environ
        and "keycloak_userdata_url" in os.environ
    ):
        keycloak = {
            "client_id": os.environ["keycloak_client_id"],
            "client_secret": os.environ["keycloak_client_secret"],
            "authorize_url": os.environ["keycloak_authorize_url"],
            "token_url": os.environ["keycloak_token_url"],
            "userdata_url": os.environ["keycloak_userdata_url"],
        }

    namespace = user_form["group_ID"].lower().replace("_", "-")
    group_subdomain = user_form["group_subdomain"]
    team_id = user_form["group_ID"]
    resources_limits = user_form["resources_limits"]

    gpu_request = 0
    if "gpu_request" in user_form:
        gpu_request = int(user_form["gpu_request"])

    domain = cluster_config["domain"]

    if "url_type" in cluster_config:
        if cluster_config["url_type"] == "subdomain":
            hub_address = f"{group_subdomain}.{domain}"
        elif cluster_config["url_type"] == "subpath":
            hub_address = domain
        else:
            hub_address = None

    admins = cluster_config.get("admins", [])

    # Used for CIFS mount
    extra_host_volumes = []

    extra_volumes = [
        {
            "name": "jupyterhub-shared",
            "pvc-name": "shared",
            "mount-path": "/home/maia-user/shared",
        }
    ]

    jh_helm_template = {
        "resource": {
            "helm_release": {
                "jupyterhub": {
                    "name": "jupyterhub-{}".format(namespace.lower()),
                    "repository": "https://hub.jupyter.org/helm-chart/",
                    "chart": "jupyterhub",
                    "version": "3.1.0",
                    "namespace": namespace.lower(),
                    "create_namespace": False,
                }
            }
        }
    }

    jh_template = {
        "cull": {"enabled": False},
        "ingress": {
            "enabled": True,
            "hosts": [hub_address],
            "annotations": {},
            "tls": [{"hosts": [hub_address]}],
        },
        "hub": {
            "config": {
                "GenericOAuthenticator": {
                    "login_service": "MAIA Account",
                    "username_claim": "preferred_username",
                    "scope": ["openid", "profile", "email"],
                    "userdata_params": {"state": "state"},
                    "claim_groups_key": "groups",
                    "allowed_groups": [f"MAIA:{team_id}"],
                    "admin_groups": ["MAIA:admin"],
                    "tls_verify": False,
                    "tls_ca_file": "/usr/local/share/ca-certificates/kubernetes-ca.crt",
                    "http_request_kwargs": {"ca_certs": "/usr/local/share/ca-certificates/kubernetes-ca.crt"},
                },
                "JupyterHub": {
                    "admin_access": True,
                    "authenticator_class": "generic-oauth",
                },
                "Authenticator": {
                    "admin_users": admins,
                    "allowed_users": user_form["users"],
                },
            }
        },
        "singleuser": {
            "startTimeout": 7200,
            "allowPrivilegeEscalation": True,
            "uid": 1000,
            "networkPolicy": {"enabled": False},
            "defaultUrl": "/lab/tree/Welcome.ipynb",
            "extraEnv": {
                "GRANT_SUDO": "yes",
                "SHELL": "/usr/bin/zsh",
                "TZ": "UTC",
                "SIZEW": "1920",
                "SIZEH": "1080",
                "REFRESH": "60",
                "DPI": "96",
                "CDEPTH": "24",
                "PASSWD": "maia",
                "WEBRTC_ENCODER": "nvh264enc",
                "BASIC_AUTH_PASSWORD": "maia",
                "NOVNC_ENABLE": "true",
                "ssh_publickey": "NOKEY",
                "NB_USER": "maia-user",
                "MINIO_ACCESS_KEY": user_form.get("minio_access_key", "N/A"),
                "MINIO_SECRET_KEY": user_form.get("minio_secret_key", "N/A"),
                "MLFLOW_TRACKING_URI": f"https://{hub_address}/mlflow",
                "HOSTNAME": cluster_config["ssh_hostname"],
                "NAMESPACE": namespace.lower(),
                "INSTALL_ZSH": "1",
                "CONDA_ENVS_PATH": "/home/maia-user/.conda/envs/",
                "FREESURFER_HOME": "/home/maia-user/freesurfer/freesurfer",
            },
        },
    }

    jh_template["hub"]["extraVolumes"] = [
        {"name": "kubernetes-ca", "secret": {"secretName": "kubernetes-ca"}},
    ]
    jh_template["hub"]["extraVolumeMounts"] = [
        {
            "name": "kubernetes-ca",
            "mountPath": "/usr/local/share/ca-certificates/kubernetes-ca.crt",
            "subPath": "tls.crt",
        },
    ]
    jh_template["hub"]["extraEnv"] = {"REQUESTS_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt"}

    if not minimal:
        jh_template["singleuser"]["extraEnv"]["INSTALL_QUPATH"] = "1"
        jh_template["singleuser"]["extraEnv"]["INSTALL_SLICER"] = "1"
        jh_template["singleuser"]["extraEnv"]["INSTALL_ITKSNAP"] = "1"
        # jh_template["singleuser"]["extraEnv"]["INSTALL_FREESURFER"] = "1"
        jh_template["singleuser"]["extraEnv"]["INSTALL_MITK"] = "1"
        jh_template["singleuser"]["extraEnv"]["INSTALL_NAPARI"] = "1"

    # Perform base64 decoding if MINIO_ACCESS_KEY or MINIO_SECRET_KEY is not "N/A"
    if jh_template["singleuser"]["extraEnv"]["MINIO_ACCESS_KEY"] != "N/A":
        jh_template["singleuser"]["extraEnv"]["MINIO_ACCESS_KEY"] = base64.b64decode(
            jh_template["singleuser"]["extraEnv"]["MINIO_ACCESS_KEY"]
        ).decode("utf-8")

    if jh_template["singleuser"]["extraEnv"]["MINIO_SECRET_KEY"] != "N/A":
        jh_template["singleuser"]["extraEnv"]["MINIO_SECRET_KEY"] = base64.b64decode(
            jh_template["singleuser"]["extraEnv"]["MINIO_SECRET_KEY"]
        ).decode("utf-8")

    jh_template["hub"]["activeServerLimit"] = 1  # TODO: Add to form
    jh_template["hub"]["concurrentSpawnLimit"] = 1  # TODO: Add to form

    shared_server_user = "user@maia.se"  # TODO: Add to form
    jh_template["hub"]["loadRoles"] = {
        "user": {
            "description": "Allow users to access the shared server in addition to default perms",
            "scopes": ["self", f"access:servers!user={shared_server_user}"],
            "users": user_form["users"],
            "groups": [],
        }
    }

    if cluster_config["url_type"] == "subpath":
        jh_template["singleuser"]["extraEnv"]["MLFLOW_TRACKING_URI"] = f"https://{hub_address}/{namespace}-mlflow"

    if "minio_env_name" in user_form or "MINIO_URL" in os.environ:
        if "minio_env_name" not in user_form:
            minio_env_name = team_id + "_env"
        else:
            minio_env_name = user_form["minio_env_name"]
        client = Minio(
            os.environ["MINIO_URL"],
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            secure=os.environ["MINIO_SECURE"],
        )
        try:
            if minio_env_name.endswith(".zip"):
                settings_dict = {
                    "MINIO_PUBLIC_URL": os.environ["MINIO_URL"],
                    "MINIO_ACCESS_KEY": os.environ["MINIO_ACCESS_KEY"],
                    "MINIO_SECRET_KEY": os.environ["MINIO_SECRET_KEY"],
                    "MINIO_PUBLIC_SECURE": os.environ["MINIO_SECURE"],
                    "BUCKET_NAME": os.environ["BUCKET_NAME"],
                }
                settings = SimpleNamespace(**settings_dict)
                jh_helm_template["singleuser"]["extraEnv"]["CUSTOM_SETUP_LINK"] = get_minio_shareable_link(
                    minio_env_name, os.environ["BUCKET_NAME"], settings
                )
            else:
                client.fget_object(os.environ["BUCKET_NAME"], minio_env_name, minio_env_name)
                with open(minio_env_name, "r") as f:
                    file_string = f.read()
                    if file_string.startswith("name:"):
                        jh_template["singleuser"]["extraEnv"]["CONDA_ENV"] = str(file_string)
                    else:
                        jh_template["singleuser"]["extraEnv"]["PIP_ENV"] = str(file_string)
        except Exception as e:
            print(e)
            print(f"Could not read {minio_env_name} from MinIO bucket {os.environ['BUCKET_NAME']}")
    if "url_type" in cluster_config:
        if cluster_config["url_type"] == "subpath":
            jh_template["hub"]["baseUrl"] = f"/{group_subdomain}-hub"

    if keycloak is not None:
        jh_template["hub"]["config"]["GenericOAuthenticator"]["client_id"] = keycloak["client_id"]
        jh_template["hub"]["config"]["GenericOAuthenticator"]["client_secret"] = keycloak["client_secret"]
        jh_template["hub"]["config"]["GenericOAuthenticator"]["authorize_url"] = keycloak["authorize_url"]
        jh_template["hub"]["config"]["GenericOAuthenticator"]["token_url"] = keycloak["token_url"]
        jh_template["hub"]["config"]["GenericOAuthenticator"]["userdata_url"] = keycloak["userdata_url"]
        if "url_type" in cluster_config:
            if cluster_config["url_type"] == "subdomain":
                jh_template["hub"]["config"]["GenericOAuthenticator"][
                    "oauth_callback_url"
                ] = f"https://{hub_address}/hub/oauth_callback"

            elif cluster_config["url_type"] == "subpath":
                jh_template["hub"]["config"]["GenericOAuthenticator"][
                    "oauth_callback_url"
                ] = f"https://{hub_address}/{group_subdomain}-hub/oauth_callback"

    if "JHUB_IMAGE" in os.environ:
        jh_template["hub"]["image"] = {"name": os.environ["JHUB_IMAGE"], "tag": "1.0"}
        jh_template["hub"]["image"]["pullSecrets"] = [os.environ["JHUB_IMAGE"].replace(".", "-").replace("/", "-")]

    if "JHUB_IMAGE_" + namespace in os.environ:
        jh_template["hub"]["image"] = {
            "name": os.environ["JHUB_IMAGE_" + namespace],
            "tag": "1.0",
        }
        jh_template["hub"]["image"]["pullSecrets"] = [os.environ["JHUB_IMAGE_" + namespace].replace(".", "-").replace("/", "-")]

    if gpu_request == 0:
        jh_template["singleuser"]["extraEnv"]["NVIDIA_VISIBLE_DEVICES"] = ""

    if "ssh_users" in user_form:
        for ssh_port in user_form["ssh_users"]:
            username = ssh_port["username"].replace("@", "__at__")
            jh_template["singleuser"]["extraEnv"][f"SSH_PORT_{username}"] = str(ssh_port["ssh_port"])

    if traefik_resolver is not None:
        jh_template["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls.certresolver"] = traefik_resolver
        jh_template["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.entrypoints"] = "websecure"
        jh_template["ingress"]["annotations"]["traefik.ingress.kubernetes.io/router.tls"] = "true"

    if nginx_cluster_issuer is not None:
        jh_template["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"] = "2g"
        jh_template["ingress"]["annotations"]["cert-manager.io/cluster-issuer"] = nginx_cluster_issuer
        jh_template["ingress"]["tls"][0]["secretName"] = "jupyterhub-{}-tls".format(namespace.lower())

    if hub_storage_class is not None:
        jh_template["hub"]["db"] = {"pvc": {"storageClassName": hub_storage_class}}

    if hub_image is not None:
        jh_template["hub"]["image"] = {"name": hub_image, "tag": hub_tag}

    if base_url is not None:
        jh_template["hub"]["base_url"] = base_url

    # jh_template["singleuser"]["nodeSelector"] = {"kubernetes.io/hostname": "node-1"}  #TODO: Add nodeSelector

    jh_template["singleuser"]["storage"] = {
        "homeMountPath": "/home/maia-user",
        "dynamic": {"storageClass": storage_class},
        "extraVolumes": [{"name": "shm-volume", "emptyDir": {"medium": "Memory"}}],
        "extraVolumeMounts": [{"name": "shm-volume", "mountPath": "/dev/shm"}],
    }

    if resources_limits["memory"][1].endswith(" Gi"):
        resources_limits["memory"][1] = resources_limits["memory"][1].replace(" Gi", "G")
    elif resources_limits["memory"][1].endswith("Gi"):
        resources_limits["memory"][1] = resources_limits["memory"][1].replace("Gi", "G")
    if resources_limits["memory"][0].endswith(" Gi"):
        resources_limits["memory"][0] = resources_limits["memory"][0].replace(" Gi", "G")
    elif resources_limits["memory"][0].endswith("Gi"):
        resources_limits["memory"][0] = resources_limits["memory"][0].replace("Gi", "G")

    jh_template["singleuser"]["memory"] = {
        "limit": resources_limits["memory"][1],
        "guarantee": resources_limits["memory"][0],
    }

    jh_template["singleuser"]["cpu"] = {
        "limit": int(resources_limits["cpu"][1]),
        "guarantee": int(resources_limits["cpu"][0]),
    }

    for extra_volume in extra_volumes:
        jh_template["singleuser"]["storage"]["extraVolumes"].append(
            {
                "name": extra_volume["name"],
                "persistentVolumeClaim": {"claimName": extra_volume["pvc-name"]},
            }
        )
        jh_template["singleuser"]["storage"]["extraVolumeMounts"].append(
            {"name": extra_volume["name"], "mountPath": extra_volume["mount-path"]}
        )

    for extra_host_volume in extra_host_volumes:
        jh_template["singleuser"]["storage"]["extraVolumes"].append(
            {
                "name": extra_host_volume["name"],
                "hostPath": {"path": extra_host_volume["host-path"]},
            }
        )
        jh_template["singleuser"]["storage"]["extraVolumeMounts"].append(
            {
                "name": extra_host_volume["name"],
                "mountPath": extra_host_volume["mount-path"],
            }
        )

    jh_template["singleuser"]["image"] = {
        "name": "jupyter/datascience-notebook",
        "tag": "latest",
    }

    if "imagePullSecrets" in os.environ:
        jh_template["singleuser"]["image"]["pullSecrets"] = [os.environ["imagePullSecrets"]]

    if "imagePullSecrets_" + namespace in os.environ:
        jh_template["singleuser"]["image"]["pullSecrets"] = [os.environ["imagePullSecrets_" + namespace]]
    if not minimal:
        if "MAIA_PRIVATE_REGISTRY_" + namespace in os.environ:
            registry_url = os.environ["MAIA_PRIVATE_REGISTRY_" + namespace]
        else:
            registry_url = os.environ.get("MAIA_PRIVATE_REGISTRY", None)
        jh_template["singleuser"]["image"]["pullSecrets"].append(registry_url.replace(".", "-").replace("/", "-"))

    maia_workspace_version = os.environ["maia_workspace_version"]
    maia_workspace_image = os.environ["maia_workspace_image"]
    if "maia_workspace_image_" + namespace in os.environ:
        maia_workspace_image = os.environ["maia_workspace_image_" + namespace]
    if "maia_workspace_version_" + namespace in os.environ:
        maia_workspace_version = os.environ["maia_workspace_version_" + namespace]
    if not minimal:
        maia_workspace_image = os.environ["maia_workspace_pro_image"]
        maia_workspace_version = os.environ["maia_workspace_pro_version"]
        if "maia_workspace_pro_image_" + namespace in os.environ:
            maia_workspace_image = os.environ["maia_workspace_pro_image_" + namespace]
        if "maia_workspace_pro_version_" + namespace in os.environ:
            maia_workspace_version = os.environ["maia_workspace_pro_version_" + namespace]

    jh_template["singleuser"]["profileList"] = [
        {
            "display_name": f"MAIA Workspace v{maia_workspace_version}",
            "description": "MAIA Workspace with Python 3.10, Anaconda and SSH Connection",
            "default": True,
            "kubespawner_override": {
                "image": f"{maia_workspace_image}:{maia_workspace_version}",
                "start_timeout": 7200,
                "http_timeout": 7200,
                # mem_limit
                # cpu_limit
                # mem_guarantee
                # cpu_guarantee
                # nodeSelector: {"kubernetes.io/hostname": "node-1"}
                "extra_resource_limits": {},
                # "container_security_context": {
                # "privileged": True, ## Remove
                # "procMount": "unmasked",
                # "seccompProfile": {
                #    "type": "Unconfined"
                # }
                # }
            },
        },
        {
            "display_name": f"MAIA Workspace v{maia_workspace_version} [No GPU]",
            "description": "MAIA Workspace with Python 3.10, Anaconda, and SSH Connection",
            "default": True,
            "kubespawner_override": {
                "image": f"{maia_workspace_image}:{maia_workspace_version}",
                "start_timeout": 7200,
                "http_timeout": 7200,
                "environment": {"NVIDIA_VISIBLE_DEVICES": ""},
                "extra_resource_limits": {},
            },
        },
    ]

    deploy_monai_toolkit = not minimal
    if (
        "maia_monai_toolkit_image" in os.environ or "maia_monai_toolkit_image_" + namespace in os.environ
    ) and deploy_monai_toolkit:
        image = os.environ["maia_monai_toolkit_image"]
        if "maia_monai_toolkit_image_" + namespace in os.environ:
            image = os.environ["maia_monai_toolkit_image_" + namespace]
        jh_template["singleuser"]["profileList"].append(
            {
                "display_name": "MONAI Toolkit 3.0",
                "description": (
                    "MONAI Toolkit 3.0, including MONAI Bundles from the MONAI Model ZOO and "
                    "Tutorial Notebooks for MONAI Core, MONAI Label and NVFlare for Federated Learning"
                ),
                "kubespawner_override": {
                    "image": image,
                    "start_timeout": 3600,
                    "http_timeout": 3600,
                    "extra_resource_limits": {},
                    "uid": 0,
                },
            }
        )
        if gpu_request > 0:
            jh_template["singleuser"]["profileList"][-1]["kubespawner_override"]["extra_resource_limits"] = {
                "nvidia.com/gpu": gpu_request
            }

    mount_cifs = form.get("extra_configs", {}).get("enable_cifs", False)
    cifs_mount_path = os.environ.get("CIFS_SERVER", "N/A")

    if cifs_mount_path == "N/A":
        mount_cifs = False

    if mount_cifs:
        jh_template["singleuser"]["storage"]["extraVolumes"].append(
            {
                "name": "cifs-encryption-key",
                "secret": {"secretName": "cifs-encryption-public-key"},
            }
        )
        jh_template["singleuser"]["storage"]["extraVolumeMounts"].append(
            {"name": "cifs-encryption-key", "mountPath": "/opt/cifs-encryption-key"}
        )

    if mount_cifs:
        jh_template["singleuser"]["profileList"].append(
            {
                "display_name": f"MAIA Workspace v{maia_workspace_version} + CIFS",
                "description": "MAIA Workspace with Python 3.10, Anaconda and SSH Connection. Includes CIFS mount.",
                "kubespawner_override": {
                    "image": f"{maia_workspace_image}:{maia_workspace_version}",
                    "start_timeout": 7200,
                    "http_timeout": 7200,
                    "extra_resource_limits": {},
                    "volumes": [
                        {
                            "name": "jupyter-shared",
                            "persistentVolumeClaim": {"claimName": "shared"},
                        },
                        {
                            "name": "home",
                            "persistentVolumeClaim": {"claimName": "claim-{username}"},
                        },
                        {"name": "shm-volume", "emptyDir": {"medium": "Memory"}},
                        {
                            "name": "cifs",
                            "flexVolume": {
                                "driver": "fstab/cifs",
                                "fsType": "cifs",
                                "options": {
                                    "mountOptions": "dir_mode=0777,file_mode=0777,iocharset=utf8,noperm,nounix,rw",
                                    "networkPath": cifs_mount_path + "/{username}",
                                },
                                "secretRef": {"name": "{username}-cifs"},
                            },
                        },
                        {
                            "name": "cifs-shared",
                            "flexVolume": {
                                "driver": "fstab/cifs",
                                "fsType": "cifs",
                                "options": {
                                    "mountOptions": "dir_mode=0777,file_mode=0777,iocharset=utf8,noperm,nounix,rw",
                                    "networkPath": cifs_mount_path + f"/{namespace}",
                                },
                                "secretRef": {"name": "{username}-cifs"},
                            },
                        },
                    ],
                    "volume_mounts": [
                        {"mountPath": "/home/maia-user/cifs", "name": "cifs"},
                        {
                            "mountPath": "/home/maia-user/cifs-shared",
                            "name": "cifs-shared",
                        },
                        {
                            "mountPath": "/home/maia-user/shared",
                            "name": "jupyter-shared",
                        },
                        {"mountPath": "/dev/shm", "name": "shm-volume"},
                        {"mountPath": "/home/maia-user", "name": "home"},
                    ],
                    "service_account": "secret-writer",
                },
            }
        )

    if gpu_request > 0:
        for profile in jh_template["singleuser"]["profileList"]:
            if (
                "environment" in profile["kubespawner_override"]
                and "NVIDIA_VISIBLE_DEVICES" in profile["kubespawner_override"]["environment"]
                and profile["kubespawner_override"]["environment"]["NVIDIA_VISIBLE_DEVICES"] == ""
            ):
                continue
            else:
                profile["kubespawner_override"]["extra_resource_limits"] = {"nvidia.com/gpu": gpu_request}
    else:
        for profile in jh_template["singleuser"]["profileList"]:
            if "environment" not in profile["kubespawner_override"]:
                profile["kubespawner_override"]["environment"] = {}
            profile["kubespawner_override"]["environment"]["NVIDIA_VISIBLE_DEVICES"] = ""
            profile["kubespawner_override"]["extra_resource_limits"] = {}
    if mount_cifs:
        for id, _ in enumerate(jh_template["singleuser"]["profileList"]):
            jh_template["singleuser"]["profileList"][id]["kubespawner_override"]["service_account"] = "secret-writer"

    jh_helm_template["resource"]["helm_release"]["jupyterhub"]["values"] = [yaml.dump(jh_template)]

    jh_template["prePuller"] = {
        "hook": {"enabled": False},
        "continuous": {"enabled": False},
    }
    chart_info = {}
    chart_info["chart_name"] = jh_helm_template["resource"]["helm_release"]["jupyterhub"]["chart"]
    chart_info["chart_version"] = jh_helm_template["resource"]["helm_release"]["jupyterhub"]["version"]
    chart_info["repo_url"] = jh_helm_template["resource"]["helm_release"]["jupyterhub"]["repository"]

    Path(config_folder).joinpath(team_id, "jupyterhub_values").mkdir(parents=True, exist_ok=True)
    Path(config_folder).joinpath(team_id, "jupyterhub_chart_info").mkdir(parents=True, exist_ok=True)

    with open(
        Path(config_folder).joinpath(team_id, "jupyterhub_values", "jupyterhub_values.yaml"),
        "w",
    ) as f:
        f.write(OmegaConf.to_yaml(jh_template))

    with open(
        Path(config_folder).joinpath(team_id, "jupyterhub_chart_info", "jupyterhub_chart_info.yaml"),
        "w",
    ) as f:
        f.write(OmegaConf.to_yaml(chart_info))

    return {
        "namespace": namespace,
        "chart": chart_info["chart_name"],
        "release": f"{namespace}-jupyterhub",
        "repo": chart_info["repo_url"],
        "version": chart_info["chart_version"],
        "values": str(Path(config_folder).joinpath(team_id, "jupyterhub_values", "jupyterhub_values.yaml")),
    }


def main():
    create_jupyterhub_config()


if __name__ == "__main__":
    main()
