# k0s Role

This Ansible role installs and configures **k0s**, a lightweight Kubernetes distribution, on Ubuntu systems. It sets up a single-node k0s controller, retrieves and configures the kubeconfig file, configures firewall rules, and enables SSH port forwarding for API access.

## Description

The `k0s` role automates the installation and configuration of k0s on Linux hosts. It performs the following tasks:

1. **Loads configuration variables** from `env.json` in the config folder
2. **Installs required packages** (e.g. `curl`)
3. **Installs k0s** using the official installer script
4. **Installs and starts a single-node k0s controller**
5. **Opens firewall ports** for the Kubernetes API and ingress traffic
6. **Retrieves and saves kubeconfig** to the local deployment folder
7. **Configures kubeconfig** to use localhost for port forwarding
8. **Copies root CA certificate** to the config folder
9. **Sets up SSH port forwarding** for API access from localhost

This role is designed to be used similarly to the `microk8s` role in the MAIA installation, but installs k0s instead.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- **Internet access**: Required to download the k0s installer and binaries
- **SSH access**: Required to target hosts and for port forwarding
- **Config folder**: Must contain `env.json` (with `DEPLOY_KUBECONFIG` variable)
- **UFW firewall**: The role configures UFW firewall rules (if UFW is enabled)

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `k0s_version` | `latest` | string | k0s version selector used by installer script |
| `k0s_firewall_ports` | `[{"port": 6443, "proto": "tcp"}, {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}]` | list | Firewall ports to open |
| `k0s_enable_port_forwarding` | `true` | boolean | Enable SSH port forwarding for API access |
| `k0s_port_forward_port` | `6443` | integer | Local port for SSH port forwarding |
| `k0s_data_dir` | `/var/lib/k0s` | string | k0s data directory on target host |
| `rancher_local_path_provisioner_version` | `v0.0.34` | string | Rancher local path provisioner version to install |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `DEPLOY_KUBECONFIG` variable specifying where to save the kubeconfig file
- **Example**: `config_folder: /opt/maia/config`

**Note**: The role will fail if `config_folder` is not provided or if `env.json` does not exist.

## Optional Values

### `k0s_version`
- **Type**: `string`
- **Default**: `latest`
- **Description**: k0s version to install. When set to `latest`, the installer fetches the latest stable release.

### `rancher_local_path_provisioner_version`
- **Type**: `string`
- **Default**: `v0.0.34`
- **Description**: Rancher local path provisioner version to install.

### `k0s_firewall_ports`
- **Type**: `list` (of dictionaries)
- **Default**: `[{"port": 6443, "proto": "tcp"}, {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}]`
- **Description**: List of firewall ports to open for k0s.

### `k0s_enable_port_forwarding`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether SSH port forwarding should be set up for API access.

### `k0s_port_forward_port`
- **Type**: `integer`
- **Default**: `6443`
- **Description**: Local port number for SSH port forwarding to the k0s API server.

### `k0s_data_dir`
- **Type**: `string`
- **Default**: `/var/lib/k0s`
- **Description**: k0s data directory on the target host. Used to locate `ca.crt`.

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Install k0s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k0s
      vars:
        config_folder: /opt/maia/config
```

### Custom Firewall Ports

```yaml
- name: Install k0s with custom ports
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k0s
      vars:
        config_folder: /opt/maia/config
        k0s_firewall_ports:
          - port: 6443
            proto: tcp
          - port: 30080
            proto: tcp
```

### Without Port Forwarding

```yaml
- name: Install k0s without port forwarding
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.k0s
      vars:
        config_folder: /opt/maia/config
        k0s_enable_port_forwarding: false
```

## Tasks

The role performs the following high-level tasks:

1. **Load configuration variables** from `env.json`
2. **Install required packages** (`curl`, `sudo`)
3. **Install k0s binary** using the official installer
4. **Install and start k0s controller service** in single-node mode
5. **Install local-path-provisioner** using `kubectl`
6. **Open firewall ports** configured in `k0s_firewall_ports`
7. **Retrieve kubeconfig** using `k0s kubeconfig admin`
8. **Save kubeconfig** to `DEPLOY_KUBECONFIG` on the local machine
9. **Configure kubeconfig** to use `https://127.0.0.1:{{ k0s_port_forward_port }}`
10. **Copy CA certificate** from `{{ k0s_data_dir }}/pki/ca.crt` to `{{ config_folder }}/ca.crt`
11. **Setup SSH port forwarding** (conditional, if enabled)

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - k0s
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts.
2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with `DEPLOY_KUBECONFIG` variable
3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/path/to/config
   ```

## Notes

- This role is intended as a k0s-based alternative to the existing `microk8s` role.
- It focuses on single-node controller setups; multi-node clustering can be added later if needed.

