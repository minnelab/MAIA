# Configure OIDC Authentication Role

This Ansible role configures OIDC-related settings for the MAIA environment by reading cluster configuration and interacting with external systems such as Rancher.

## Description

The `configure_oidc_authentication` role:
1. Loads environment variables from `env.json` in the specified `config_folder`
2. Reads the cluster configuration YAML (`{{ cluster_name }}.yaml`) from the same folder
3. Extracts `domain` and `rancher_password` from the cluster configuration
4. Logs in to Rancher and obtains an API token
5. Accepts the Rancher EULA using the obtained token
6. Configures Harbor with OIDC authentication

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
| `configure_rancher` | `true` | boolean | Configure Rancher with OIDC authentication. |
| `configure_harbor` | `true` | boolean | Configure Harbor with OIDC authentication. |
| `harbor_admin_user` | `admin` | string | Harbor admin user. |
| `harbor_admin_pass` | `Harbor12345` | string | Harbor admin password. |
## Required Values

The role requires a valid cluster configuration file at:
- `{{ config_folder }}/{{ cluster_name }}.yaml`

This file must contain at least:
- `domain`
- `rancher_password`

The `cluster_name` is expected to be provided via `env.json` or from the calling playbook.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `configure_rancher`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Configure Rancher with OIDC authentication.

If `configure_rancher` is set to `false`, the role will not configure Rancher.

### `configure_harbor`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Configure Harbor with OIDC authentication.

If `configure_harbor` is set to `false`, the role will not configure Harbor.

### `harbor_admin_user`
- **Type**: `string`
- **Default**: `admin`
- **Description**: Harbor admin user.

### `harbor_admin_pass`
- **Type**: `string`
- **Default**: `Harbor12345`
- **Description**: Harbor admin password.

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


