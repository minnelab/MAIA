# NVIDIA Drivers Role

This Ansible role installs NVIDIA drivers on Ubuntu/Debian systems using the apt package manager. It handles driver installation and optionally reboots the system to activate the newly installed drivers.

## Description

The `nvidia_drivers` role automates the installation of NVIDIA GPU drivers on Linux hosts. It performs the following tasks:

1. **Updates the apt cache** to ensure the latest package information is available
2. **Installs the specified NVIDIA driver package** using apt
3. **Optionally reboots the system** to activate the newly installed drivers (configurable)

This role is designed to be used as part of the MAIA installation process, particularly in the `prepare_hosts.yaml` playbook, but can also be used standalone for NVIDIA driver installation.

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
- Internet access to download NVIDIA driver packages from Ubuntu repositories
- APT package manager must be available and configured
- SSH access to target hosts

## Default Values

The following variables are set by default in `defaults/main.yaml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `nvidia_driver_package` | `nvidia-driver-570` | string | NVIDIA driver package name to install |
| `nvidia_driver_reboot` | `true` | boolean | Whether to reboot the system after driver installation |
| `nvidia_driver_reboot_timeout` | `600` | integer | Timeout in seconds for the reboot operation |

## Required Values

**None** - All variables have default values and are optional. The role can be used without specifying any variables.

## Optional Values

All variables are optional and can be overridden when using the role:

### `nvidia_driver_package`
- **Type**: `string`
- **Default**: `nvidia-driver-570`
- **Description**: Specifies the NVIDIA driver package to install. Common values include:
  - `nvidia-driver-470`
  - `nvidia-driver-510`
  - `nvidia-driver-535`
  - `nvidia-driver-570`
  - Or any other available NVIDIA driver package in the Ubuntu repositories
- **Example**: `nvidia_driver_package: nvidia-driver-535`

### `nvidia_driver_reboot`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether the system should be rebooted after driver installation. Set to `false` if you want to handle reboots manually or at a different time.
- **Example**: `nvidia_driver_reboot: false`

### `nvidia_driver_reboot_timeout`
- **Type**: `integer`
- **Default**: `600` (10 minutes)
- **Description**: Maximum time in seconds to wait for the system to come back online after reboot. This is used by Ansible's `reboot` module to wait for the system to become available again.
- **Example**: `nvidia_driver_reboot_timeout: 900`

## Usage

### Basic Usage

Include the role in a playbook with default settings:

```yaml
- name: Install NVIDIA drivers
  hosts: all
  become: true
  roles:
    - role: maia.installation.nvidia_drivers
```

### Custom Driver Package

Specify a different NVIDIA driver package:

```yaml
- name: Install NVIDIA drivers
  hosts: all
  become: true
  roles:
    - role: maia.installation.nvidia_drivers
      vars:
        nvidia_driver_package: nvidia-driver-535
```

### Without Automatic Reboot

Install drivers without automatically rebooting:

```yaml
- name: Install NVIDIA drivers
  hosts: all
  become: true
  roles:
    - role: maia.installation.nvidia_drivers
      vars:
        nvidia_driver_reboot: false
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e nvidia_driver_package=nvidia-driver-535 \
  -e nvidia_driver_reboot=false
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
    # ... other roles
```

### Standalone Playbook Example

Create a dedicated playbook for NVIDIA driver installation:

```yaml
---
- name: Install NVIDIA drivers on all hosts
  hosts: all
  become: true
  roles:
    - role: maia.installation.nvidia_drivers
      vars:
        nvidia_driver_package: nvidia-driver-570
        nvidia_driver_reboot: true
        nvidia_driver_reboot_timeout: 600
```

## Tasks

The role performs the following tasks:

1. **Update apt cache**: Ensures package information is up to date
2. **Install NVIDIA driver**: Installs the specified NVIDIA driver package
3. **Reboot system** (conditional): Reboots the system if `nvidia_driver_reboot` is set to `true`

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yaml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - nvidia_drivers
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory.ini` contains your test hosts:
   ```ini
   [all]
   maia-dev-node-0 ansible_user=root ansible_become=true
   ```

2. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yaml
   ```

3. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yaml \
     -e nvidia_driver_package=nvidia-driver-535 \
     -e nvidia_driver_reboot=false
   ```

### Manual Verification

After running the role, verify the installation:

1. **Check installed driver version**:
   ```bash
   nvidia-smi
   ```

2. **Verify driver package is installed**:
   ```bash
   dpkg -l | grep nvidia-driver
   ```

3. **Check kernel module**:
   ```bash
   lsmod | grep nvidia
   ```

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom driver package**: Test with different driver versions
- **No reboot**: Test with `nvidia_driver_reboot: false`
- **Custom timeout**: Test with different reboot timeout values

## Notes

- **Reboot behavior**: By default, the role will reboot the system after installation. Ensure your playbook execution can handle this, or set `nvidia_driver_reboot: false` to skip automatic reboot.
- **Driver compatibility**: Ensure the specified driver package is compatible with your GPU model and Ubuntu version.
- **Internet access**: The role requires internet access to download packages from Ubuntu repositories.
- **Sudo privileges**: The role requires elevated privileges to install packages and reboot the system.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.

