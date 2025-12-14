# OIDC MicroK8s Role

This Ansible role enables OIDC (OpenID Connect) authentication for MicroK8s. It configures the Kubernetes API server to authenticate users using JWT tokens from an OIDC provider (typically Keycloak).

## Description

The `oidc_microk8s` role automates the configuration of OIDC authentication for MicroK8s clusters. It performs the following tasks:

1. **Loads environment variables** from `env.json` in the config folder (including `cluster_name`)
2. **Reads cluster configuration** to extract the cluster domain from the YAML file
3. **Ensures MicroK8s is installed** on the target host
4. **Configures kube-apiserver** with OIDC authentication parameters
5. **Restarts MicroK8s** to apply the OIDC configuration changes
6. **Waits for MicroK8s to become operational** after restart with retry logic

This role is designed to be used as part of the MAIA installation process, particularly in the `install_microk8s.yaml` playbook after the `microk8s` role, but can also be used standalone for OIDC configuration.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Tested on**: Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **MicroK8s must be installed**: This role requires MicroK8s to be installed and running (typically via the `microk8s` role)
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
| `cluster_config` | `{{ config_folder }}/{{ cluster_name }}.yaml` | string | Path to cluster configuration file |
| `oidc_username_claim` | `email` | string | JWT claim to use as username |
| `oidc_groups_claim` | `groups` | string | JWT claim to use for groups |
| `oidc_client_id` | `maia` | string | OIDC client ID |
| `oidc_realm` | `maia` | string | OIDC realm name |
| `oidc_subdomain` | `iam` | string | Subdomain prefix for OIDC issuer URL |
| `oidc_ca_file` | `/var/snap/microk8s/current/certs/ca.crt` | string | Path to CA certificate file |
| `microk8s_apiserver_args_file` | `/var/snap/microk8s/current/args/kube-apiserver` | string | Path to kube-apiserver arguments file |
| `oidc_microk8s_retries` | `10` | integer | Number of retries when waiting for MicroK8s |
| `oidc_microk8s_retry_delay` | `15` | integer | Delay in seconds between retries |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `cluster_name` variable
  - Cluster YAML file: Located at `{{ config_folder }}/{{ cluster_name }}.yaml` (or specified via `cluster_config`)
- **Example**: `config_folder: /opt/maia/config`

**Note**: 
- The `env.json` file must exist and contain the `cluster_name` variable. The role loads this file automatically.
- The cluster configuration file must exist and contain a `domain` field. The role will fail if the file is missing or doesn't contain the domain.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `cluster_config`
- **Type**: `string`
- **Default**: `{{ config_folder }}/{{ cluster_name }}.yaml`
- **Description**: Full path to the cluster configuration YAML file. If not specified, defaults to `{{ config_folder }}/{{ cluster_name }}.yaml`. The file must contain a `domain` field.
- **Example**: `cluster_config: /opt/maia/config/my-cluster.yaml`

### `oidc_username_claim`
- **Type**: `string`
- **Default**: `email`
- **Description**: JWT claim to use as the username for Kubernetes authentication. Common values: `email`, `sub`, `preferred_username`.
- **Example**: `oidc_username_claim: preferred_username`

### `oidc_groups_claim`
- **Type**: `string`
- **Default**: `groups`
- **Description**: JWT claim to use for user groups. This is used for RBAC group-based authorization in Kubernetes.
- **Example**: `oidc_groups_claim: groups`

### `oidc_client_id`
- **Type**: `string`
- **Default**: `maia`
- **Description**: OIDC client ID registered in the OIDC provider (Keycloak). This must match the client ID configured in Keycloak.
- **Example**: `oidc_client_id: kubernetes`

### `oidc_realm`
- **Type**: `string`
- **Default**: `maia`
- **Description**: OIDC realm name used in the issuer URL. The issuer URL will be: `https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`.
- **Example**: `oidc_realm: kubernetes`

### `oidc_subdomain`
- **Type**: `string`
- **Default**: `iam`
- **Description**: Subdomain prefix for the OIDC issuer URL. The issuer URL will be: `https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`.
- **Example**: `oidc_subdomain: keycloak`

### `oidc_ca_file`
- **Type**: `string`
- **Default**: `/var/snap/microk8s/current/certs/ca.crt`
- **Description**: Path to the CA certificate file used for OIDC verification. This should be the MicroK8s CA certificate or a custom CA certificate that signed the OIDC provider's certificate.
- **Example**: `oidc_ca_file: /var/snap/microk8s/current/certs/ca.crt`

### `microk8s_apiserver_args_file`
- **Type**: `string`
- **Default**: `/var/snap/microk8s/current/args/kube-apiserver`
- **Description**: Path to the kube-apiserver arguments file where OIDC configuration will be written.
- **Example**: `microk8s_apiserver_args_file: /var/snap/microk8s/current/args/kube-apiserver`

### `oidc_microk8s_retries`
- **Type**: `integer`
- **Default**: `10`
- **Description**: Number of retries when waiting for MicroK8s to become operational after restart. The role will retry this many times before failing.
- **Example**: `oidc_microk8s_retries: 15`

### `oidc_microk8s_retry_delay`
- **Type**: `integer`
- **Default**: `15`
- **Description**: Delay in seconds between retries when waiting for MicroK8s to become operational after restart.
- **Example**: `oidc_microk8s_retry_delay: 20`

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Enable OIDC authentication for MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.oidc_microk8s
      vars:
        config_folder: /opt/maia/config
```

**Important**: 
- Ensure `env.json` exists in the config folder and contains the `cluster_name` variable
- Ensure the cluster configuration file exists at `{{ config_folder }}/{{ cluster_name }}.yaml` and contains a `domain` field:

```yaml
domain: example.com
```

### Custom OIDC Configuration

Specify custom OIDC parameters:

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.oidc_microk8s
      vars:
        config_folder: /opt/maia/config
        oidc_client_id: kubernetes
        oidc_realm: kubernetes
        oidc_subdomain: keycloak
        oidc_username_claim: preferred_username
```

### Custom Cluster Config Path

Specify a custom path to the cluster configuration file:

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.oidc_microk8s
      vars:
        config_folder: /opt/maia/config
        cluster_config: /opt/maia/config/custom-cluster.yaml
```

### Custom Retry Settings

Adjust retry behavior for slower systems:

```yaml
- name: Enable OIDC authentication
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.oidc_microk8s
      vars:
        config_folder: /opt/maia/config
        oidc_microk8s_retries: 20
        oidc_microk8s_retry_delay: 30
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e config_folder=/opt/maia/config \
  -e oidc_client_id=kubernetes
```

### In install_microk8s.yaml

This role is used as part of the MAIA installation process:

```yaml
- name: Prepare hosts for Kubernetes installation
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
    - role: maia.installation.oidc_microk8s
```

### Standalone Playbook Example

Create a dedicated playbook for OIDC configuration:

```yaml
---
- name: Enable OIDC authentication for MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.oidc_microk8s
      vars:
        config_folder: /opt/maia/config
        oidc_username_claim: email
        oidc_groups_claim: groups
        oidc_client_id: maia
        oidc_realm: maia
        oidc_subdomain: iam
        oidc_ca_file: /var/snap/microk8s/current/certs/ca.crt
        oidc_microk8s_retries: 10
        oidc_microk8s_retry_delay: 15
```

## Tasks

The role performs the following tasks:

1. **Load environment variables**: Loads `env.json` from config folder to get `cluster_name` and other variables
2. **Read cluster config**: Reads the cluster configuration YAML file to extract the domain
3. **Extract cluster domain**: Extracts the `domain` field from the cluster configuration
4. **Share cluster domain**: Shares the cluster domain fact with target hosts
5. **Ensure MicroK8s is installed**: Verifies MicroK8s is installed (installs if missing)
6. **Enable OIDC authentication**: Configures kube-apiserver with OIDC parameters:
   - `--oidc-username-claim`: JWT claim for username
   - `--oidc-groups-claim`: JWT claim for groups
   - `--oidc-issuer-url`: OIDC issuer URL
   - `--oidc-client-id`: OIDC client ID
   - `--oidc-ca-file`: CA certificate file path
7. **Restart MicroK8s**: Restarts MicroK8s to apply OIDC configuration
8. **Wait for MicroK8s**: Waits for MicroK8s to become operational with retry logic
9. **Fail if not operational**: Terminates playbook if MicroK8s doesn't become operational

## OIDC Configuration Details

### Issuer URL

The OIDC issuer URL is constructed as:
```
https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}
```

For example, with defaults:
- `oidc_subdomain`: `iam`
- `cluster_domain`: `example.com` (from cluster config)
- `oidc_realm`: `maia`

Results in: `https://iam.example.com/realms/maia`

### API Server Arguments

The role adds the following arguments to the kube-apiserver:
- `--oidc-username-claim={{ oidc_username_claim }}`
- `--oidc-groups-claim={{ oidc_groups_claim }}`
- `--oidc-issuer-url=https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}`
- `--oidc-client-id={{ oidc_client_id }}`
- `--oidc-ca-file={{ oidc_ca_file }}`

### Cluster Restart

After configuring OIDC, MicroK8s is restarted to apply the changes. The role waits for MicroK8s to become operational with configurable retry logic.

## Testing

### Test Playbook

The role can be tested with a dedicated playbook:

```yaml
---
- hosts: control-plane
  remote_user: root
  become: true
  roles:
    - oidc_microk8s
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts:
   ```ini
   [control-plane]
   maia-dev-node-0 ansible_user=root ansible_become=true
   ```

2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with `cluster_name` variable:
     ```json
     {
       "cluster_name": "my-cluster"
     }
     ```
   - Cluster configuration file at `{{ config_folder }}/{{ cluster_name }}.yaml`:
     ```yaml
     domain: example.com
     ```

3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/opt/maia/config
   ```

4. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/opt/maia/config \
     -e oidc_client_id=kubernetes \
     -e oidc_realm=kubernetes
   ```

### Manual Verification

After running the role, verify the OIDC configuration:

1. **Check MicroK8s is running**:
   ```bash
   microk8s status --wait-ready
   ```

2. **Verify OIDC configuration in kube-apiserver**:
   ```bash
   cat /var/snap/microk8s/current/args/kube-apiserver | grep oidc
   ```
   Should show the OIDC configuration lines:
   - `--oidc-username-claim=email`
   - `--oidc-groups-claim=groups`
   - `--oidc-issuer-url=https://iam.<cluster_domain>/realms/maia`
   - `--oidc-client-id=maia`
   - `--oidc-ca-file=/var/snap/microk8s/current/certs/ca.crt`

3. **Check MicroK8s API server is responding**:
   ```bash
   microk8s.kubectl get nodes
   ```

4. **Verify cluster domain was extracted correctly**:
   ```bash
   cat {{ config_folder }}/{{ cluster_name }}.yaml | grep domain
   ```

5. **Test OIDC authentication** (requires valid JWT token):
   ```bash
   kubectl --token=<jwt_token> get nodes
   ```

6. **Check MicroK8s logs for OIDC-related errors**:
   ```bash
   journalctl -u snap.microk8s.daemon-apiserver | tail -50
   ```

7. **Verify CA certificate exists**:
   ```bash
   ls -l {{ oidc_ca_file }}
   ```

8. **Check OIDC issuer URL is accessible**:
   ```bash
   curl -k https://{{ oidc_subdomain }}.{{ cluster_domain }}/realms/{{ oidc_realm }}/.well-known/openid-configuration
   ```

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom OIDC parameters**: Test with different client IDs, realms, and subdomains
- **Custom cluster config path**: Test with different cluster configuration file locations
- **Custom retry settings**: Test with different retry counts and delays
- **Missing cluster config**: Test error handling when cluster config is missing
- **Missing domain field**: Test error handling when domain field is missing

## Notes

- **MicroK8s prerequisite**: MicroK8s must be installed and running before enabling OIDC. Install MicroK8s using the `microk8s` role first.
- **Cluster restart**: After enabling OIDC, MicroK8s will restart. The role waits for it to become operational, but this may take a few minutes.
- **OIDC provider availability**: The OIDC provider (Keycloak) should be deployed and accessible before enabling OIDC. The role will configure OIDC even if the provider is not yet available, but authentication will fail until the provider is accessible.
- **env.json file**: The `env.json` file must exist in the config folder and contain the `cluster_name` variable. The role loads this file automatically.
- **Cluster configuration file**: The cluster configuration file must exist and contain a `domain` field. The role will fail if the file is missing or doesn't contain the domain.
- **CA certificate**: The CA certificate file must exist at the specified path. By default, this is the MicroK8s CA certificate.
- **JWT token format**: Users must obtain JWT tokens from the OIDC provider to authenticate with Kubernetes. The token must contain the claims specified in `oidc_username_claim` and `oidc_groups_claim`.
- **RBAC configuration**: After enabling OIDC, you must configure Kubernetes RBAC to grant permissions to users and groups based on the OIDC claims.
- **Sudo privileges**: The role requires elevated privileges to modify MicroK8s configuration and restart services.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
