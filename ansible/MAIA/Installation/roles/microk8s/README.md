# MicroK8s Role

This Ansible role installs and configures MicroK8s, a lightweight Kubernetes distribution, on Ubuntu systems. It sets up MicroK8s with necessary addons, configures the kubeconfig file, sets up firewall rules, and enables SSH port forwarding for API access.

## Description

The `microk8s` role automates the installation and configuration of MicroK8s on Linux hosts. It performs the following tasks:

1. **Loads configuration variables** from `env.json` in the config folder
2. **Creates MicroK8s config directory** structure
3. **Copies MicroK8s configuration file** to the target host
4. **Installs snapd** package manager if not present
5. **Installs MicroK8s** via snap package manager
6. **Adds user to microk8s group** to allow running microk8s commands without sudo
7. **Enables MicroK8s addons** (hostpath-storage, rbac, and optionally others)
8. **Starts MicroK8s** service
9. **Retrieves and saves kubeconfig** to the local deployment folder
10. **Configures kubeconfig** to use localhost for port forwarding
11. **Opens firewall ports** (16443, 80, 443) for MicroK8s services
12. **Labels nodes** with appropriate roles (for control-plane hosts)
13. **Copies root CA certificate** to the config folder
14. **Sets up SSH port forwarding** for API access from localhost

This role is designed to be used as part of the MAIA installation process, particularly in the `install_microk8s.yaml` playbook, but can also be used standalone for MicroK8s installation.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Tested on**: Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- **Internet access**: Required to download snap packages from the snap store
- **SSH access**: Required to target hosts and for port forwarding
- **Config folder**: Must contain `env.json` (with `DEPLOY_KUBECONFIG` variable) and `microk8s-config.yaml`
- **UFW firewall**: The role configures UFW firewall rules (if UFW is enabled)

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `microk8s_version` | `1.31/stable` | string | MicroK8s version/channel to install |
| `ansible_user` | `root` | string | User to add to the microk8s group |
| `microk8s_addons` | `[hostpath-storage, rbac]` | list | List of MicroK8s addons to enable |
| `microk8s_firewall_ports` | `[{"port": 16443, "proto": "tcp"}, {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}]` | list | Firewall ports to open |
| `microk8s_config_file` | `microk8s-config.yaml` | string | Name of MicroK8s config file in config_folder |
| `microk8s_config_dir` | `/var/snap/microk8s/common` | string | MicroK8s config directory on target host |
| `microk8s_enable_port_forwarding` | `true` | boolean | Enable SSH port forwarding for API access |
| `microk8s_port_forward_port` | `16443` | integer | Local port for SSH port forwarding |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing:
  - `env.json`: Must contain `DEPLOY_KUBECONFIG` variable specifying where to save the kubeconfig file
  - `microk8s-config.yaml`: MicroK8s configuration file to copy to the target host
- **Example**: `config_folder: /opt/maia/config`

**Note**: The role will fail if `config_folder` is not provided or if the required files do not exist.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `microk8s_version`
- **Type**: `string`
- **Default**: `1.31/stable`
- **Description**: MicroK8s version/channel to install via snap. Format is `version/channel` where:
  - `version`: Kubernetes version (e.g., `1.31`, `1.30`, `latest`)
  - `channel`: Release channel (`stable`, `candidate`, `beta`, `edge`)
- **Example**: `microk8s_version: 1.30/stable`

### `ansible_user`
- **Type**: `string`
- **Default**: `root`
- **Description**: User to add to the `microk8s` group. This user will be able to run `microk8s` commands without sudo.
- **Example**: `ansible_user: maia-admin`

### `microk8s_addons`
- **Type**: `list` (of strings)
- **Default**: `[hostpath-storage, rbac]`
- **Description**: List of MicroK8s addons to enable. Common addons include:
  - `hostpath-storage`: Local persistent storage provisioner
  - `rbac`: Role-based access control
  - `dns`: CoreDNS for service discovery
  - `ingress`: Ingress controller
  - `storage`: Storage class
  - `metrics-server`: Metrics collection
- **Example**: 
  ```yaml
  microk8s_addons:
    - hostpath-storage
    - rbac
    - dns
    - ingress
  ```

### `microk8s_firewall_ports`
- **Type**: `list` (of dictionaries)
- **Default**: `[{"port": 16443, "proto": "tcp"}, {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}]`
- **Description**: List of firewall ports to open for MicroK8s. Each entry is a dictionary with:
  - `port` (required): Port number
  - `proto` (required): Protocol (`tcp` or `udp`)
- **Example**: 
  ```yaml
  microk8s_firewall_ports:
    - port: 16443
      proto: tcp
    - port: 80
      proto: tcp
    - port: 443
      proto: tcp
  ```

### `microk8s_config_file`
- **Type**: `string`
- **Default**: `microk8s-config.yaml`
- **Description**: Name of the MicroK8s configuration file in the config folder. This file will be copied to `{{ microk8s_config_dir }}/.microk8s.yaml` on the target host.
- **Example**: `microk8s_config_file: my-microk8s-config.yaml`

### `microk8s_config_dir`
- **Type**: `string`
- **Default**: `/var/snap/microk8s/common`
- **Description**: Directory on the target host where MicroK8s configuration is stored.
- **Example**: `microk8s_config_dir: /var/snap/microk8s/common`

### `microk8s_enable_port_forwarding`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether SSH port forwarding should be set up for API access. When enabled, creates an SSH tunnel from localhost to the MicroK8s API server.
- **Example**: `microk8s_enable_port_forwarding: false`

### `microk8s_port_forward_port`
- **Type**: `integer`
- **Default**: `16443`
- **Description**: Local port number for SSH port forwarding to the MicroK8s API server. The kubeconfig will be configured to use `https://127.0.0.1:{{ microk8s_port_forward_port }}`.
- **Example**: `microk8s_port_forward_port: 16443`

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Install MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
      vars:
        config_folder: /opt/maia/config
```

**Important**: Ensure the config folder contains:
- `env.json` with `DEPLOY_KUBECONFIG` variable
- `microk8s-config.yaml` configuration file

### Custom MicroK8s Version

Specify a different MicroK8s version:

```yaml
- name: Install MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
      vars:
        config_folder: /opt/maia/config
        microk8s_version: 1.30/stable
```

### Custom Addons

Enable additional MicroK8s addons:

```yaml
- name: Install MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
      vars:
        config_folder: /opt/maia/config
        microk8s_addons:
          - hostpath-storage
          - rbac
          - dns
          - ingress
          - storage
```

### Custom User

Specify a different user to add to the microk8s group:

```yaml
- name: Install MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
      vars:
        config_folder: /opt/maia/config
        ansible_user: maia-admin
```

### Without Port Forwarding

Disable SSH port forwarding:

```yaml
- name: Install MicroK8s
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
      vars:
        config_folder: /opt/maia/config
        microk8s_enable_port_forwarding: false
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e config_folder=/opt/maia/config \
  -e microk8s_version=1.30/stable \
  -e ansible_user=maia-admin
```

### In install_microk8s.yaml

This role is used as part of the MAIA installation process:

```yaml
- name: Prepare hosts for Kubernetes installation
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
```

### Standalone Playbook Example

Create a dedicated playbook for MicroK8s installation:

```yaml
---
- name: Install MicroK8s on control plane
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.microk8s
      vars:
        config_folder: /opt/maia/config
        microk8s_version: 1.31/stable
        ansible_user: root
        microk8s_addons:
          - hostpath-storage
          - rbac
        microk8s_enable_port_forwarding: true
        microk8s_port_forward_port: 16443
```

## Tasks

The role performs the following tasks:

1. **Load configuration variables**: Loads `env.json` from config folder to get `DEPLOY_KUBECONFIG` and other variables
2. **Create config directory**: Creates MicroK8s configuration directory on target host
3. **Copy config file**: Copies MicroK8s configuration file to target host
4. **Update apt cache**: Updates package cache for apt
5. **Install snapd**: Installs snapd package manager
6. **Start snapd**: Ensures snapd service is running
7. **Install MicroK8s**: Installs MicroK8s via snap package manager
8. **Add user to group**: Adds specified user to microk8s group
9. **Enable addons**: Enables specified MicroK8s addons
10. **Start MicroK8s**: Starts the MicroK8s service
11. **Get kubeconfig**: Retrieves kubeconfig from MicroK8s
12. **Save kubeconfig**: Writes kubeconfig to local file specified by `DEPLOY_KUBECONFIG`
13. **Configure kubeconfig**: Updates kubeconfig to use localhost for port forwarding
14. **Open firewall ports**: Configures UFW to allow specified ports
15. **Label nodes** (conditional): Labels nodes with master and control-plane roles for hosts in `control-plane` group
16. **Copy CA certificate**: Copies root CA certificate to config folder
17. **Setup port forwarding** (conditional): Sets up SSH port forwarding if enabled

## MicroK8s Configuration Details

### Addons

The role enables MicroK8s addons by default:
- **hostpath-storage**: Provides local persistent volumes using hostPath
- **rbac**: Enables role-based access control for Kubernetes

Additional addons can be specified via the `microk8s_addons` variable.

### Port Forwarding

The role sets up SSH port forwarding to allow accessing the MicroK8s API server from localhost:
- Local port: `16443` (configurable via `microk8s_port_forward_port`)
- Remote port: `16443` (MicroK8s API server port)
- The kubeconfig is configured to use `https://127.0.0.1:16443`

### Node Labeling

For hosts in the `control-plane` group, the role automatically labels nodes with:
- `node-role.kubernetes.io/master=master`
- `node-role.kubernetes.io/control-plane=control-plane`

### Firewall Configuration

The role opens the following ports by default:
- **16443**: Kubernetes API server (for port forwarding)
- **80**: HTTP (for ingress)
- **443**: HTTPS (for ingress)

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - microk8s
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts:
   ```ini
   [control-plane]
   maia-dev-node-0 ansible_user=root ansible_become=true
   ```

2. **Prepare config folder**: Ensure the config folder contains:
   - `env.json` with `DEPLOY_KUBECONFIG` variable
   - `microk8s-config.yaml` configuration file

3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/path/to/config
   ```

4. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/path/to/config \
     -e microk8s_version=1.30/stable \
     -e microk8s_enable_port_forwarding=false
   ```

### Manual Verification

After running the role, verify the MicroK8s installation:

1. **Check MicroK8s is installed**:
   ```bash
   snap list | grep microk8s
   ```

2. **Verify MicroK8s is running**:
   ```bash
   microk8s status --wait-ready
   ```

3. **Check addons are enabled**:
   ```bash
   microk8s status
   ```
   Should show enabled addons (hostpath-storage, rbac, etc.).

4. **Verify kubeconfig file exists**:
   ```bash
   ls -l {{ DEPLOY_KUBECONFIG }}
   ```

5. **Test kubectl access**:
   ```bash
   export KUBECONFIG={{ DEPLOY_KUBECONFIG }}
   kubectl get nodes
   ```

6. **Check node labels** (for control-plane nodes):
   ```bash
   microk8s.kubectl get nodes --show-labels
   ```
   Should show `node-role.kubernetes.io/master=master` and `node-role.kubernetes.io/control-plane=control-plane`.

7. **Verify firewall ports are open**:
   ```bash
   ufw status | grep -E "(16443|80|443)"
   ```

8. **Check CA certificate was copied**:
   ```bash
   ls -l {{ config_folder }}/ca.crt
   ```

9. **Verify SSH port forwarding is working** (if enabled):
   ```bash
   export KUBECONFIG={{ DEPLOY_KUBECONFIG }}
   kubectl config set-cluster microk8s-cluster --server=https://127.0.0.1:16443
   kubectl get nodes
   ```

10. **Check MicroK8s config file**:
    ```bash
    cat /var/snap/microk8s/common/.microk8s.yaml
    ```

11. **Verify user is in microk8s group**:
    ```bash
    groups {{ ansible_user }}
    ```
    Should include `microk8s`.

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom version**: Test with different MicroK8s versions
- **Custom addons**: Test with different addon combinations
- **Custom user**: Test with different users
- **Without port forwarding**: Test with `microk8s_enable_port_forwarding: false`
- **Custom firewall ports**: Test with different port configurations

## Notes

- **Config folder requirements**: The role requires `env.json` and `microk8s-config.yaml` in the config folder. Ensure these files exist before running the role.
- **DEPLOY_KUBECONFIG**: This variable must be set in `env.json`. It specifies where the kubeconfig file will be saved locally.
- **Port forwarding**: SSH port forwarding is enabled by default to allow accessing the MicroK8s API from localhost. This requires SSH access to the target host.
- **Node labeling**: Node labels are only applied to hosts in the `control-plane` group. Ensure your inventory groups hosts correctly.
- **Firewall configuration**: The role configures UFW firewall rules. Ensure UFW is enabled (via the ufw role) for this to work.
- **Snap package manager**: MicroK8s is installed via snap. Ensure snapd is available or will be installed.
- **User permissions**: The specified user is added to the `microk8s` group, allowing them to run `microk8s` commands without sudo.
- **Sudo privileges**: The role requires elevated privileges to install packages, configure services, and modify system files.
- **Internet access**: The role requires internet access to download snap packages from the snap store.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
