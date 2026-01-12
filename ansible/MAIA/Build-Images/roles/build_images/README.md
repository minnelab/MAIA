# Build Images Role

This Ansible role builds MAIA Docker images using Kaniko on Kubernetes. It automates the build process for MAIA components (maia-kube, maia-dashboard, maia-filebrowser) and synchronizes them via ArgoCD for deployment.

## Description

The `build_images` role automates the building and deployment of MAIA Docker images using Kaniko, a container image builder that works within Kubernetes without requiring privileged access. It performs the following tasks:

1. **Validates required variables** (config_folder, cluster_name, GIT_USERNAME, GIT_TOKEN)
2. **Loads environment variables** from `env.json` in the config folder
3. **Reads cluster configuration** to extract cluster-specific settings (ingress_resolver_email)
4. **Loads registry credentials** from JSON file containing username/password
5. **Executes MAIA_build_images** command to build Docker images using Kaniko
6. **Logs into ArgoCD** using CLI with multiple fallback methods
7. **Synchronizes ArgoCD applications** for maia-kube, maia-dashboard, and maia-filebrowser
8. **Waits for applications** to complete synchronization

This role is designed to be used as part of the MAIA build process, typically after infrastructure is deployed, to build and deploy custom MAIA application images.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Linux (role runs on localhost, delegates to Kubernetes)
- **Privileges**: Requires access to Kubernetes cluster via kubeconfig

### Dependencies
- **Ansible Collections**: 
  - `kubernetes.core` (for Kubernetes API access)
  - Install with: `ansible-galaxy collection install kubernetes.core`
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- **Kubernetes cluster**: Must be accessible via kubeconfig file
- **Kubeconfig access**: `DEPLOY_KUBECONFIG` must be set in `env.json`
- **Config folder**: Must contain `env.json`, cluster configuration YAML, and registry credentials JSON
- **ArgoCD**: Must be installed and accessible (typically via the `argocd` role)
- **ArgoCD CLI**: Will be installed if not present (for application synchronization)
- **MAIA_build_images command**: Must be available in the PATH
- **Git access**: Requires valid GitHub credentials (GIT_USERNAME and GIT_TOKEN) to access MAIA repository
- **Container registry**: Requires valid container registry credentials (Docker Hub, Harbor, etc.)
- **Internet access**: Required to download images and access Git repositories

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `maia_git_repo_url` | `git://github.com/minnelab/MAIA.git` | string | MAIA git repository URL |
| `docker_build_project_chart` | `maia-docker-build-project` | string | Helm chart name for Docker build project |
| `docker_build_project_repo` | `https://minnelab.github.io/MAIA/` | string | Helm chart repository URL |
| `docker_build_project_version` | `1.2.0` | string | Helm chart version for Docker build project |
| `maia_project_id` | `maia-image` | string | MAIA project identifier for ArgoCD applications |
| `cluster_address` | `https://kubernetes.default.svc` | string | Kubernetes cluster API address |
| `registry_base` | `https://index.docker.io/v1/` | string | Container registry base URL |
| `registry_path` | `maiacloudai` | string | Container registry path/namespace |
| `credentials_json_filename` | `maia-registry-credentials.json` | string | Registry credentials JSON filename |
| `argocd_namespace` | `argocd` | string | Namespace where ArgoCD is installed |
| `argocd_port` | `8080` | integer | Local port for ArgoCD CLI access |
| `auto_sync` | `false` | boolean | Enable automatic ArgoCD application synchronization |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `DEPLOY_KUBECONFIG`, `ARGOCD_PASSWORD`, `admin_group_ID`, and optionally `domain`
  - Cluster config YAML: Located at `{{ config_folder }}/{{ cluster_name }}.yaml` containing `ingress_resolver_email`
  - Registry credentials JSON: Located at `{{ config_folder }}/{{ credentials_json_filename }}` with `username` and `password` fields
- **Example**: `config_folder: /opt/maia/config`

**Note**: The role will fail if `config_folder` is not provided or if the required files do not exist.

### `cluster_name`
- **Type**: `string`
- **Required**: `true`
- **Description**: Name of the cluster configuration file (without .yaml extension). This file should exist at `{{ config_folder }}/{{ cluster_name }}.yaml` and contain cluster-specific configuration including `ingress_resolver_email`.
- **Example**: `cluster_name: maia-prod-cluster`

**Note**: The role will fail if `cluster_name` is not provided or if the corresponding YAML file does not exist.

### `GIT_USERNAME`
- **Type**: `string`
- **Required**: `true`
- **Description**: Git username for accessing the MAIA repository. This is used to clone the repository and access Dockerfiles for building images.
- **Example**: `GIT_USERNAME: github-user`

**Note**: The role will fail if `GIT_USERNAME` is not provided or is empty.

### `GIT_TOKEN`
- **Type**: `string`
- **Required**: `true`
- **Description**: Git token (personal access token) for accessing the MAIA repository. This should have read access to the repository.
- **Example**: `GIT_TOKEN: ghp_xxxxxxxxxxxxxxxxxxxx`

**Note**: The role will fail if `GIT_TOKEN` is not provided or is empty. Store this securely using Ansible Vault or environment variables.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `maia_git_repo_url`
- **Type**: `string`
- **Default**: `git://github.com/minnelab/MAIA.git`
- **Description**: URL of the MAIA git repository. You can specify a different branch or commit by appending `#refs/heads/mybranch#<commit-id>`.
- **Example**: `maia_git_repo_url: git://github.com/myorg/MAIA.git#refs/heads/develop`

### `docker_build_project_chart`
- **Type**: `string`
- **Default**: `maia-docker-build-project`
- **Description**: Helm chart name for the Docker build project. This chart contains the Kaniko job definitions for building MAIA images.
- **Example**: `docker_build_project_chart: custom-build-chart`

### `docker_build_project_repo`
- **Type**: `string`
- **Default**: `https://minnelab.github.io/MAIA/`
- **Description**: Helm chart repository URL for the Docker build project. The chart should be available in this repository.
- **Example**: `docker_build_project_repo: https://myorg.github.io/charts/`

### `docker_build_project_version`
- **Type**: `string`
- **Default**: `1.2.0`
- **Description**: Version of the Helm chart for the Docker build project. Specify a different version to use a specific chart release.
- **Example**: `docker_build_project_version: 1.3.0`

### `maia_project_id`
- **Type**: `string`
- **Default**: `maia-image`
- **Description**: MAIA project identifier used as a prefix for ArgoCD application names. Applications will be named `{{ maia_project_id }}-maia-kube`, `{{ maia_project_id }}-maia-dashboard`, etc.
- **Example**: `maia_project_id: prod-maia`

### `cluster_address`
- **Type**: `string`
- **Default**: `https://kubernetes.default.svc`
- **Description**: Kubernetes cluster API server address. Used by the build process to communicate with the cluster.
- **Example**: `cluster_address: https://maia-k8s-api.example.com:6443`

### `registry_base`
- **Type**: `string`
- **Default**: `https://index.docker.io/v1/`
- **Description**: Container registry base URL. Supports Docker Hub, Harbor, and other OCI-compliant registries.
- **Example**: 
  - Docker Hub: `https://index.docker.io/v1/`
  - Harbor: `https://harbor.example.com`
  - Custom registry: `https://registry.example.com`

### `registry_path`
- **Type**: `string`
- **Default**: `maiacloudai`
- **Description**: Container registry path/namespace where images will be pushed. For Docker Hub, this is the username or organization. For Harbor, this is the project name.
- **Example**: `registry_path: myorg/maia`

### `credentials_json_filename`
- **Type**: `string`
- **Default**: `maia-registry-credentials.json`
- **Description**: Name of the registry credentials JSON file in the config folder. This file should contain `username` and `password` fields for registry authentication.
- **Example**: `credentials_json_filename: docker-creds.json`

**Format of credentials JSON file**:
```json
{
  "username": "registry-username",
  "password": "registry-password-or-token"
}
```

### `argocd_namespace`
- **Type**: `string`
- **Default**: `argocd`
- **Description**: Kubernetes namespace where ArgoCD is installed. The role will log into ArgoCD in this namespace.
- **Example**: `argocd_namespace: gitops`

### `argocd_port`
- **Type**: `integer`
- **Default**: `8080`
- **Description**: Local port number for ArgoCD CLI access. Should match the port forwarding configuration from the ArgoCD role.
- **Example**: `argocd_port: 9090`

### `domain`
- **Type**: `string`
- **Required**: `false`
- **Description**: Domain name for ArgoCD access. Used as a fallback method when logging into ArgoCD via CLI (tries `argocd.{{ domain }}`).
- **Example**: `domain: example.com`

### `DEPLOY_KUBECONFIG`
- **Type**: `string`
- **Required**: `false`
- **Description**: Path to the kubeconfig file for deployment. Should be set in `env.json`. Used for kubectl and ArgoCD CLI operations.
- **Example**: `DEPLOY_KUBECONFIG: /opt/maia/config/kubeconfig.yaml`

### `ARGOCD_PASSWORD`
- **Type**: `string`
- **Required**: `false`
- **Description**: ArgoCD admin password for CLI login. Should be set in `env.json`. Used to authenticate with ArgoCD for application synchronization.
- **Example**: Set in `env.json`: `{"ARGOCD_PASSWORD": "admin-password"}`

**Note**: Store this securely using Ansible Vault or environment variables.

### `admin_group_ID`
- **Type**: `string`
- **Required**: `false`
- **Description**: Admin group identifier for MAIA access control. Passed to the build process for configuring access permissions in MAIA applications.
- **Example**: `admin_group_ID: maia-admins`

### `auto_sync`
- **Type**: `boolean`
- **Default**: `false`
- **Description**: Enable automatic ArgoCD application synchronization after building images. When enabled, the role will sync maia-kube, maia-dashboard, and maia-filebrowser applications.
- **Example**: `auto_sync: true`

**Note**: If set to `false`, you will need to manually sync the applications in ArgoCD after the build completes.

## Usage

### Basic Usage

Include the role in a playbook with the required variables:

```yaml
- name: Build MAIA Docker images
  hosts: localhost
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
        GIT_TOKEN: "{{ github_token }}"
```

**Important**: Ensure the config folder contains:
- `env.json` with `DEPLOY_KUBECONFIG`, `ARGOCD_PASSWORD`, and `admin_group_ID`
- `{{ cluster_name }}.yaml` with cluster configuration
- `{{ credentials_json_filename }}` with registry credentials

### With Auto Sync

Enable automatic ArgoCD application synchronization:

```yaml
- name: Build MAIA Docker images
  hosts: localhost
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
        GIT_TOKEN: "{{ github_token }}"
        auto_sync: true
```

### Custom Git Repository and Branch

Build from a custom repository and branch:

```yaml
- name: Build MAIA Docker images
  hosts: localhost
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
        GIT_TOKEN: "{{ github_token }}"
        maia_git_repo_url: "git://github.com/myorg/MAIA.git#refs/heads/develop"
```

### Custom Container Registry

Push images to a custom registry:

```yaml
- name: Build MAIA Docker images
  hosts: localhost
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
        GIT_TOKEN: "{{ github_token }}"
        registry_base: "https://harbor.example.com"
        registry_path: "maia-project"
```

### Custom Build Chart Version

Use a specific version of the build chart:

```yaml
- name: Build MAIA Docker images
  hosts: localhost
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
        GIT_TOKEN: "{{ github_token }}"
        docker_build_project_version: "1.3.0"
```

### Custom Project ID

Use a custom project identifier for ArgoCD applications:

```yaml
- name: Build MAIA Docker images
  hosts: localhost
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
        GIT_TOKEN: "{{ github_token }}"
        maia_project_id: "prod-maia"
```

**Note**: This will create/sync applications named `prod-maia-maia-kube`, `prod-maia-maia-dashboard`, and `prod-maia-maia-filebrowser`.

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e config_folder=/opt/maia/config \
  -e cluster_name=maia-prod-cluster \
  -e GIT_USERNAME=github-user \
  -e GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx \
  -e auto_sync=true
```

### Using Ansible Vault for Secrets

Store sensitive variables in an encrypted vault file:

```bash
# Create vault file
ansible-vault create secrets.yml
```

**secrets.yml**:
```yaml
---
GIT_TOKEN: ghp_xxxxxxxxxxxxxxxxxxxx
vault_registry_credentials:
  username: registry-user
  password: registry-password
ARGOCD_PASSWORD: admin-password
```

**playbook.yaml**:
```yaml
- name: Build MAIA Docker images
  hosts: localhost
  vars_files:
    - secrets.yml
  pre_tasks:
    - name: Write registry credentials to file
      copy:
        content: "{{ vault_registry_credentials | to_json }}"
        dest: "{{ config_folder }}/maia-registry-credentials.json"
        mode: '0600'
  roles:
    - role: maia.build_images.build_images
      vars:
        config_folder: /opt/maia/config
        cluster_name: maia-prod-cluster
        GIT_USERNAME: github-user
```

Run with:
```bash
ansible-playbook -i inventory playbook.yaml --ask-vault-pass
```

### Standalone Playbook Example

Create a dedicated playbook for building MAIA images:

```yaml
---
- name: Build MAIA Docker images
  hosts: localhost
  vars:
    config_folder: /opt/maia/config
    cluster_name: maia-prod-cluster
  vars_files:
    - "{{ config_folder }}/env.json"
  roles:
    - role: maia.build_images.build_images
      vars:
        GIT_USERNAME: "{{ lookup('env', 'GIT_USERNAME') }}"
        GIT_TOKEN: "{{ lookup('env', 'GIT_TOKEN') }}"
        auto_sync: true
        maia_git_repo_url: "git://github.com/minnelab/MAIA.git"
        docker_build_project_version: "1.2.0"
        registry_base: "https://index.docker.io/v1/"
        registry_path: "maiacloudai"
```

Run with:
```bash
export GIT_USERNAME=github-user
export GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
ansible-playbook build-images.yaml
```

## Tasks

The role performs the following tasks:

1. **Validate required variables**: Checks that `config_folder`, `cluster_name`, `GIT_USERNAME`, and `GIT_TOKEN` are provided and not empty
2. **Load environment variables**: Loads `env.json` from config folder to get `DEPLOY_KUBECONFIG`, `ARGOCD_PASSWORD`, `admin_group_ID`, and optionally `domain`
3. **Read cluster config**: Reads the cluster configuration YAML file at `{{ config_folder }}/{{ cluster_name }}.yaml`
4. **Extract cluster facts**: Extracts `ingress_resolver_email` from the cluster configuration
5. **Load registry credentials**: Reads the registry credentials JSON file from config folder
6. **Parse registry credentials**: Parses the JSON to extract `username` and `password`
7. **Validate registry credentials**: Checks that username and password are not empty
8. **Run MAIA_build_images**: Executes the `MAIA_build_images` command with all necessary environment variables to build Docker images using Kaniko
9. **Show build output**: Displays the output from the build process
10. **Login to ArgoCD**: Logs into ArgoCD using CLI with multiple fallback methods (domain, localhost:port, cluster IP)
11. **Sync maia-kube**: Synchronizes the `{{ maia_project_id }}-maia-kube` ArgoCD application and waits for completion
12. **Sync maia-dashboard**: Synchronizes the `{{ maia_project_id }}-maia-dashboard` ArgoCD application and waits for completion
13. **Sync maia-filebrowser**: Synchronizes the `{{ maia_project_id }}-maia-filebrowser` ArgoCD application and waits for completion

## Build Process Details

### Kaniko Build

The role uses Kaniko to build Docker images within Kubernetes without requiring privileged access. Kaniko:
- Runs as a Kubernetes job
- Pulls the MAIA source code from Git
- Builds Docker images for maia-kube, maia-dashboard, and maia-filebrowser
- Pushes built images to the specified container registry
- Uses Git credentials for repository access
- Uses registry credentials for pushing images

### Environment Variables

The `MAIA_build_images` command is executed with the following environment variables:
- `config_folder`: Path to configuration folder
- `cluster_name`: Name of the cluster
- `ingress_resolver_email`: Email for Let's Encrypt certificates
- `MAIA_GIT_REPO_URL`: Git repository URL
- `GIT_USERNAME`: Git username for authentication
- `GIT_TOKEN`: Git token for authentication
- `docker_build_project_chart`: Helm chart name
- `docker_build_project_repo`: Helm chart repository
- `docker_build_project_version`: Helm chart version
- `KUBECONFIG`: Path to kubeconfig file
- `admin_group_ID`: Admin group identifier
- `CLUSTER_ADDRESS`: Kubernetes API address
- `registry_path`: Container registry path
- `argocd_namespace`: ArgoCD namespace
- `JSON_KEY_PATH`: Path to registry credentials file
- `registry_username`: Registry username (from credentials file)
- `registry_password`: Registry password (from credentials file)
- `registry_server`: Registry server URL

### ArgoCD Synchronization

After building images, the role logs into ArgoCD and synchronizes three applications:
1. **maia-kube**: Backend services and API for MAIA
2. **maia-dashboard**: Frontend dashboard for MAIA
3. **maia-filebrowser**: File browser component for MAIA

The role uses multiple fallback methods for ArgoCD login:
1. Domain-based: `argocd.{{ domain }}`
2. Localhost with port forwarding: `localhost:{{ argocd_port }}`
3. Cluster IP: Retrieved from ArgoCD server service

Each application sync waits for the application to become healthy before continuing to the next one.

### Registry Support

The role supports multiple container registries:
- **Docker Hub**: Use `registry_base: "https://index.docker.io/v1/"` with your Docker Hub username as `registry_path`
- **Harbor**: Use `registry_base: "https://harbor.example.com"` with project name as `registry_path`
- **GitHub Container Registry**: Use `registry_base: "https://ghcr.io"` with your GitHub username/org as `registry_path`
- **Custom OCI registry**: Provide the full URL as `registry_base`

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - build_images
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory.ini` contains your test hosts:
   ```ini
   [all]
   localhost
   ```

2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with required variables:
     ```json
     {
       "DEPLOY_KUBECONFIG": "/path/to/kubeconfig.yaml",
       "ARGOCD_PASSWORD": "admin-password",
       "admin_group_ID": "maia-admins",
       "domain": "example.com"
     }
     ```
   - Cluster configuration file `{{ cluster_name }}.yaml` with:
     ```yaml
     ingress_resolver_email: admin@example.com
     ```
   - Registry credentials file `maia-registry-credentials.json`:
     ```json
     {
       "username": "registry-user",
       "password": "registry-password"
     }
     ```

3. **Ensure prerequisites are met**:
   - Kubernetes cluster is accessible via kubeconfig
   - ArgoCD is installed and accessible
   - `MAIA_build_images` command is available in PATH
   - Valid Git credentials for MAIA repository
   - Valid container registry credentials

4. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e config_folder=/path/to/config \
     -e cluster_name=test-cluster \
     -e GIT_USERNAME=github-user \
     -e GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

5. **Test with auto sync**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e config_folder=/path/to/config \
     -e cluster_name=test-cluster \
     -e GIT_USERNAME=github-user \
     -e GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx \
     -e auto_sync=true
   ```

### Manual Verification

After running the role, verify the image build process:

1. **Check build output**: Review the Ansible output for the `MAIA_build_images` execution. Look for:
   - Kaniko job creation
   - Image build progress
   - Image push to registry
   - Build completion status

2. **Verify images in registry**: Check that images were pushed to the container registry:
   ```bash
   # For Docker Hub
   curl -s "https://hub.docker.com/v2/repositories/${registry_path}/maia-kube/tags/" | jq
   
   # For Harbor
   curl -k -u "${username}:${password}" \
     "https://harbor.example.com/api/v2.0/projects/${registry_path}/repositories/maia-kube/artifacts"
   ```

3. **Check ArgoCD login**: Verify the ArgoCD CLI login output in the Ansible output

4. **Check ArgoCD applications**: Verify applications exist and are synced:
   ```bash
   export KUBECONFIG={{ DEPLOY_KUBECONFIG }}
   argocd login localhost:{{ argocd_port }} --username admin --password "$ARGOCD_PASSWORD" --insecure
   argocd app list | grep {{ maia_project_id }}
   ```

5. **Verify application sync status**:
   ```bash
   argocd app get {{ maia_project_id }}-maia-kube
   argocd app get {{ maia_project_id }}-maia-dashboard
   argocd app get {{ maia_project_id }}-maia-filebrowser
   ```
   Each application should show `Sync Status: Synced` and `Health Status: Healthy`.

6. **Check deployed pods**: Verify pods are running with new images:
   ```bash
   kubectl get pods -n maia-kube -o wide
   kubectl get pods -n maia-dashboard -o wide
   kubectl get pods -n maia-filebrowser -o wide
   ```

7. **Verify image versions**: Check that pods are using the newly built images:
   ```bash
   kubectl get pods -n maia-kube -o jsonpath='{.items[*].spec.containers[*].image}'
   ```

8. **Check Kaniko jobs**: Verify Kaniko build jobs completed successfully:
   ```bash
   kubectl get jobs -n default | grep maia-build
   kubectl logs job/maia-build-<job-name> -n default
   ```

### Test Scenarios

- **Default build**: Test with all default values
- **Custom registry**: Test with different container registries (Docker Hub, Harbor, custom)
- **Custom branch**: Test building from different Git branches
- **Custom chart version**: Test with different build chart versions
- **With auto sync**: Test with `auto_sync: true`
- **Without auto sync**: Test with `auto_sync: false` and manual sync
- **Missing credentials**: Test error handling when credentials are missing
- **Invalid Git credentials**: Test error handling with invalid Git credentials
- **Invalid registry credentials**: Test error handling with invalid registry credentials
- **Missing kubeconfig**: Test error handling when kubeconfig is invalid

## Notes

- **Required variables**: The role requires `config_folder`, `cluster_name`, `GIT_USERNAME`, and `GIT_TOKEN`. Ensure these are provided before running the role.
- **Config folder structure**: The config folder must contain `env.json`, `{{ cluster_name }}.yaml`, and `{{ credentials_json_filename }}`. Ensure these files exist with correct format.
- **Git credentials**: Store Git credentials securely using Ansible Vault or environment variables. Never commit credentials to version control.
- **Registry credentials**: Store registry credentials securely. The credentials JSON file should have restricted permissions (0600).
- **ArgoCD prerequisite**: ArgoCD must be installed and accessible before running this role. Use the `argocd` role first if not already installed.
- **MAIA_build_images command**: This command must be available in the PATH. It's typically installed as part of the MAIA installation process.
- **Build time**: Building Docker images can take several minutes depending on cluster resources and image sizes.
- **Auto sync**: If `auto_sync` is `false`, you must manually sync the applications in ArgoCD after the build completes.
- **Network access**: The role requires internet access to:
  - Clone Git repositories
  - Pull base images for building
  - Push images to the registry
  - Access ArgoCD
- **Kubernetes resources**: Kaniko builds consume CPU and memory resources. Ensure your cluster has sufficient capacity.
- **Image tags**: The build process typically tags images with Git commit SHA or timestamp. Check the build output for specific tags.
- **Rollback**: If the build fails or produces bad images, use ArgoCD to rollback to previous versions.
- **Idempotency**: The role can be run multiple times. Each run will trigger a new build with updated images.
- **Error handling**: The role includes error handling for missing credentials and failed validations. ArgoCD sync errors are ignored (`ignore_errors: true`) to allow manual intervention.

## Troubleshooting

### Build Fails with Git Authentication Error

**Problem**: Cannot clone Git repository

**Solution**:
- Verify `GIT_USERNAME` and `GIT_TOKEN` are correct
- Check that the token has read access to the repository
- Verify the repository URL is correct
- Check network connectivity to GitHub

### Build Fails with Registry Push Error

**Problem**: Cannot push images to registry

**Solution**:
- Verify registry credentials in the JSON file are correct
- Check that the registry user has push permissions
- Verify the registry URL and path are correct
- Check network connectivity to the registry
- For Docker Hub, ensure you're not hitting rate limits

### ArgoCD Login Fails

**Problem**: Cannot log into ArgoCD via CLI

**Solution**:
- Verify `ARGOCD_PASSWORD` in `env.json` is correct
- Check that ArgoCD is running: `kubectl get pods -n {{ argocd_namespace }}`
- Verify port forwarding is set up correctly
- Try logging in manually: `argocd login localhost:{{ argocd_port }}`
- Check ArgoCD server logs: `kubectl logs -n {{ argocd_namespace }} -l app.kubernetes.io/name=argocd-server`

### Application Sync Fails

**Problem**: ArgoCD application sync fails or times out

**Solution**:
- Check application status: `argocd app get {{ maia_project_id }}-<app-name>`
- View application events in ArgoCD UI
- Check pod logs: `kubectl logs -n <namespace> <pod-name>`
- Verify image exists in registry
- Check image pull secrets are configured correctly
- Increase ArgoCD sync timeout if needed

### MAIA_build_images Command Not Found

**Problem**: Command not available in PATH

**Solution**:
- Install MAIA CLI tools
- Check that the command is executable: `which MAIA_build_images`
- Verify PATH includes the directory with MAIA commands
- Install MAIA toolkit: `pip install maia-toolkit` (or equivalent)

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project build automation.

**Author**: Simone Bendazzoli <simben@kth.se>  
**Company**: MAIA Project

For more information about MAIA, visit: https://github.com/minnelab/MAIA
