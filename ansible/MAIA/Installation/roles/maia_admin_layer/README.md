# MAIA Admin Layer Role

This Ansible role installs and configures the MAIA Admin layer on a Kubernetes cluster. It provisions identity and access management, registry, dashboards, and supporting services via the MAIA Admin Toolkit and ArgoCD.

## Description

The `maia_admin_layer` role automates deployment of admin-facing MAIA components. It:
1. Loads environment variables from `env.json` in the provided `config_folder`
2. Reads the cluster configuration to extract `cluster_name` and `domain`
3. Creates required Kubernetes namespaces
4. Runs the MAIA Admin Toolkit installer
5. Optionally installs ArgoCD CLI, logs in, and synchronizes ArgoCD applications
6. Applies Keycloak and MinIO configuration needed for the admin stack

## Requirements

### Ansible Version
- Minimum Ansible version: 2.1

### Target Systems
- Linux control host with access to the target Kubernetes cluster
- Kubeconfig available for the target cluster

### Dependencies
- Ansible collections:
  - `kubernetes.core`
- No role dependencies

### System Requirements
- Kubernetes cluster reachable via `DEPLOY_KUBECONFIG`
- Config folder containing `env.json` and the cluster config YAML (`{{ cluster_name }}.yaml`)
- ArgoCD installed on the cluster

## Default Values

The following defaults are defined in `defaults/main.yml`:

| Variable | Default | Type | Description |
| --- | --- | --- | --- |
| `maia_admin_namespaces` | `[harbor, keycloak, maia-admin-toolkit, maia-dashboard, cattle-system]` | list | Namespaces created for MAIA Admin components |
| `auto_sync` | `true` | bool | Enable ArgoCD synchronization and post-install tasks |
| `argocd_port` | `8080` | integer | ArgoCD port for CLI login |

## Required Values

| Variable | Type | Description |
| --- | --- | --- |
| `config_folder` | string | Path to config folder containing `env.json` and `{{ cluster_name }}.yaml` |

## Optional Values

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `maia_admin_namespaces` | list | See defaults | Override namespaces created by the role |
| `auto_sync` | bool | `true` | Disable to skip ArgoCD sync and post-install actions |
| `argocd_port` | integer | `8080` | ArgoCD port for CLI login |
## Usage

### Basic Usage

```yaml
- name: Install MAIA Admin layer
  hosts: localhost
  roles:
    - role: maia.installation.maia_admin_layer
      vars:
        config_folder: /opt/maia/config
```

### Without Auto Sync

```yaml
- name: Install MAIA Admin layer without syncing ArgoCD apps
  hosts: localhost
  roles:
    - role: maia.installation.maia_admin_layer
      vars:
        config_folder: /opt/maia/config
        auto_sync: false
```

### Running Tests

The role includes a simple test playbook in `tests/test.yml`:

```bash
ansible-playbook -i tests/inventory.ini tests/test.yml \
  -e config_folder=/path/to/config
```

Ensure your config folder contains `env.json`, the cluster config YAML, and that the kubeconfig referenced by `DEPLOY_KUBECONFIG` is accessible.

## Tasks Overview

Key tasks executed by the role:
- Load environment and cluster configuration
- Create namespaces for admin components
- Run `MAIA_install_admin_toolkit`
- (When `auto_sync` is true) Install ArgoCD CLI, log in, sync admin ArgoCD applications
- Configure Keycloak and MinIO resources used by the admin layer

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.

