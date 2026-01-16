from __future__ import annotations

import os
from pathlib import Path

import yaml

from MAIA.versions import define_maia_docker_versions

kaniko_chart_version = define_maia_docker_versions()["kaniko_chart_version"]
kaniko_chart_type = define_maia_docker_versions()["kaniko_chart_type"]


def deploy_maia_kaniko(
    namespace,
    config_folder,
    cluster_config_dict,
    release_name,
    project_id,
    registry_url,
    registry_secret_name,
    image_name,
    image_tag,
    subpath,
    build_args=None,
    registry_credentials=None,
    git_repo_url=None,
):
    """
    Deploys a Kaniko job for building and pushing Docker images to a specified registry.

    Parameters
    ----------
    namespace : str
        The Kubernetes namespace where the Kaniko job will be deployed.
    config_folder : str
        The folder path where the configuration files will be stored.
    cluster_config_dict : dict
        Dictionary containing cluster configuration details, including storage class.
    release_name : str
        The release name for the Kaniko job.
    project_id : str
        The project identifier.
    registry_url : str
        The URL of the Docker registry where the image will be pushed.
    registry_secret_name : str
        The name of the Kubernetes secret for accessing the Docker registry.
    image_name : str
        The name of the Docker image to be built.
    image_tag : str
        The tag of the Docker image to be built.
    subpath : str
        The subpath of the repository where the Dockerfile is located.
    build_args : list, optional
        A list of build arguments to be passed to the Kaniko job.
    registry_credentials : dict, optional
        A dictionary containing registry credentials with keys 'username', 'password', 'server', and 'email'.
    custom_git_repo_url : str, optional
        The URL of the Git repository where the Dockerfile is located.
    Returns
    -------
    dict
        A dictionary containing deployment details including namespace, release name,
        chart name, repo URL, chart version, and values file path.
    """

    kaniko_values = {
        "chart_version": kaniko_chart_version,
        "namespace": "mkg-kaniko",
    }

    if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True" and kaniko_chart_type == "git_repo":
        raise ValueError("ARGOCD_DISABLED is set to True and core_toolkit_chart_type is set to git_repo, which is not allowed")

    if kaniko_chart_type == "helm_repo":
        kaniko_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://minnelab.github.io/MAIA/")
        kaniko_values["chart_name"] = "mkg-kaniko"
    elif kaniko_chart_type == "git_repo":
        kaniko_values["repo_url"] = os.environ.get("MAIA_PRIVATE_REGISTRY", "https://github.com/minnelab/MAIA.git")
        kaniko_values["path"] = "charts/maiakubegate-kaniko"

    if "MAIA_GIT_REPO_URL" not in os.environ:
        raise ValueError(
            "MAIA_GIT_REPO_URL environment variable not set. Please set this variable to the URL of the MAIA Git repository with the Docker Image to build. Example: git://github.com/minnelab/MAIA.git"  # noqa: B950
        )

    if "GIT_USERNAME" not in os.environ:
        raise ValueError(
            "GIT_USERNAME environment variable not set. Please set this variable to the username for accessing the Git repository with the Docker Image to build."  # noqa: B950
        )

    if "GIT_TOKEN" not in os.environ:
        raise ValueError(
            "GIT_TOKEN environment variable not set. Please set this variable to the personal access token for accessing the Git repository with the Docker Image to build."  # noqa: B950
        )

    registry_server = registry_credentials.get("server") if registry_credentials else None
    registry_username = registry_credentials.get("username") if registry_credentials else None
    registry_password = registry_credentials.get("password") if registry_credentials else None
    registry_email = registry_credentials.get("email") if registry_credentials else None

    registry_complete_url = registry_url
    if registry_url.startswith("https://index.docker.io/v1/"):
        registry_complete_url = registry_url.replace("https://index.docker.io/v1/", "")

    kaniko_values.update(
        {
            "docker_registry_secret": registry_secret_name,
            "namespace": "mkg-kaniko",
            "dockerRegistryServer": ("https://" + registry_server if "registry_server" not in os.environ else registry_server),
            "dockerRegistryUsername": registry_username,
            "dockerRegistryPassword": registry_password,
            "dockerRegistryEmail": registry_email,
            "dockerRegistrySecretName": registry_secret_name,
            "pvc": {"pvc_type": cluster_config_dict["storage_class"], "size": "10Gi"},
            "git_username": os.environ.get("GIT_USERNAME"),
            "git_token": os.environ.get("GIT_TOKEN"),
            "args": [
                "--dockerfile=Dockerfile",
                f"--context={git_repo_url if git_repo_url is not None else os.environ['MAIA_GIT_REPO_URL']}",  # git://github.com/acme/myproject.git#refs/heads/mybranch#<desired-commit-id>
                "--context-sub-path=" + subpath,
                "--destination={}/{}:{}".format(registry_complete_url, image_name, image_tag),
                "--cache=true",
                "--cache-dir=/cache",
                "--insecure",
                "--skip-tls-verify",
            ],
        }
    )

    if build_args:
        for build_arg in build_args:
            kaniko_values["args"].append(f"--build-arg={build_arg}")

    release_name_values = release_name.replace("-", "_")
    Path(config_folder).joinpath(project_id, f"{release_name_values}_values").mkdir(parents=True, exist_ok=True)
    with open(
        Path(config_folder).joinpath(project_id, f"{release_name_values}_values", f"{release_name_values}_values.yaml"), "w"
    ) as f:
        yaml.dump(kaniko_values, f)

    return {
        "namespace": namespace,
        "release": f"{project_id}-{release_name}",
        "chart": (kaniko_values["chart_name"] if kaniko_chart_type == "helm_repo" else kaniko_values["path"]),
        "repo": kaniko_values["repo_url"],
        "version": kaniko_values["chart_version"],
        "values": str(
            Path(config_folder).joinpath(project_id, f"{release_name_values}_values", f"{release_name_values}_values.yaml")
        ),
    }
