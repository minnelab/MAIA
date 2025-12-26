# CIFS Role

This Ansible role installs and configures CIFS (Common Internet File System) support for Kubernetes. It sets up the CIFS volume plugin that allows Kubernetes to mount CIFS shares as persistent volumes using flexVolume drivers.

## Description

The `cifs` role automates the installation and configuration of CIFS support for Kubernetes clusters. It performs the following tasks:

1. **Installs cifs-utils package** for CIFS filesystem support
2. **Installs python-is-python3 package** for Python compatibility
3. **Creates the CIFS plugin directory** structure in the kubelet volume plugins path
4. **Downloads the CIFS plugin script** from the MAIA repository
5. **Downloads the decrypt_string.py script** for credential decryption
6. **Copies the private key** for decrypting CIFS credentials
7. **Initializes the CIFS plugin** to register it with kubelet

This role is designed to be used as part of the MAIA installation process, particularly in the `prepare_hosts.yaml` playbook, but can also be used standalone for CIFS plugin configuration.

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
- **Kubernetes kubelet**: The plugin is installed in the kubelet volume plugins directory (`/var/lib/kubelet/volumeplugins/` by default)
- **Internet access**: Required to download CIFS plugin scripts from GitHub
- **Private key file**: The CIFS private key file must exist in the specified config folder
- **SSH access**: Required to target hosts

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `volume_driver_path` | `/var/lib/kubelet/volumeplugins/fstab~cifs` | string | Path to the volume driver plugin directory |
| `cifs_private_key_name` | `cifs_key` | string | Name of the private key file in the config folder |
| `cifs_script_url` | `https://raw.githubusercontent.com/minnelab/maia/master/CIFS/cifs` | string | URL for the CIFS plugin script |
| `cifs_decrypt_script_url` | `https://raw.githubusercontent.com/minnelab/maia/master/CIFS/decrypt_string.py` | string | URL for the decrypt_string.py script |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing the CIFS private key file. The private key file should be located at `{{ config_folder }}/{{ cifs_private_key_name }}`.
- **Example**: `config_folder: /opt/maia/config`

**Note**: The role will fail if `config_folder` is not provided or if the private key file does not exist at the expected location.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `cifs_private_key_name`
- **Type**: `string`
- **Default**: `cifs_key`
- **Description**: Name of the private key file in the config folder. The full path will be `{{ config_folder }}/{{ cifs_private_key_name }}`.
- **Example**: `cifs_private_key_name: cifs_private_key.pem`

### `volume_driver_path`
- **Type**: `string`
- **Default**: `/var/lib/kubelet/volumeplugins/fstab~cifs`
- **Description**: Path to the volume driver plugin directory. This should match your Kubernetes distribution:
  - **Standard Kubernetes**: `/var/lib/kubelet/volumeplugins/fstab~cifs`
  - **MicroK8s**: `/usr/libexec/kubernetes/kubelet-plugins/volume/exec/fstab~cifs`
- **Example**: `volume_driver_path: /usr/libexec/kubernetes/kubelet-plugins/volume/exec/fstab~cifs`

### `cifs_script_url`
- **Type**: `string`
- **Default**: `https://raw.githubusercontent.com/minnelab/maia/master/CIFS/cifs`
- **Description**: URL for downloading the CIFS plugin script. Use this to specify a custom version or fork of the script.
- **Example**: `cifs_script_url: https://raw.githubusercontent.com/minnelab/maia/v1.0.0/CIFS/cifs`

### `cifs_decrypt_script_url`
- **Type**: `string`
- **Default**: `https://raw.githubusercontent.com/minnelab/maia/master/CIFS/decrypt_string.py`
- **Description**: URL for downloading the decrypt_string.py script. Use this to specify a custom version or fork of the script.
- **Example**: `cifs_decrypt_script_url: https://raw.githubusercontent.com/minnelab/maia/v1.0.0/CIFS/decrypt_string.py`

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Configure CIFS plugin
  hosts: all
  become: true
  roles:
    - role: maia.installation.cifs
      vars:
        config_folder: /opt/maia/config
```

**Important**: Ensure the CIFS private key file exists at `{{ config_folder }}/{{ cifs_private_key_name }}` (default: `{{ config_folder }}/cifs_key`).

### Custom Private Key Name

Specify a different private key file name:

```yaml
- name: Configure CIFS plugin
  hosts: all
  become: true
  roles:
    - role: maia.installation.cifs
      vars:
        config_folder: /opt/maia/config
        cifs_private_key_name: cifs_private_key.pem
```

### MicroK8s Configuration

For MicroK8s, use the MicroK8s volume driver path:

```yaml
- name: Configure CIFS plugin for MicroK8s
  hosts: all
  become: true
  roles:
    - role: maia.installation.cifs
      vars:
        config_folder: /opt/maia/config
        volume_driver_path: /usr/libexec/kubernetes/kubelet-plugins/volume/exec/fstab~cifs
```

### Custom Script URLs

Use custom URLs for the CIFS scripts (e.g., for a specific version or fork):

```yaml
- name: Configure CIFS plugin
  hosts: all
  become: true
  roles:
    - role: maia.installation.cifs
      vars:
        config_folder: /opt/maia/config
        cifs_script_url: https://raw.githubusercontent.com/minnelab/maia/v1.0.0/CIFS/cifs
        cifs_decrypt_script_url: https://raw.githubusercontent.com/minnelab/maia/v1.0.0/CIFS/decrypt_string.py
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e config_folder=/opt/maia/config \
  -e cifs_private_key_name=cifs_key.pem
```

### In prepare_hosts.yaml

This role is used as part of the MAIA installation process:

```yaml
- name: Prepare hosts for Kubernetes installation
  hosts: all
  become: true
  roles:
    - role: maia.installation.nvidia_drivers
    - role: maia.installation.lvm
    - role: maia.installation.ufw
    - role: maia.installation.nfs
    - role: maia.installation.cifs
      vars:
        config_folder: "{{ config_folder }}"
      when: cifs_private_key is defined and cifs_private_key != ""
```

### Standalone Playbook Example

Create a dedicated playbook for CIFS plugin configuration:

```yaml
---
- name: Configure CIFS plugin on all hosts
  hosts: all
  become: true
  roles:
    - role: maia.installation.cifs
      vars:
        config_folder: /opt/maia/config
        cifs_private_key_name: cifs_key
        volume_driver_path: /var/lib/kubelet/volumeplugins/fstab~cifs
        cifs_script_url: https://raw.githubusercontent.com/minnelab/maia/master/CIFS/cifs
        cifs_decrypt_script_url: https://raw.githubusercontent.com/minnelab/maia/master/CIFS/decrypt_string.py
```

## Tasks

The role performs the following tasks:

1. **Install cifs-utils**: Installs the cifs-utils package for CIFS filesystem support
2. **Install python-is-python3**: Installs Python compatibility package
3. **Create plugin directory**: Creates the CIFS plugin directory structure
4. **Download CIFS script**: Downloads the CIFS plugin script from GitHub
5. **Download decrypt script**: Downloads the decrypt_string.py utility script
6. **Copy private key**: Copies the CIFS private key to the plugin directory
7. **Initialize plugin**: Runs the CIFS plugin init command to register it with kubelet

## CIFS Plugin Configuration Details

### Plugin Directory Structure

The role creates the following directory structure:
```
{{ volume_driver_path }}/
├── cifs                    # Main CIFS plugin script (executable)
├── decrypt_string.py       # Decryption utility (executable)
└── private_key.pem         # Private key for credential decryption
```

### Private Key

The private key is used to decrypt CIFS credentials stored in Kubernetes secrets. The key must be:
- Located in the config folder specified by `config_folder`
- Named according to `cifs_private_key_name` (default: `cifs_key`)
- A valid PEM-format private key file

### Plugin Initialization

The plugin is initialized by running `{{ volume_driver_path }}/cifs init`, which:
- Verifies required binaries are installed (mount.cifs, jq, mountpoint, base64)
- Registers the plugin with kubelet
- Returns a success message if initialization is successful

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - cifs
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts:
   ```ini
   [all]
   maia-dev-node-0 ansible_user=root ansible_become=true
   ```

2. **Prepare private key**: Ensure the CIFS private key exists in your config folder:
   ```bash
   ls -l /path/to/config/cifs_key
   ```

3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/path/to/config
   ```

4. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e config_folder=/path/to/config \
     -e cifs_private_key_name=cifs_key.pem \
     -e volume_driver_path=/usr/libexec/kubernetes/kubelet-plugins/volume/exec/fstab~cifs
   ```

### Manual Verification

After running the role, verify the CIFS plugin configuration:

1. **Check CIFS utilities are installed**:
   ```bash
   dpkg -l | grep cifs-utils
   ```

2. **Check Python compatibility package**:
   ```bash
   dpkg -l | grep python-is-python3
   ```

3. **Verify CIFS plugin directory exists**:
   ```bash
   ls -la {{ volume_driver_path }}
   ```

4. **Check CIFS plugin script is present and executable**:
   ```bash
   ls -l {{ volume_driver_path }}/cifs
   ```
   Should show executable permissions (755).

5. **Check decrypt script is present**:
   ```bash
   ls -l {{ volume_driver_path }}/decrypt_string.py
   ```
   Should show executable permissions (700).

6. **Verify private key is copied**:
   ```bash
   ls -l {{ volume_driver_path }}/private_key.pem
   ```
   Should show read permissions (644).

7. **Test CIFS plugin initialization**:
   ```bash
   {{ volume_driver_path }}/cifs init
   ```
   Should output a JSON success message without errors.

8. **Check plugin is registered** (if kubelet is running):
   ```bash
   journalctl -u kubelet | grep -i cifs
   ```
   Or check kubelet logs for CIFS plugin registration.

9. **Verify required binaries**:
   ```bash
   which mount.cifs
   which jq
   which mountpoint
   which base64
   ```
   All should return paths to the binaries.

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom private key name**: Test with different private key file names
- **MicroK8s path**: Test with MicroK8s volume driver path
- **Custom script URLs**: Test with different script URLs (version tags, forks)
- **Missing private key**: Test error handling when private key is missing

## Notes

- **Private key requirement**: The role requires a CIFS private key file to exist in the config folder. Ensure the key is generated and placed in the correct location before running the role.
- **Kubernetes distribution**: The default `volume_driver_path` is for standard Kubernetes. For MicroK8s, use `/usr/libexec/kubernetes/kubelet-plugins/volume/exec/fstab~cifs`.
- **Internet access**: The role requires internet access to download CIFS plugin scripts from GitHub. Ensure hosts can reach `raw.githubusercontent.com`.
- **Kubelet dependency**: The role installs the plugin in the kubelet volume plugins directory. Kubelet should be installed and running for the plugin to be functional.
- **Plugin initialization**: The plugin is initialized during role execution. Kubelet will discover the plugin automatically if it's running.
- **Security**: The private key file is copied to the plugin directory with restricted permissions (644). Ensure proper file system permissions are in place.
- **Sudo privileges**: The role requires elevated privileges to install packages, create directories, download files, and modify system files.
- **Conditional execution**: In `prepare_hosts.yaml`, the role is conditionally executed only when `cifs_private_key` is defined and not empty. This allows optional CIFS support.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
