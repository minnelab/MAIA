# Ansible Collection - MAIA.Build_Images

Documentation for the MAIA.Build_Images Ansible collection, which provides roles and playbooks for building and pushing Docker images for MAIA (Medical AI Assistant) platform components to container registries.

## Requirements

The following packages and tools are required before using this collection:

**Python packages:**
```bash
pip install maia-toolkit ansible
```

### Minimum Hardware Requirements

To successfully build MAIA images, your build host should meet at least the following specifications:

- **Memory:** 8 GB RAM
- **CPU:** 4 CPU cores
- **Disk:** 50 GB available storage (for Docker images and build cache)
- **Network:** Stable internet connection for pulling base images and pushing to registries

**Operating System:**  
MAIA image building has been tested on Ubuntu 22.04 and 24.04 LTS.

> **Note:**  
> These requirements are for building MAIA platform images. Building time may vary depending on the number of images and your internet connection speed.

## Installation

To install the MAIA.Build_Images collection, run the following command:
```bash
ansible-galaxy collection install maia.build_images
```

Or install from source:
```bash
cd ansible/MAIA/Build-Images
ansible-galaxy collection build
ansible-galaxy collection install maia-build_images-<version>.tar.gz
```

## Quick Start

### 1. Prepare Configuration

Before building images, you need:

- A configuration folder containing `env.json` and cluster configuration files
- Git credentials (username and token) for accessing MAIA repositories
- Registry credentials for pushing images

**Create registry credentials file:**

For Docker Hub (`dockerhub-registry-credentials.json`):
```json
{
  "username": "your-dockerhub-username",
  "password": "your-dockerhub-token"
}
```

For GitHub Container Registry (`github-registry-credentials.json`):
```json
{
  "username": "your-github-username",
  "password": "your-github-token"
}
```

### 2. Run the Build Playbook

**For Docker Hub:**
```bash
ansible-playbook -i inventory maia.build_images.build_images \
  -e config_folder=/path/to/config \
  -e cluster_name=maia-cluster \
  -e GIT_USERNAME=your-git-username \
  -e GIT_TOKEN=your-git-token \
  -e registry_base=https://index.docker.io/v1/ \
  -e registry_path=maiacloudai \
  -e credentials_json_filename=dockerhub-registry-credentials.json \
  -e maia_project_id=maia-image-dockerhub
```

**For GitHub Container Registry:**
```bash
ansible-playbook -i inventory maia.build_images.build_images \
  -e config_folder=/path/to/config \
  -e cluster_name=maia-cluster \
  -e GIT_USERNAME=your-git-username \
  -e GIT_TOKEN=your-git-token \
  -e registry_base=ghcr.io \
  -e registry_path=/minnelab \
  -e credentials_json_filename=github-registry-credentials.json \
  -e maia_project_id=maia-image-github
```

## Required Variables

The following variables must be provided when running the build_images playbook:

- **config_folder**: Directory containing `env.json`, cluster config, and registry credentials
- **cluster_name**: Name of the cluster configuration file (without .yaml extension)
- **GIT_USERNAME**: Git username for accessing MAIA repositories
- **GIT_TOKEN**: Git token or password for authentication
- **registry_base**: Registry base URL
  - Docker Hub: `https://index.docker.io/v1/`
  - GitHub: `ghcr.io`
  - Private registry: `https://harbor.example.com`
- **registry_path**: Registry organization or path
  - Docker Hub: `maiacloudai`
  - GitHub: `/minnelab`
  - Private: `/your-project`
- **credentials_json_filename**: Name of the registry credentials JSON file in config_folder
- **maia_project_id**: MAIA project identifier for the registry

## Optional Variables

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

## Using Environment Variables

Instead of passing credentials on the command line, you can use environment variables:

```bash
export GIT_USERNAME=your-username
export GIT_TOKEN=your-token

ansible-playbook -i inventory maia.build_images.build_images \
  -e config_folder=/path/to/config \
  -e cluster_name=maia-cluster \
  -e GIT_USERNAME="{{ lookup('env', 'GIT_USERNAME') }}" \
  -e GIT_TOKEN="{{ lookup('env', 'GIT_TOKEN') }}" \
  -e registry_base=https://index.docker.io/v1/ \
  -e registry_path=maiacloudai \
  -e credentials_json_filename=dockerhub-registry-credentials.json \
  -e maia_project_id=maia-image-dockerhub
```

## Using the Role Directly

You can also use the `build_images` role in your own playbooks:

```yaml
---
- name: Build MAIA images
  hosts: localhost
  vars:
    config_folder: /opt/maia/config
    cluster_name: maia-cluster
    GIT_USERNAME: "{{ lookup('env', 'GIT_USERNAME') }}"
    GIT_TOKEN: "{{ lookup('env', 'GIT_TOKEN') }}"
    registry_base: https://index.docker.io/v1/
    registry_path: maiacloudai
    credentials_json_filename: dockerhub-registry-credentials.json
    maia_project_id: maia-image-dockerhub
  vars_files:
    - "{{ config_folder }}/env.json"
    - "{{ config_folder }}/{{ cluster_name }}.yaml"
  roles:
    - maia.build_images.build_images
```

## Supported Registries

The collection supports building and pushing images to:

- **Docker Hub** (`https://index.docker.io/v1/`)
- **GitHub Container Registry** (`ghcr.io`)
- **Private registries** (Harbor, GitLab Registry, etc.)

## Troubleshooting

### Common Issues

**1. Authentication failures:**
- Verify Git credentials have access to MAIA repositories
- Ensure registry credentials are correct
- Check that tokens have not expired and have appropriate permissions

**2. Build failures:**
- Ensure Docker is running: `systemctl status docker`
- Check disk space: `df -h`
- Verify `MAIA_build_images` command is available: `which MAIA_build_images`

**3. Push failures:**
- Confirm network connectivity to the registry
- Verify registry path and project exist
- Check that you have push permissions

### Verbose Mode

For detailed output during the build process:

```bash
ansible-playbook -vvv playbooks/build_images.yaml (...)
```

## Documentation

<!-- DOCS-START -->
<!-- DOCS-END -->

<!-- DOCS-EXAMPLE-START -->
<!-- DOCS-EXAMPLE-END -->

## Contributing

For issues, feature requests, or contributions, please visit the [MAIA GitHub repository](https://github.com/minnelab/MAIA).

## License

This collection is licensed under GPL-3.0-only. See the LICENSE file for details.

## Authors

- Simone Bendazzoli <simben@kth.se>
