Build Images
============

The MAIA Build-Images Ansible collection provides automation for building and pushing Docker images for the MAIA platform components to container registries (Docker Hub, GitHub Container Registry, or private registries).

Requirements
------------

Before running the playbooks, ensure you have:

- Docker installed and configured on the build host
- Git credentials (username and token/password) for accessing MAIA repositories
- Registry credentials for pushing images (Docker Hub, GitHub, or private registry)
- The MAIA toolkit installed with the ``MAIA_build_images`` command available
- A properly configured environment with ``env.json`` and cluster configuration files

Required Variables
------------------

The build_images role requires the following variables:

- **config_folder**: Directory containing ``env.json``, cluster configuration YAML, and registry credentials JSON
- **cluster_name**: Name of the cluster configuration file (without .yaml extension, e.g., ``maia-dev``)
- **GIT_USERNAME**: Git username for accessing MAIA source repositories
- **GIT_TOKEN**: Git token or password for authentication
- **registry_base**: Docker registry base URL (e.g., ``https://index.docker.io/v1/`` for Docker Hub or ``ghcr.io`` for GitHub)
- **registry_path**: Registry organization/path (e.g., ``maiacloudai`` for Docker Hub or ``/minnelab`` for GitHub)
- **credentials_json_filename**: Name of the registry credentials JSON file (e.g., ``dockerhub-registry-credentials.json`` or ``github-registry-credentials.json``)
- **maia_project_id**: MAIA project identifier for the registry (e.g., ``maia-image-dockerhub`` or ``maia-image-github``)

Optional Variables
------------------

- **auto_sync**: Enable automatic ArgoCD application synchronization (optional)
  - Default: `false`
  - Description: Enable automatic ArgoCD application synchronization. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `auto_sync: true`
- **apps_to_sync**: List of ArgoCD applications to synchronize (optional)
  - Default: `["all"]`
  - Description: List of ArgoCD applications to synchronize. When set to `["all"]`, all applications will be synchronized. Otherwise, only the specified applications will be synchronized.
  - Example: `apps_to_sync: ["maia-kube", "maia-dashboard", "maia-filebrowser"]`
- **maia_workspace_notebook_ssh_addons_image_name**: Name of the MAIA workspace notebook SSH addons image (optional)
  - Default: `maia-workspace-notebook-ssh-addons`
  - Description: Name of the MAIA workspace notebook SSH addons image. This is used to synchronize the ArgoCD application for the workspace notebook SSH addons.
  - Example: `maia_workspace_notebook_ssh_addons_image_name: "maia-workspace-notebook-ssh-addons-image"`
- **argocd_port**: Local port for ArgoCD CLI access (optional)
  - Default: `8080`
  - Description: Local port for ArgoCD CLI access. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `argocd_port: 8080`
- **maia_git_repo_url**: MAIA git repository URL (optional)
  - Default: `git://github.com/minnelab/MAIA.git`
  - Description: MAIA git repository URL. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `maia_git_repo_url: git://github.com/minnelab/MAIA.git`
- **build_custom_images**: Enable building custom images from the given YAML file (optional)
  - Default: `false`
  - Description: Enable building custom images from the given YAML file. When enabled, the role will build the custom images from the given YAML file.
  - Example: `build_custom_images: true`
- **docker_build_project_chart**: Helm chart name for Docker build project (optional)
  - Default: `maia-docker-build-project`
  - Description: Helm chart name for Docker build project. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `docker_build_project_chart: maia-docker-build-project`
- **docker_build_project_repo**: Helm chart repository URL for Docker build project (optional)
  - Default: `https://minnelab.github.io/MAIA/`
  - Description: Helm chart repository URL for Docker build project. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `docker_build_project_repo: https://minnelab.github.io/MAIA/`
- **docker_build_project_version**: Helm chart version for Docker build project (optional)
  - Default: `1.2.0`
  - Description: Helm chart version for Docker build project. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `docker_build_project_version: 1.2.0`
- **maia_project_id**: MAIA project identifier for the registry (optional)
  - Default: `maia-image`
  - Description: MAIA project identifier for the registry. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `maia_project_id: maia-image`
- **cluster_address**: Kubernetes cluster API address (optional)
  - Default: `https://kubernetes.default.svc`
  - Description: Kubernetes cluster API address. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `cluster_address: https://kubernetes.default.svc`
- **registry_base**: Container registry base URL (optional)
  - Default: `https://index.docker.io/v1/`
  - Description: Container registry base URL. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `registry_base: https://index.docker.io/v1/`
- **registry_path**: Container registry path/namespace (optional)
  - Default: `maiacloudai`
  - Description: Container registry path/namespace. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `registry_path: maiacloudai`
- **credentials_json_filename**: Name of the registry credentials JSON file in config_folder (optional)
  - Default: `maia-registry-credentials.json`
  - Description: Name of the registry credentials JSON file in config_folder. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `credentials_json_filename: maia-registry-credentials.json`
- **kubeconfig_path**: Path to kubeconfig file for deployment (optional)
  - Default: `{{ config_folder }}/{{ cluster_name }}-kubeconfig.yaml`
  - Description: Path to kubeconfig file for deployment. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
  - Example: `kubeconfig_path: {{ config_folder }}/{{ cluster_name }}-kubeconfig.yaml`

Configuration Files
-------------------

Registry Credentials
~~~~~~~~~~~~~~~~~~~~

The registry credentials file (``<credentials_json_filename>``) should be placed in the ``config_folder`` and contain:

.. code-block:: json

    {
      "username": "registry-username",
      "password": "registry-password-or-token"
    }

For Docker Hub, use your Docker Hub username and an access token.
For GitHub Container Registry, use your GitHub username and a personal access token with ``write:packages`` scope.

Environment Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``env.json`` file in the ``config_folder`` should contain necessary environment variables for the MAIA build process.

Cluster Configuration
~~~~~~~~~~~~~~~~~~~~~

The cluster configuration YAML (``<cluster_name>.yaml``) in the ``config_folder`` should contain cluster-specific settings.

Build Process
-------------

The build_images role executes the ``MAIA_build_images`` helper script which:

1. Builds Docker images for MAIA components from the MAIA Project Repository
2. Tags images with appropriate versions and registry paths
3. Pushes images to the specified container registry
4. Updates configuration files with new image references

The script uses values previously exported and configuration files in the ``config_folder`` to determine what to build and where to push images.

Custom Images
~~~~~~~~~~~~~

To build custom images, you need to create a YAML file with the images to build, and save the file in the config folder with the name `custom_images.yaml`.

.. code-block:: yaml
- release_name: custom-image-1
  image_name: custom-image-1
  image_tag: latest
  subpath: ./custom-image-1
  build_args:
    - BUILD_ARG=value
```
Where:
- **release_name**: The name of the release. This is used to create the ArgoCD application name.
- **image_name**: The name of the image. This is used to create the image name.
- **image_tag**: The tag of the image. This is used to create the image tag.
- **git_repo_url**: The Git repository URL. This is used to clone the repository and access the Dockerfile.
- **subpath**: The subpath of the repository where the Dockerfile is located.
- **build_args**: The list of build arguments for the image. This is used to create the image build arguments.

Inventory
=========

The playbook runs on ``localhost`` and does not require a complex inventory. It can be executed with a simple inventory file:

.. code-block:: ini

    [local]
    localhost ansible_connection=local

Or directly without an inventory file by targeting localhost.

Usage
=====

See the Example section for complete usage examples with different registry configurations.
