# OIDC k0s Role

This Ansible role enables OIDC (OpenID Connect) authentication for **k0s**. It configures the Kubernetes API server managed by k0s to authenticate users using JWT tokens from an OIDC provider (typically Keycloak).

## Description

The `oidc_k0s` role automates the configuration of OIDC authentication for k0s clusters. It performs the following tasks:

1. **Loads environment variables** from `env.json` in the config folder (including `cluster_name`)
2. **Reads cluster configuration** to extract the cluster domain from the YAML file
3. **Ensures k0s is installed and running** on the target host
4. **Configures the k0s-managed kube-apiserver** with OIDC authentication parameters
5. **Restarts the k0s controller service** to apply the OIDC configuration changes
6. **Waits for k0s to become operational** after restart with retry logic

This role is designed to be used together with the `k0s` installation role as a k0s-based counterpart to `oidc_microk8s`.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **k0s must be installed**: This role requires k0s to be installed and running (typically via the `k0s` role)
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
| `oidc_ca_file` | `/var/lib/k0s/pki/ca.crt` | string | Path to CA certificate file |
| `k0s_apiserver_args_file` | `/var/lib/k0s/pki/admin.conf` | string | Path to k0s kube-apiserver configuration/arguments file (override as needed) |
| `oidc_k0s_retries` | `10` | integer | Number of retries when waiting for k0s |
| `oidc_k0s_retry_delay` | `15` | integer | Delay in seconds between retries |

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
- **Default**: `/var/lib/k0s/pki/ca.crt`
- **Description**: Path to the CA certificate file used for OIDC verification.

### `k0s_apiserver_args_file`
- **Type**: `string`
- **Default**: `/var/lib/k0s/pki/admin.conf`
- **Description**: Path to the k0s kube-apiserver configuration or arguments file. Override this to point to the appropriate configuration file in your k0s setup.

### `oidc_k0s_retries`
- **Type**: `integer`
- **Default**: `10`
- **Description**: Number of retries when waiting for k0s to become operational after restart.

### `oidc_k0s_retry_delay`
- **Type**: `integer`
- **Default**: `15`
- **Description**: Delay in seconds between retries when waiting for k0s to become operational.

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Enable OIDC authentication for k0s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k0s
    - role: maia.installation.oidc_k0s
      vars:
        config_folder: /opt/maia/config
```

### Custom OIDC Configuration

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k0s
    - role: maia.installation.oidc_k0s
      vars:
        config_folder: /opt/maia/config
        oidc_client_id: kubernetes
        oidc_realm: kubernetes
        oidc_subdomain: keycloak
        oidc_username_claim: preferred_username
```

### Custom Cluster Config Path

Override `cluster_name` in `env.json` or adjust the path you use for the cluster config file if you adapt the role.

### Custom Retry Settings

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k0s
    - role: maia.installation.oidc_k0s
      vars:
        config_folder: /opt/maia/config
        oidc_k0s_retries: 20
        oidc_k0s_retry_delay: 30
```

## Tasks

The role performs the following tasks:

1. **Load environment variables**: Loads `env.json` from config folder to get `cluster_name` and other variables.
2. **Read cluster config**: Reads the cluster configuration YAML file to extract the domain.
3. **Extract cluster domain**: Extracts the `domain` field from the cluster configuration.
4. **Share cluster domain**: Shares the cluster domain fact with target hosts.
5. **Ensure k0s is installed**: Verifies k0s is installed and responds to `k0s status`.
6. **Enable OIDC authentication**: Writes OIDC parameters to the k0s API server configuration file:
   - `--oidc-username-claim={{ oidc_username_claim }}`
   - `--oidc-groups-claim={{ oidc_groups_claim }}`
   - `--oidc-issuer-url=https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`
   - `--oidc-client-id={{ oidc_client_id }}`
   - `--oidc-ca-file={{ oidc_ca_file }}`
7. **Restart k0s controller service**: Restarts the `k0scontroller` service to apply configuration.
8. **Wait for k0s**: Waits for k0s to become operational with retry logic.
9. **Fail if not operational**: Terminates playbook if k0s doesn't become operational.

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

The role adds the following arguments to the k0s API server configuration file:
- `--oidc-username-claim={{ oidc_username_claim }}`
- `--oidc-groups-claim={{ oidc_groups_claim }}`
- `--oidc-issuer-url=https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`
- `--oidc-client-id={{ oidc_client_id }}`
- `--oidc-ca-file={{ oidc_ca_file }}`

## Testing

### Test Playbook

The role can be tested with a dedicated playbook:

```yaml
---
- hosts: control-plane
  remote_user: root
  become: true
  roles:
    - k0s
    - oidc_k0s
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

- k0s must already be installed and running before enabling OIDC. Install k0s using the `k0s` role first.
- After enabling OIDC, k0s will restart the controller service. The role waits for it to become operational.
- The exact path for k0s API server configuration can vary; adjust `k0s_apiserver_args_file` as appropriate for your deployment.

