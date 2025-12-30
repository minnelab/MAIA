# LVM Role

This Ansible role configures LVM (Logical Volume Manager) for MAIA storage, creating volume groups and logical volumes for local and NFS storage. It handles LVM setup, filesystem formatting, and automatic mounting via `/etc/fstab`.

## Description

The `lvm` role automates the configuration of LVM storage on Linux hosts. It performs the following tasks:

1. **Installs lvm2 package** to ensure LVM tools are available
2. **Creates a volume group** (`MAIA_Storage`) using specified physical volumes
3. **Creates a local storage logical volume** (`maia_0_local`) for local-path-provisioner
4. **Formats volumes** to ext4 filesystem if not already formatted
5. **Creates NFS storage logical volume** (`maia_0`) for hosts in the `nfs_server` group
6. **Configures automatic mounting** by adding entries to `/etc/fstab`

This role is designed to be used as part of the MAIA installation process, particularly in the `prepare_hosts.yaml` playbook, but can also be used standalone for LVM configuration.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Linux distributions with LVM support (Ubuntu, Debian, RHEL, CentOS, etc.)
- **Tested on**: Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **Ansible Collections**: 
  - `community.general` (for `lvg` and `lvol` modules)
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- Physical volumes (disk devices) available for LVM
- Devices should not be in use or mounted before running the role
- SSH access to target hosts

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `device_list` | `[]` | list | List of physical volumes (devices) to use for the volume group |
| `local_storage_size` | `100%FREE` | string | Size of the local storage logical volume |
| `nfs_storage_size` | `100%FREE` | string | Size of the NFS storage logical volume (only for nfs_server group) |

## Required Values

### `device_list`
- **Type**: `list` (of strings)
- **Required**: `true`
- **Description**: List of physical volumes (disk devices) to use for creating the volume group. Each device should be a block device path (e.g., `/dev/sda1`, `/dev/sdb1`).
- **Example**: 
  ```yaml
  device_list:
    - /dev/sda1
    - /dev/sdc2
  ```

**Note**: This variable must be provided for each host, typically via `host_vars` or inventory variables. The role will fail if this variable is not set or is empty.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `local_storage_size`
- **Type**: `string`
- **Default**: `100%FREE`
- **Description**: Specifies the size of the local storage logical volume (`maia_0_local`). Can be specified as:
  - Absolute size: `300g`, `500m`, `1t`
  - Percentage of free space: `100%FREE`, `50%FREE`
  - Percentage of volume group: `50%VG`
- **Example**: `local_storage_size: 300g`

### `nfs_storage_size`
- **Type**: `string`
- **Default**: `100%FREE`
- **Description**: Specifies the size of the NFS storage logical volume (`maia_0`). This volume is only created for hosts in the `nfs_server` group. Can be specified as:
  - Absolute size: `1.8t`, `500g`
  - Percentage of free space: `100%FREE`, `50%FREE`
  - Percentage of volume group: `50%VG`
- **Example**: `nfs_storage_size: 1.8t`
- **Note**: This variable is only used when the host is in the `nfs_server` group in the Ansible inventory.

## Usage

### Basic Usage

Include the role in a playbook with required variables:

```yaml
- name: Configure LVM storage
  hosts: all
  become: true
  roles:
    - role: maia.installation.lvm
```

**Important**: You must provide `device_list` for each host, typically via `host_vars`:

```yaml
# host_vars/maia-server-0.yml
device_list:
  - /dev/sda1
  - /dev/sdc2
```

### Custom Storage Sizes

Specify custom sizes for local and NFS storage:

```yaml
- name: Configure LVM storage
  hosts: all
  become: true
  roles:
    - role: maia.installation.lvm
      vars:
        device_list:
          - /dev/sda1
          - /dev/sdc2
        local_storage_size: 300g
        nfs_storage_size: 1.8t
```

### Using Host Variables

Define device lists per host in `host_vars`:

```yaml
# host_vars/maia-server-0.yml
device_list:
  - /dev/sda1
  - /dev/sdc2
local_storage_size: 300g
nfs_storage_size: 1.8t  # Only for nfs_server group hosts
```

```yaml
# host_vars/maia-server-1.yml
device_list:
  - /dev/sdb1
local_storage_size: 500g
```

Then use the role in a playbook:

```yaml
- name: Configure LVM storage
  hosts: all
  become: true
  roles:
    - role: maia.installation.lvm
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e device_list='["/dev/sda1","/dev/sdc2"]' \
  -e local_storage_size=300g
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

Create a dedicated playbook for LVM configuration:

```yaml
---
- name: Configure LVM storage on all hosts
  hosts: all
  become: true
  roles:
    - role: maia.installation.lvm
      vars:
        device_list:
          - /dev/sda1
          - /dev/sdc2
        local_storage_size: 300g
        nfs_storage_size: 1.8t
```

## Tasks

The role performs the following tasks:

1. **Install lvm2 package**: Ensures LVM tools are available on the system
2. **Create volume group**: Creates `MAIA_Storage` volume group using specified physical volumes
3. **Create local storage logical volume**: Creates `maia_0_local` logical volume for local-path-provisioner
4. **Check and format filesystem**: Checks if volumes are formatted and formats them to ext4 if needed
5. **Create NFS storage logical volume** (conditional): Creates `maia_0` logical volume for hosts in `nfs_server` group
6. **Get volume UUIDs**: Retrieves UUIDs for automatic mounting
7. **Configure /etc/fstab**: Adds mount entries to `/etc/fstab` for automatic mounting on boot

## Storage Configuration Details

### Volume Group
- **Name**: `MAIA_Storage` (hardcoded)
- **Physical Volumes**: Specified via `device_list` variable

### Local Storage Logical Volume
- **Name**: `maia_0_local` (hardcoded)
- **Size**: Configurable via `local_storage_size` (default: `100%FREE`)
- **Mount Point**: `/opt/local-path-provisioner` (hardcoded)
- **Filesystem**: `ext4` (hardcoded)
- **Created for**: All hosts

### NFS Storage Logical Volume
- **Name**: `maia_0` (hardcoded)
- **Size**: Configurable via `nfs_storage_size` (default: `100%FREE`)
- **Mount Point**: `/nfs` (hardcoded)
- **Filesystem**: `ext4` (hardcoded)
- **Created for**: Only hosts in the `nfs_server` group

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - lvm
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts:
   ```ini
   [all]
   maia-dev-node-0 ansible_user=root ansible_become=true
   ```

2. **Define device_list in host_vars**: Create `host_vars/maia-dev-node-0.yml`:
   ```yaml
   device_list:
     - /dev/sda1
   ```

3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml
   ```

4. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e device_list='["/dev/sda1"]' \
     -e local_storage_size=100g
   ```

### Manual Verification

After running the role, verify the LVM configuration:

1. **Check volume group**:
   ```bash
   vgs
   vgdisplay MAIA_Storage
   ```

2. **Check logical volumes**:
   ```bash
   lvs
   lvdisplay /dev/MAIA_Storage/maia_0_local
   ```

3. **Verify filesystem**:
   ```bash
   blkid /dev/MAIA_Storage/maia_0_local
   ```

4. **Check /etc/fstab entries**:
   ```bash
   grep MAIA_Storage /etc/fstab
   ```

5. **Verify mount points** (after mounting):
   ```bash
   mount | grep MAIA_Storage
   df -h | grep MAIA_Storage
   ```

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom storage sizes**: Test with different size specifications (absolute and percentage)
- **Multiple devices**: Test with multiple physical volumes
- **NFS server configuration**: Test on hosts in `nfs_server` group
- **Non-NFS hosts**: Test on hosts not in `nfs_server` group

## Notes

- **Device availability**: Ensure the specified devices in `device_list` are available and not currently in use or mounted. The role will fail if devices are already part of another volume group or are mounted.
- **Data loss warning**: Creating volume groups and logical volumes will destroy any existing data on the specified devices. Always backup important data before running this role.
- **NFS server group**: The NFS storage logical volume is only created for hosts in the `nfs_server` group. Ensure your inventory properly groups NFS server hosts.
- **Mount points**: The role configures `/etc/fstab` but does not mount the volumes. You may need to manually mount them or reboot the system for automatic mounting.
- **Filesystem formatting**: The role only formats volumes if they are not already formatted. If a volume is already formatted with a different filesystem, it will not be reformatted.
- **Sudo privileges**: The role requires elevated privileges to install packages, create LVM structures, format filesystems, and modify `/etc/fstab`.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
