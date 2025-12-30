# Get Kubeconfig from Rancher Local Role

This Ansible role retrieves a kubeconfig for the local Rancher-managed cluster using the Rancher API and stores it in the MAIA configuration folder.

## Description

The `get_kubeconfig_from_rancher_local` role:
1. Loads environment variables from `env.json` in the specified `config_folder`
2. Reads the cluster configuration YAML (`{{ cluster_name }}.yaml`) from the same folder
3. Extracts `domain` and `rancher_password` from the cluster configuration
4. Logs into Rancher and obtains an API token
5. Creates a Rancher API key and extracts its secret
6. Calls the Rancher `generateKubeconfig` action for the `local` cluster
7. Saves the returned kubeconfig to `{{ config_folder }}/{{ kubeconfig_file }}`
8. Extracts the Rancher bearer token from the kubeconfig and writes it back into the cluster configuration as `rancher_token`

## Requirements

### Ansible Version
- Minimum Ansible version: 2.1

### Target Systems
- Linux control host with:
  - Network access to the Rancher endpoint at `https://mgmt.<domain>`
  - `curl` and `jq` installed

### Dependencies
- No role dependencies

## Default Values

Defined in `defaults/main.yml`:

| Variable | Default | Type | Description |
| --- | --- | --- | --- |
| `config_folder` | `/opt/maia/config` | string | Folder containing `env.json` and cluster YAML |
| `kubeconfig_file` | `local.yaml` | string | File name for the kubeconfig written inside `config_folder` |

## Required Values

The role requires a valid cluster configuration file at:
- `{{ config_folder }}/{{ cluster_name }}.yaml`

This file must contain at least:
- `domain`
- `rancher_password`

The `cluster_name` is expected to be provided via `env.json` or from the calling playbook.

## Usage

### Basic Usage

```yaml
- name: Get kubeconfig for Rancher local cluster
  hosts: localhost
  roles:
    - role: maia.installation.get_kubeconfig_from_rancher_local
      vars:
        config_folder: /opt/maia/config
```

### Custom Kubeconfig File Name

```yaml
- name: Get kubeconfig for Rancher local cluster with custom file name
  hosts: localhost
  roles:
    - role: maia.installation.get_kubeconfig_from_rancher_local
      vars:
        config_folder: /opt/maia/config
        kubeconfig_file: local-from-rancher.yaml
```

## Tasks Overview

Key tasks performed by the role:
- Load environment variables from `env.json`
- Read and decode the cluster configuration YAML
- Extract `domain` and `rancher_password`
- Login to Rancher and obtain a token
- Create a Rancher API key and capture its secret
- Call `generateKubeconfig` for the `local` cluster
- Save the kubeconfig YAML to `config_folder`
- Extract `rancher_token` from the kubeconfig and write it back into the cluster configuration

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.


