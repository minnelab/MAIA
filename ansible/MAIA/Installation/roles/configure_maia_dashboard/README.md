# Configure MAIA Dashboard Role

This Ansible role configures the MAIA Dashboard by running the Admin Toolkit installer and synchronizing the dashboard ArgoCD application.

## Description

The `configure_maia_dashboard` role:
1. Loads environment variables from `env.json` in the specified `config_folder`
2. Reads the cluster configuration YAML (`{{ cluster_name }}.yaml`) from the same folder
3. Extracts `cluster_name` and `domain` from the cluster configuration
4. Runs `MAIA_install_admin_toolkit` with required environment variables to configure the dashboard
5. Optionally logs into ArgoCD and synchronizes the `maia-admin-maia-dashboard` application
6. Optionally restarts the `maia-admin-maia-dashboard` deployment to apply changes

It is intended to be used after the MAIA Admin layer has been installed and ArgoCD is accessible.

## Requirements

### Ansible Version
- Minimum Ansible version: 2.1

### Target Systems
- Linux control host with:
  - Network access to the Kubernetes cluster via kubeconfig
  - Network access to ArgoCD (either `localhost:8080` or `argocd.<domain>`)
  - `MAIA_install_admin_toolkit` command available in PATH
  - ArgoCD CLI installed (if `auto_sync` is enabled)
  - `kubectl` installed (if `auto_sync` is enabled)

### Dependencies
- No role dependencies

## Default Values

Defined in `defaults/main.yml`:

| Variable | Default | Type | Description |
| --- | --- | --- | --- |
| `config_folder` | `/opt/maia/config` | string | Folder containing `env.json` and cluster YAML |
| `auto_sync` | `true` | boolean | Enable ArgoCD application synchronization and deployment restart |

## Required Values

The role requires a valid cluster configuration file at:
- `{{ config_folder }}/{{ cluster_name }}.yaml`

This file must contain at least:
- `cluster_name`
- `domain`

The `cluster_name` is expected to be provided via `env.json` or from the calling playbook.

Additionally, the following environment variables must be provided (typically from `env.json`):
- `DEPLOY_KUBECONFIG`: Path to kubeconfig file
- `argocd_namespace`: Namespace where ArgoCD is installed
- `admin_group_ID`: Keycloak admin group ID
- `admin_project_chart`: Helm chart reference for admin project
- `admin_project_repo`: Repository containing admin project chart
- `admin_project_version`: Version of admin project chart
- `keycloak_client_secret`: Client secret for Keycloak
- `minio_admin_password`: Admin password for MinIO tenant
- `minio_root_password`: Root password for MinIO tenant
- `dashboard_api_secret`: API secret for MAIA dashboard
- `mysql_dashboard_password`: Password for dashboard MySQL backend
- `ARGOCD_PASSWORD`: Password for ArgoCD CLI login

## Optional Values

All other variables are optional and can be overridden when using the role:

### `auto_sync`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Enable ArgoCD application synchronization and deployment restart.

If `auto_sync` is set to `false`, the role will skip ArgoCD login, application synchronization, and deployment restart steps.

## Usage

### Basic Usage

```yaml
- name: Configure MAIA Dashboard
  hosts: localhost
  roles:
    - role: maia.installation.configure_maia_dashboard
      vars:
        config_folder: /opt/maia/config
```

### Without Auto Sync

```yaml
- name: Configure MAIA Dashboard without syncing
  hosts: localhost
  roles:
    - role: maia.installation.configure_maia_dashboard
      vars:
        config_folder: /opt/maia/config
        auto_sync: false
```

## Tasks Overview

Key tasks performed by the role:
- Load environment variables from `env.json`
- Read and decode the cluster configuration YAML
- Extract `cluster_name` and `domain` from cluster config
- Run `MAIA_install_admin_toolkit` with required environment variables
- (Conditional) Login to ArgoCD using CLI
- (Conditional) Synchronize `maia-admin-maia-dashboard` ArgoCD application
- (Conditional) Restart `maia-admin-maia-dashboard` deployment

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.


