# MAIA Core Layer Role

This Ansible role installs and configures the MAIA Core layer components on a Kubernetes cluster. It deploys core infrastructure including observability (Prometheus, Loki, Tempo), ingress (Traefik), storage (MinIO, NFS), GPU support, and GitOps tooling via ArgoCD applications.

## Description

The `maia_core_layer` role automates the installation and configuration of MAIA Core infrastructure components. It performs the following tasks:

1. **Loads environment variables** from `env.json` in the config folder (including `cluster_name` and `DEPLOY_KUBECONFIG`)
2. **Reads cluster configuration** to extract cluster information
3. **Creates MAIA Core namespaces** required for core components
4. **Runs MAIA Core Toolkit installer** to deploy core applications via ArgoCD
5. **Installs Prometheus stack** for observability and monitoring
6. **Installs ArgoCD CLI** for application management
7. **Logs into ArgoCD** for application synchronization
8. **Synchronizes ArgoCD applications** for core components (Traefik, cert-manager, GPU operator, etc.)
9. **Handles self-signed certificates** by restarting deployments if needed

This role is designed to be used as part of the MAIA installation process, particularly in the `install_maia_core.yaml` playbook, but can also be used standalone for MAIA Core installation.

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
- **Kubeconfig access**: `DEPLOY_KUBECONFIG` must be set in `env.json` or `KUBECONFIG` environment variable
- **Config folder**: Must contain `env.json` and cluster configuration YAML file
- **ArgoCD**: Must be installed and accessible (typically via the `argocd` role)
- **Helm**: Must be installed for Prometheus stack installation
- **Internet access**: Required to download ArgoCD CLI and Helm charts

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `maia_core_namespaces` | `[observability, metrics-server, traefik, metallb-system, cert-manager, gpu-operator, maia-core-toolkit, ingress-nginx, minio-operator, authentication, maia-webhooks, nfs-server-provisioner]` | list | MAIA Core namespaces to create |
| `auto_sync` | `true` | boolean | Enable automatic ArgoCD application synchronization |
| `prometheus_values_path` | `maia-core/prometheus_values/prometheus_values.yaml` | string | Path to Prometheus values file |
| `prometheus_chart_version` | `45.5.0` | string | Prometheus chart version |
| `prometheus_chart_name` | `prometheus-community/kube-prometheus-stack` | string | Prometheus Helm chart name |
| `prometheus_release_name` | `maia-core-prometheus` | string | Prometheus Helm release name |
| `argocd_port` | `8080` | integer | ArgoCD port for CLI login |
| `argocd_login_retries` | `3` | integer | Number of retries for ArgoCD login |
| `argocd_login_retry_delay` | `10` | integer | Delay in seconds between login retries |
| `argocd_sync_retries` | `3` | integer | Number of retries for ArgoCD sync |
| `argocd_sync_retry_delay` | `10` | integer | Delay in seconds between sync retries |
| `maia_core_argocd_applications` | `[maia-core-traefik, maia-core-cert-manager, maia-core-gpu-operator, maia-core-metallb, maia-core-loki, maia-core-tempo, maia-core-metrics-server, maia-core-toolkit, maia-core-gpu-booking, maia-core-minio-operator, maia-core-nfs-provisioner]` | list | ArgoCD applications to sync |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `cluster_name`, `DEPLOY_KUBECONFIG`, and other environment variables
  - Cluster config YAML: Located at `{{ config_folder }}/{{ cluster_name }}.yaml`
- **Example**: `config_folder: /opt/maia/config`

**Note**: The `env.json` file must exist and contain `cluster_name` and `DEPLOY_KUBECONFIG`. The cluster configuration file must exist and contain cluster configuration.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `maia_core_namespaces`
- **Type**: `list` (of strings)
- **Default**: `[observability, metrics-server, traefik, metallb-system, cert-manager, gpu-operator, maia-core-toolkit, ingress-nginx, minio-operator, authentication, maia-webhooks, nfs-server-provisioner]`
- **Description**: List of Kubernetes namespaces to create for MAIA Core components.
- **Example**: 
  ```yaml
  maia_core_namespaces:
    - observability
    - traefik
    - cert-manager
  ```

### `auto_sync`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether ArgoCD applications should be automatically synchronized. When enabled, the role will install ArgoCD CLI, login, and sync all configured applications.
- **Example**: `auto_sync: false`

### `prometheus_values_path`
- **Type**: `string`
- **Default**: `maia-core/prometheus_values/prometheus_values.yaml`
- **Description**: Path to the Prometheus values file relative to `config_folder`. This file contains custom configuration for the Prometheus stack.
- **Example**: `prometheus_values_path: custom/prometheus/values.yaml`

### `prometheus_chart_version`
- **Type**: `string`
- **Default**: `45.5.0`
- **Description**: Version of the Prometheus Helm chart to install.
- **Example**: `prometheus_chart_version: 46.0.0`

### `prometheus_chart_name`
- **Type**: `string`
- **Default**: `prometheus-community/kube-prometheus-stack`
- **Description**: Helm chart name for the Prometheus stack.
- **Example**: `prometheus_chart_name: prometheus-community/kube-prometheus-stack`

### `prometheus_release_name`
- **Type**: `string`
- **Default**: `maia-core-prometheus`
- **Description**: Helm release name for the Prometheus installation.
- **Example**: `prometheus_release_name: my-prometheus`

### `argocd_port`
- **Type**: `integer`
- **Default**: `8080`
- **Description**: Port number for ArgoCD CLI login. Should match the port forwarding configuration from the ArgoCD role.
- **Example**: `argocd_port: 9090`

### `argocd_login_retries`
- **Type**: `integer`
- **Default**: `3`
- **Description**: Number of retries when attempting to login to ArgoCD via CLI.
- **Example**: `argocd_login_retries: 5`

### `argocd_login_retry_delay`
- **Type**: `integer`
- **Default**: `10`
- **Description**: Delay in seconds between ArgoCD login retry attempts.
- **Example**: `argocd_login_retry_delay: 15`

### `argocd_sync_retries`
- **Type**: `integer`
- **Default**: `3`
- **Description**: Number of retries when synchronizing ArgoCD applications.
- **Example**: `argocd_sync_retries: 5`

### `argocd_sync_retry_delay`
- **Type**: `integer`
- **Default**: `10`
- **Description**: Delay in seconds between ArgoCD application sync retry attempts.
- **Example**: `argocd_sync_retry_delay: 15`

### `maia_core_argocd_applications`
- **Type**: `list` (of strings)
- **Default**: `[maia-core-traefik, maia-core-cert-manager, maia-core-gpu-operator, maia-core-metallb, maia-core-loki, maia-core-tempo, maia-core-metrics-server, maia-core-toolkit, maia-core-gpu-booking, maia-core-minio-operator, maia-core-nfs-provisioner]`
- **Description**: List of ArgoCD application names to synchronize. These applications should be created by the MAIA Core Toolkit installer.
- **Example**: 
  ```yaml
  maia_core_argocd_applications:
    - maia-core-traefik
    - maia-core-cert-manager
  ```

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Install MAIA Core layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_core_layer
      vars:
        config_folder: /opt/maia/config
```

**Important**: Ensure `env.json` exists in the config folder and contains:
- `cluster_name`: Name of the cluster
- `DEPLOY_KUBECONFIG`: Path to kubeconfig file
- Other required environment variables for MAIA Core Toolkit installer

### Without Auto Sync

Disable automatic ArgoCD application synchronization:

```yaml
- name: Install MAIA Core layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_core_layer
      vars:
        config_folder: /opt/maia/config
        auto_sync: false
```

### Custom Prometheus Configuration

Specify custom Prometheus values file:

```yaml
- name: Install MAIA Core layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_core_layer
      vars:
        config_folder: /opt/maia/config
        prometheus_values_path: custom/prometheus/values.yaml
        prometheus_chart_version: 46.0.0
```

### Custom ArgoCD Applications

Sync only specific ArgoCD applications:

```yaml
- name: Install MAIA Core layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_core_layer
      vars:
        config_folder: /opt/maia/config
        maia_core_argocd_applications:
          - maia-core-traefik
          - maia-core-cert-manager
          - maia-core-toolkit
```

### Custom Retry Settings

Adjust retry behavior for slower systems:

```yaml
- name: Install MAIA Core layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_core_layer
      vars:
        config_folder: /opt/maia/config
        argocd_login_retries: 5
        argocd_login_retry_delay: 20
        argocd_sync_retries: 5
        argocd_sync_retry_delay: 20
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e config_folder=/opt/maia/config \
  -e auto_sync=false
```

### In install_maia_core.yaml

This role is used as part of the MAIA installation process:

```yaml
- name: Run MAIA Core Installation
  hosts: localhost
  vars_files:
    - "{{ config_folder }}/env.json"
    - "{{ config_folder }}/{{ cluster_name }}.yaml"
  roles:
    - maia.installation.maia_core_layer
```

### Standalone Playbook Example

Create a dedicated playbook for MAIA Core installation:

```yaml
---
- name: Install MAIA Core layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_core_layer
      vars:
        config_folder: /opt/maia/config
        auto_sync: true
        prometheus_chart_version: 45.5.0
        argocd_port: 8080
        argocd_login_retries: 3
        argocd_sync_retries: 3
```

## Tasks

The role performs the following tasks:

1. **Load environment variables**: Loads `env.json` from config folder to get `cluster_name`, `DEPLOY_KUBECONFIG`, and other variables
2. **Read cluster config**: Reads the cluster configuration YAML file
3. **Extract cluster name**: Extracts `cluster_name` from the cluster configuration
4. **Create namespaces**: Creates all required MAIA Core namespaces
5. **Run MAIA Core Toolkit installer**: Executes `MAIA_install_core_toolkit` to deploy core applications via ArgoCD
6. **Install Prometheus stack**: Installs Prometheus stack using Helm for observability
7. **Install ArgoCD CLI** (conditional): Downloads and installs ArgoCD CLI if `auto_sync` is enabled
8. **Login to ArgoCD** (conditional): Logs into ArgoCD using CLI if `auto_sync` is enabled
9. **Sync ArgoCD applications** (conditional): Synchronizes all configured ArgoCD applications if `auto_sync` is enabled
10. **Handle self-signed certificates** (conditional): Restarts deployments if self-signed certificates are enabled

## MAIA Core Components

### Namespaces

The role creates the following namespaces by default:
- `observability`: For Prometheus, Grafana, Loki, Tempo
- `metrics-server`: For Kubernetes metrics collection
- `traefik`: For ingress controller
- `metallb-system`: For load balancer
- `cert-manager`: For certificate management
- `gpu-operator`: For GPU support
- `maia-core-toolkit`: For MAIA Core toolkit components
- `ingress-nginx`: For additional ingress support
- `minio-operator`: For object storage
- `authentication`: For authentication components
- `maia-webhooks`: For MAIA webhooks
- `nfs-server-provisioner`: For NFS storage provisioning

### ArgoCD Applications

The role synchronizes the following ArgoCD applications by default:
- `maia-core-traefik`: Ingress controller
- `maia-core-cert-manager`: Certificate management
- `maia-core-gpu-operator`: GPU operator for NVIDIA GPUs
- `maia-core-metallb`: Load balancer
- `maia-core-loki`: Log aggregation
- `maia-core-tempo`: Distributed tracing
- `maia-core-metrics-server`: Kubernetes metrics
- `maia-core-toolkit`: MAIA Core toolkit
- `maia-core-gpu-booking`: GPU booking system
- `maia-core-minio-operator`: Object storage operator
- `maia-core-nfs-provisioner`: NFS storage provisioner

### Prometheus Stack

The role installs the Prometheus stack (kube-prometheus-stack) which includes:
- Prometheus for metrics collection
- Grafana for visualization
- Alertmanager for alerting
- Node exporter and other exporters

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - maia_core_layer
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory.ini` contains your test hosts:
   ```ini
   [all]
   localhost
   ```

2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with `cluster_name` and `DEPLOY_KUBECONFIG`
   - Cluster configuration YAML file at `{{ config_folder }}/{{ cluster_name }}.yaml`
   - Prometheus values file at `{{ config_folder }}/{{ prometheus_values_path }}`

3. **Ensure Kubernetes cluster is accessible**: The test requires a valid kubeconfig and accessible Kubernetes cluster with ArgoCD installed.

4. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e config_folder=/path/to/config
   ```

5. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e config_folder=/path/to/config \
     -e auto_sync=false \
     -e prometheus_chart_version=46.0.0
   ```

### Manual Verification

After running the role, verify the MAIA Core installation:

1. **Check namespaces are created**:
   ```bash
   kubectl get namespaces | grep -E "(observability|traefik|cert-manager|gpu-operator)"
   ```

2. **Check MAIA Core Toolkit installer output**:
   - Review the Ansible output for `MAIA_install_core_toolkit` execution
   - Verify ArgoCD applications were created

3. **Check Prometheus stack is installed**:
   ```bash
   helm list -n observability
   kubectl get pods -n observability
   ```

4. **Check ArgoCD applications**:
   ```bash
   argocd app list
   ```
   Should show all MAIA Core applications.

5. **Verify ArgoCD applications are synced**:
   ```bash
   argocd app get maia-core-traefik
   ```
   Should show application status and sync state.

6. **Check core components are running**:
   ```bash
   kubectl get pods -n traefik
   kubectl get pods -n cert-manager
   kubectl get pods -n gpu-operator
   ```

7. **Verify Prometheus is accessible**:
   ```bash
   kubectl port-forward -n observability svc/maia-core-prometheus-kube-prom-prometheus 9090:9090
   ```
   Then access `http://localhost:9090` in a browser.

8. **Check Grafana is accessible**:
   ```bash
   kubectl port-forward -n observability svc/maia-core-prometheus-grafana 3000:80
   ```
   Then access `http://localhost:3000` in a browser.

### Test Scenarios

- **Default installation**: Test with all default values
- **Without auto sync**: Test with `auto_sync: false`
- **Custom Prometheus version**: Test with different Prometheus chart versions
- **Custom applications**: Test with subset of ArgoCD applications
- **Custom retry settings**: Test with different retry counts and delays
- **Missing env.json**: Test error handling when env.json is missing
- **Invalid kubeconfig**: Test error handling when kubeconfig is invalid

## Notes

- **env.json requirement**: The role requires `env.json` in the config folder with `cluster_name` and `DEPLOY_KUBECONFIG`. Ensure these are set before running the role.
- **Cluster configuration**: The cluster configuration YAML file must exist at `{{ config_folder }}/{{ cluster_name }}.yaml` and contain valid cluster configuration.
- **ArgoCD prerequisite**: ArgoCD must be installed and accessible before running this role. Install ArgoCD using the `argocd` role first.
- **MAIA Core Toolkit**: The role executes `MAIA_install_core_toolkit` which creates ArgoCD applications. Ensure this command is available in the PATH.
- **Prometheus values**: The Prometheus values file must exist at the specified path. Create this file before running the role if using custom configuration.
- **Auto sync**: When `auto_sync` is enabled, the role will attempt to synchronize all ArgoCD applications. This may take several minutes.
- **Self-signed certificates**: If `selfsigned: true` is set in the cluster config, the role will restart Traefik and CoreDNS deployments to pick up new certificates.
- **kubernetes.core collection**: The role requires the `kubernetes.core` Ansible collection. Install it with `ansible-galaxy collection install kubernetes.core`.
- **Helm requirement**: Helm must be installed and configured to access the Prometheus chart repository.
- **Internet access**: The role requires internet access to download ArgoCD CLI and Helm charts.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
