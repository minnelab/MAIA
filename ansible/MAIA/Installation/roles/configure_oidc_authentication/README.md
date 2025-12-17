# Configure OIDC Authentication Role

This Ansible role configures OIDC-related settings for the MAIA environment by reading cluster configuration and interacting with external systems such as Rancher.

## Description

The `configure_oidc_authentication` role:
1. Loads environment variables from `env.json` in the specified `config_folder`
2. Reads the cluster configuration YAML (`{{ cluster_name }}.yaml`) from the same folder
3. Extracts `domain` and `rancher_password` from the cluster configuration
4. Logs in to Rancher and obtains an API token
5. Accepts the Rancher EULA using the obtained token

It is intended to be used after the cluster and Rancher are up and reachable.

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
- name: Configure OIDC authentication bits (Rancher EULA, etc.)
  hosts: localhost
  roles:
    - role: maia.installation.configure_oidc_authentication
      vars:
        config_folder: /opt/maia/config
```

## Tasks Overview

Key tasks performed by the role:
- Load environment variables from `env.json`
- Read and decode the cluster configuration YAML
- Extract `domain` and `rancher_password`
- Obtain a Rancher token via the public login endpoint
- Accept the Rancher end-user license agreement (EULA)

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.


