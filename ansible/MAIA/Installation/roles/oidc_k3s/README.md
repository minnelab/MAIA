# OIDC k3s Role

This Ansible role enables OIDC (OpenID Connect) authentication for **k3s**. It configures the Kubernetes API server managed by k3s to authenticate users using JWT tokens from an OIDC provider (typically Keycloak).

## Description

The `oidc_k3s` role automates the configuration of OIDC authentication for k3s clusters. It performs the following tasks:

1. **Loads environment variables** from `env.json` in the config folder (including `cluster_name`)
2. **Reads cluster configuration** to extract the cluster domain from the YAML file
3. **Ensures k3s is installed and running** on the target host
4. **Configures the k3s kube-apiserver** with OIDC authentication parameters via `/etc/rancher/k3s/config.yaml` (`kube-apiserver-arg`)
5. **Restarts the k3s service** to apply the OIDC configuration changes
6. **Waits for k3s to become operational** after restart with retry logic

This role is designed to be used together with the `k3s` installation role as a k3s-based counterpart to `oidc_k0s` and `oidc_microk8s`.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **k3s must be installed**: This role requires k3s to be installed and running (typically via the `k3s` role)
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- **env.json file**: Must exist in the config folder and contain the `cluster_name` variable
- **Cluster configuration file**: Must exist with a `domain` field (located at `{{ config_folder }}/{{ cluster_name }}.yaml`)
- **OIDC provider**: The OIDC provider (Keycloak) should be deployed and accessible at `https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`
- **CA certificate**: The CA certificate file must exist at the specified path for OIDC verification

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `oidc_username_claim` | `email` | string | JWT claim to use as username |
| `oidc_groups_claim` | `groups` | string | JWT claim to use for groups |
| `oidc_client_id` | `maia` | string | OIDC client ID |
| `oidc_realm` | `maia` | string | OIDC realm name |
| `oidc_subdomain` | `iam` | string | Subdomain prefix for OIDC issuer URL |
| `oidc_ca_file` | `/var/lib/rancher/k3s/server/tls/server-ca.crt` | string | Path to CA certificate file |
| `k3s_config_dir` | `/etc/rancher/k3s` | string | Path to k3s config directory |
| `oidc_k3s_retries` | `10` | integer | Number of retries when waiting for k3s |
| `oidc_k3s_retry_delay` | `15` | integer | Delay in seconds between retries |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `cluster_name` variable
  - Cluster YAML file: Located at `{{ config_folder }}/{{ cluster_name }}.yaml`
- **Example**: `config_folder: /opt/maia/config`

**Note**:
- The `env.json` file must exist and contain the `cluster_name` variable. The role loads this file automatically.
- The cluster configuration file must exist and contain a `domain` field. The role will fail if the file is missing or doesn't contain the domain.

## Optional Values

### `oidc_username_claim`
- **Type**: `string`
- **Default**: `email`
- **Description**: JWT claim to use as the username for Kubernetes authentication. Common values: `email`, `sub`, `preferred_username`.

### `oidc_groups_claim`
- **Type**: `string`
- **Default**: `groups`
- **Description**: JWT claim to use for user groups. This is used for RBAC group-based authorization in Kubernetes.

### `oidc_client_id`
- **Type**: `string`
- **Default**: `maia`
- **Description**: OIDC client ID registered in the OIDC provider (Keycloak). This must match the client ID configured in Keycloak.

### `oidc_realm`
- **Type**: `string`
- **Default**: `maia`
- **Description**: OIDC realm name used in the issuer URL: `https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`.

### `oidc_subdomain`
- **Type**: `string`
- **Default**: `iam`
- **Description**: Subdomain prefix for the OIDC issuer URL.

### `oidc_ca_file`
- **Type**: `string`
- **Default**: `/var/lib/rancher/k3s/server/tls/server-ca.crt`
- **Description**: Path to the CA certificate file used for OIDC verification. Can be overridden via cluster config `externalCA.cert`.

### `k3s_config_dir`
- **Type**: `string`
- **Default**: `/etc/rancher/k3s`
- **Description**: Path to the k3s config directory. The config file is `{{ k3s_config_dir }}/config.yaml`.

### `oidc_k3s_retries`
- **Type**: `integer`
- **Default**: `10`
- **Description**: Number of retries when waiting for k3s to become operational after restart.

### `oidc_k3s_retry_delay`
- **Type**: `integer`
- **Default**: `15`
- **Description**: Delay in seconds between retries when waiting for k3s to become operational.

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Enable OIDC authentication for k3s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k3s
    - role: maia.installation.oidc_k3s
      vars:
        config_folder: /opt/maia/config
```

### Custom OIDC Configuration

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k3s
    - role: maia.installation.oidc_k3s
      vars:
        config_folder: /opt/maia/config
        oidc_client_id: kubernetes
        oidc_realm: kubernetes
        oidc_subdomain: keycloak
        oidc_username_claim: preferred_username
```

### Custom Retry Settings

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k3s
    - role: maia.installation.oidc_k3s
      vars:
        config_folder: /opt/maia/config
        oidc_k3s_retries: 20
        oidc_k3s_retry_delay: 30
```

## Tasks

The role performs the following tasks:

1. **Load environment variables**: Loads `env.json` from config folder to get `cluster_name` and other variables.
2. **Read cluster config**: Reads the cluster configuration YAML file to extract the domain (and optional `externalCA.cert`).
3. **Share cluster domain**: Shares the cluster domain fact with target hosts.
4. **Ensure k3s is installed**: Verifies k3s responds to `k3s kubectl get nodes`.
5. **Read or create k3s config**: Ensures `/etc/rancher/k3s/config.yaml` exists; reads existing or starts with empty config.
6. **Merge OIDC kube-apiserver-arg**: Builds `kube-apiserver-arg` list (keeps existing non-OIDC args, removes old oidc-* args, adds current OIDC args).
7. **Write config.yaml**: Writes the updated k3s config with OIDC parameters.
8. **Restart k3s service**: Restarts the `k3s` service to apply configuration.
9. **Wait for k3s**: Waits for k3s to become operational with retry logic.
10. **Fail if not operational**: Terminates playbook if k3s doesn't become operational.

## OIDC Configuration Details

### Issuer URL

The OIDC issuer URL is constructed as:

```text
https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}
```

For example, with defaults:
- `oidc_subdomain`: `iam`
- `cluster_domain`: `example.com` (from cluster config)
- `oidc_realm`: `maia`

Results in: `https://iam.example.com/realms/maia`

### API Server Arguments

The role adds the following to k3s `kube-apiserver-arg` in `config.yaml`:
- `oidc-issuer-url={{ oidc_issuer_url }}`
- `oidc-client-id={{ oidc_client_id }}`
- `oidc-username-claim={{ oidc_username_claim }}`
- `oidc-groups-claim={{ oidc_groups_claim }}`
- `oidc-ca-file={{ oidc_ca_file }}`

## Testing

### Test Playbook

The role can be tested with a dedicated playbook:

```yaml
---
- hosts: localhost
  remote_user: root
  roles:
    - k3s
    - oidc_k3s
```

### Running Tests

1. **Prepare test inventory**: Ensure an inventory with your test hosts exists.
2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with `cluster_name` variable.
   - Cluster configuration file at `{{ config_folder }}/{{ cluster_name }}.yaml` including:
     ```yaml
     domain: example.com
     ```
3. **Run the test playbook** with appropriate `config_folder`.

## Notes

- k3s must already be installed and running before enabling OIDC. Install k3s using the `k3s` role first.
- After enabling OIDC, the role restarts the k3s service. The role waits for k3s to become operational.
- k3s loads configuration from `/etc/rancher/k3s/config.yaml`. The role merges OIDC args with any existing `kube-apiserver-arg` entries (existing oidc-* args are replaced by the role’s values).
