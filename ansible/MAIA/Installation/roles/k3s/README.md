# k3s Role

This Ansible role installs and configures **k3s**, a lightweight Kubernetes distribution, on Ubuntu systems. It sets up a single-node k3s server, retrieves and configures the kubeconfig file with local certificate paths, configures firewall rules, and enables SSH port forwarding for API access.

## Description

The `k3s` role automates the installation and configuration of k3s on Linux hosts. It performs the following tasks:

1. **Loads configuration variables** from `env.json` in the config folder
2. **Installs required packages** (e.g. `curl`)
3. **Installs k3s** using the official installer script (server with TLS SAN for cluster domain)
4. **Starts and enables the k3s service**
5. **Opens firewall ports** for the Kubernetes API and ingress traffic
6. **Fetches CA and client certificates** to the local config folder
7. **Writes kubeconfig** to `DEPLOY_KUBECONFIG` with localhost server and local cert paths
8. **Sets up SSH port forwarding** for API access from localhost

This role is designed to be used similarly to the `k0s` and `microk8s` roles in the MAIA installation, but installs k3s instead.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- **Internet access**: Required to download the k3s installer and binaries
- **SSH access**: Required to target hosts and for port forwarding
- **Config folder**: Must contain `env.json` (with `DEPLOY_KUBECONFIG` variable) and cluster YAML (with `domain` for TLS SAN)
- **UFW firewall**: The role configures UFW firewall rules (if UFW is enabled)

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `k3s_version` | `latest` | string | k3s version selector used by installer script |
| `k3s_firewall_ports` | `[{"port": 6443, "proto": "tcp"}, {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}]` | list | Firewall ports to open |
| `k3s_enable_port_forwarding` | `true` | boolean | Enable SSH port forwarding for API access |
| `k3s_port_forward_port` | `6443` | integer | Local port for SSH port forwarding |
| `k3s_data_dir` | `/var/lib/rancher/k3s` | string | k3s data directory on target host |
| `k3s_config_dir` | `/etc/rancher/k3s` | string | k3s config directory on target host |
| `rancher_local_path_provisioner_version` | `v0.0.34` | string | Rancher local path provisioner version to install |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `DEPLOY_KUBECONFIG` variable specifying where to save the kubeconfig file
  - `{{ cluster_name }}.yaml`: Cluster config YAML with `domain` key (used for TLS SAN)
- **Example**: `config_folder: /opt/maia/config`

**Note**: The role will fail if `config_folder` is not provided or if `env.json` does not exist.

## Optional Values

### `k3s_version`
- **Type**: `string`
- **Default**: `latest`
- **Description**: k3s version to install. When set to `latest`, the installer fetches the latest stable release. Example pin: `v1.28.5+k3s1`.

### `k3s_firewall_ports`
- **Type**: `list` (of dictionaries)
- **Default**: `[{"port": 6443, "proto": "tcp"}, {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}]`
- **Description**: List of firewall ports to open for k3s.

### `k3s_enable_port_forwarding`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether SSH port forwarding should be set up for API access.

### `k3s_port_forward_port`
- **Type**: `integer`
- **Default**: `6443`
- **Description**: Local port number for SSH port forwarding to the k3s API server.

### `k3s_data_dir`
- **Type**: `string`
- **Default**: `/var/lib/rancher/k3s`
- **Description**: k3s data directory on the target host. Used to locate CA and client certs.

### `k3s_config_dir`
- **Type**: `string`
- **Default**: `/etc/rancher/k3s`
- **Description**: k3s config directory on the target host (kubeconfig location).

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` (and `cluster_name` if not default) variable:

```yaml
- name: Install k3s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k3s
      vars:
        config_folder: /opt/maia/config
        cluster_name: my-cluster   # optional; cluster config file is {{ cluster_name }}.yaml
```

### Custom Firewall Ports

```yaml
- name: Install k3s with custom ports
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k3s
      vars:
        config_folder: /opt/maia/config
        k3s_firewall_ports:
          - port: 6443
            proto: tcp
          - port: 30080
            proto: tcp
```

### Without Port Forwarding

```yaml
- name: Install k3s without port forwarding
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k3s
      vars:
        config_folder: /opt/maia/config
        k3s_enable_port_forwarding: false
```

## Tasks

The role performs the following high-level tasks:

1. **Load configuration variables** from `env.json`
2. **Read cluster config** to get `domain` for TLS SAN
3. **Install required packages** (`curl`, `sudo`)
4. **Install k3s server** using the official installer with `--tls-san={{ cluster_domain }}`
5. **Ensure k3s service** is started and enabled
6. **Open firewall ports** configured in `k3s_firewall_ports`
7. **Wait for k3s API** to become available
8. **Fetch CA and client certs** to the config folder
9. **Write kubeconfig** to `DEPLOY_KUBECONFIG` with localhost server and local cert paths
10. **Setup SSH port forwarding** (conditional, if enabled)

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - k3s
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts.
2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with `DEPLOY_KUBECONFIG` variable
   - `{{ cluster_name }}.yaml` with a `domain` key
3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/path/to/config -e cluster_name=my-cluster
   ```

## Notes

- This role is intended as a k3s-based alternative to the `k0s` and `microk8s` roles.
- It focuses on single-node server setups; multi-node clustering can be added later if needed.
- The kubeconfig written uses certificate and key file paths under `config_folder` so that kubectl run from the control machine can authenticate via the fetched certs and the SSH port forward.
