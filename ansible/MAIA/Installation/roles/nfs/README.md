# NFS Role

This Ansible role configures NFS (Network File System) server and client for shared storage in Kubernetes clusters. It automatically detects whether a host is in the `nfs_server` or `nfs_clients` group and applies the appropriate configuration.

## Description

The `nfs` role automates the configuration of NFS server and client on Linux hosts. It performs the following tasks:

**For NFS Server hosts** (in `nfs_server` group):
1. **Installs NFS server packages** (nfs-kernel-server, nfs-common, rpcbind)
2. **Creates export directory** with specified ownership and permissions
3. **Configures NFS exports** in `/etc/exports`
4. **Starts and enables NFS server** service
5. **Configures firewall rules** to allow NFS clients to access the server

**For NFS Client hosts** (in `nfs_clients` group):
1. **Installs NFS client packages** (nfs-common, rpcbind)
2. **Creates mount point directory** with specified ownership and permissions
3. **Mounts NFS share** from the NFS server and adds it to `/etc/fstab` for persistence

This role is designed to be used as part of the MAIA installation process, particularly in the `prepare_hosts.yaml` playbook, but can also be used standalone for NFS configuration.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Tested on**: Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **No role dependencies**: This role has no dependencies on other Ansible roles
- **Ansible facts**: Requires `gather_facts: yes` to discover IP addresses for NFS mounting and firewall rules
- **UFW firewall**: The role uses UFW for firewall configuration on the server (if UFW is enabled)

### System Requirements
- **Inventory groups**: Hosts must be grouped as `nfs_server` and/or `nfs_clients` in the Ansible inventory
- **Network connectivity**: NFS clients must be able to reach the NFS server
- **Storage**: NFS server should have storage available at the export path (typically configured via LVM role)

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `nfs_export_path` | `/nfs` | string | NFS export path on server |
| `nfs_mount_path` | `/nfs` | string | NFS mount path on client |
| `nfs_export_options` | `*(rw,sync,no_subtree_check,no_root_squash)` | string | NFS export options |
| `nfs_mount_options` | `rw,sync,vers=4` | string | NFS mount options |
| `nfs_export_owner` | `nobody` | string | Owner of export/mount directories |
| `nfs_export_group` | `nogroup` | string | Group of export/mount directories |
| `nfs_export_mode` | `0777` | string | Permissions for export/mount directories |
| `nfs_server_packages` | `[nfs-kernel-server, nfs-common, rpcbind]` | list | NFS server packages to install |
| `nfs_client_packages` | `[nfs-common, rpcbind]` | list | NFS client packages to install |
| `nfs_port` | `2049` | integer | NFS port for firewall rules |

## Required Values

**None** - All variables have default values and are optional. The role can be used without specifying any variables.

**Note**: Hosts must be properly grouped in the inventory as `nfs_server` and/or `nfs_clients` for the role to apply the appropriate tasks.

## Optional Values

All variables are optional and can be overridden when using the role:

### `nfs_export_path`
- **Type**: `string`
- **Default**: `/nfs`
- **Description**: Path on the NFS server where the shared storage is exported. This should match the mount point created by the LVM role if using LVM for storage.
- **Example**: `nfs_export_path: /data/nfs`

### `nfs_mount_path`
- **Type**: `string`
- **Default**: `/nfs`
- **Description**: Path on NFS client hosts where the NFS share will be mounted.
- **Example**: `nfs_mount_path: /mnt/nfs`

### `nfs_export_options`
- **Type**: `string`
- **Default**: `*(rw,sync,no_subtree_check,no_root_squash)`
- **Description**: NFS export options in the format `client_spec(options)`. Common options:
  - `*` or specific IP/network: Client specification
  - `rw`: Read-write access
  - `ro`: Read-only access
  - `sync`: Synchronous writes
  - `async`: Asynchronous writes
  - `no_subtree_check`: Disable subtree checking
  - `no_root_squash`: Allow root access
  - `root_squash`: Map root to nobody
- **Example**: `nfs_export_options: "*(rw,sync,no_subtree_check)"`

### `nfs_mount_options`
- **Type**: `string`
- **Default**: `rw,sync,vers=4`
- **Description**: NFS mount options for client mounts. Common options:
  - `rw` or `ro`: Read-write or read-only
  - `sync` or `async`: Synchronous or asynchronous I/O
  - `vers=3` or `vers=4`: NFS version
  - `hard` or `soft`: Hard or soft mount
  - `timeo=`: Timeout in tenths of a second
- **Example**: `nfs_mount_options: "rw,sync,vers=4.2,hard"`

### `nfs_export_owner`
- **Type**: `string`
- **Default**: `nobody`
- **Description**: Owner user for export and mount directories.
- **Example**: `nfs_export_owner: nfs`

### `nfs_export_group`
- **Type**: `string`
- **Default**: `nogroup`
- **Description**: Group for export and mount directories.
- **Example**: `nfs_export_group: nfs`

### `nfs_export_mode`
- **Type**: `string`
- **Default**: `0777`
- **Description**: Permissions for export and mount directories in octal format.
- **Example**: `nfs_export_mode: '0755'`

### `nfs_server_packages`
- **Type**: `list` (of strings)
- **Default**: `[nfs-kernel-server, nfs-common, rpcbind]`
- **Description**: List of packages to install on NFS server hosts.
- **Example**: 
  ```yaml
  nfs_server_packages:
    - nfs-kernel-server
    - nfs-common
    - rpcbind
    - nfs-utils
  ```

### `nfs_client_packages`
- **Type**: `list` (of strings)
- **Default**: `[nfs-common, rpcbind]`
- **Description**: List of packages to install on NFS client hosts.
- **Example**: 
  ```yaml
  nfs_client_packages:
    - nfs-common
    - rpcbind
    - nfs-utils
  ```

### `nfs_port`
- **Type**: `integer`
- **Default**: `2049`
- **Description**: NFS port number for firewall rules. Used when configuring UFW to allow NFS clients to access the server.
- **Example**: `nfs_port: 2049`

## Usage

### Basic Usage

Include the role in a playbook. The role automatically detects group membership:

```yaml
- name: Configure NFS server and clients
  hosts: nfs_server:nfs_clients
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.nfs
```

**Important**: Ensure your inventory groups hosts correctly:
```ini
[nfs_server]
nfs-server-0

[nfs_clients]
node-0
node-1
node-2
```

### Custom Export and Mount Paths

Specify custom paths for export and mount:

```yaml
- name: Configure NFS
  hosts: nfs_server:nfs_clients
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.nfs
      vars:
        nfs_export_path: /data/nfs
        nfs_mount_path: /mnt/nfs
```

### Custom Export Options

Configure custom export options:

```yaml
- name: Configure NFS
  hosts: nfs_server:nfs_clients
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.nfs
      vars:
        nfs_export_options: "*(rw,sync,no_subtree_check)"
        nfs_mount_options: "rw,sync,vers=4.2,hard"
```

### Custom Permissions

Set custom ownership and permissions:

```yaml
- name: Configure NFS
  hosts: nfs_server:nfs_clients
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.nfs
      vars:
        nfs_export_owner: nfs
        nfs_export_group: nfs
        nfs_export_mode: '0755'
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e nfs_export_path=/data/nfs \
  -e nfs_mount_path=/mnt/nfs
```

### In prepare_hosts.yaml

This role is used as part of the MAIA installation process:

```yaml
- name: Prepare hosts for Kubernetes installation
  hosts: all
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.nvidia_drivers
    - role: maia.installation.lvm
    - role: maia.installation.ufw
    - role: maia.installation.nfs
    # ... other roles
```

### Standalone Playbook Example

Create a dedicated playbook for NFS configuration:

```yaml
---
- name: Configure NFS server and clients
  hosts: nfs_server:nfs_clients
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.nfs
      vars:
        nfs_export_path: /nfs
        nfs_mount_path: /nfs
        nfs_export_options: "*(rw,sync,no_subtree_check,no_root_squash)"
        nfs_mount_options: "rw,sync,vers=4"
        nfs_export_owner: nobody
        nfs_export_group: nogroup
        nfs_export_mode: '0777'
        nfs_port: 2049
```

## Tasks

The role performs different tasks based on host group membership:

### NFS Server Tasks (for hosts in `nfs_server` group)

1. **Install NFS server packages**: Installs nfs-kernel-server, nfs-common, and rpcbind
2. **Create export directory**: Creates the export path with specified ownership and permissions
3. **Configure NFS exports**: Adds export configuration to `/etc/exports`
4. **Restart NFS server**: Restarts the nfs-kernel-server service to apply exports
5. **Enable and start NFS server**: Ensures the service is running and enabled on boot
6. **Configure firewall rules**: Adds UFW rules to allow NFS clients to access the server

### NFS Client Tasks (for hosts in `nfs_clients` group)

1. **Install NFS client packages**: Installs nfs-common and rpcbind
2. **Create mount point**: Creates the mount point directory with specified ownership and permissions
3. **Mount NFS share**: Mounts the NFS share from the server and adds it to `/etc/fstab` for persistence

## NFS Configuration Details

### Server Configuration

The role configures the NFS server to:
- Export the specified path to all clients (configurable via `nfs_export_options`)
- Use the specified ownership and permissions
- Automatically allow NFS clients through the firewall (if UFW is enabled)

### Client Configuration

The role configures NFS clients to:
- Mount the NFS share from the first host in the `nfs_server` group
- Use the specified mount options
- Persistently mount the share via `/etc/fstab`

### Group-Based Configuration

The role automatically detects host group membership:
- Hosts in `nfs_server` group: Server configuration is applied
- Hosts in `nfs_clients` group: Client configuration is applied
- Hosts in both groups: Both server and client configurations are applied

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  gather_facts: yes
  roles:
    - nfs
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts with proper groups:
   ```ini
   [nfs_server]
   nfs-server-0 ansible_user=root ansible_become=true

   [nfs_clients]
   node-0 ansible_user=root ansible_become=true
   node-1 ansible_user=root ansible_become=true
   ```

2. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml
   ```

3. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e nfs_export_path=/data/nfs \
     -e nfs_mount_path=/mnt/nfs
   ```

### Manual Verification

After running the role, verify the NFS configuration:

**For NFS Server:**

1. **Check NFS packages are installed**:
   ```bash
   dpkg -l | grep -E "(nfs-kernel-server|nfs-common|rpcbind)"
   ```

2. **Verify export directory exists**:
   ```bash
   ls -ld {{ nfs_export_path }}
   ```

3. **Check NFS exports configuration**:
   ```bash
   cat /etc/exports
   ```
   Should contain an entry for `{{ nfs_export_path }}`.

4. **Verify NFS service is running**:
   ```bash
   systemctl status nfs-kernel-server
   ```

5. **Check NFS service is enabled**:
   ```bash
   systemctl is-enabled nfs-kernel-server
   ```
   Should output `enabled`.

6. **Test NFS export**:
   ```bash
   showmount -e localhost
   ```
   Should list the exported path.

7. **Verify firewall rules** (if UFW is enabled):
   ```bash
   ufw status | grep {{ nfs_port }}
   ```

**For NFS Clients:**

1. **Check NFS client packages are installed**:
   ```bash
   dpkg -l | grep -E "(nfs-common|rpcbind)"
   ```

2. **Verify mount point exists**:
   ```bash
   ls -ld {{ nfs_mount_path }}
   ```

3. **Check NFS share is mounted**:
   ```bash
   mount | grep nfs
   ```
   Should show the NFS mount.

4. **Verify mount entry in /etc/fstab**:
   ```bash
   grep nfs /etc/fstab
   ```

5. **Test write access** (if applicable):
   ```bash
   touch {{ nfs_mount_path }}/test_file && rm {{ nfs_mount_path }}/test_file
   ```

6. **Test read access**:
   ```bash
   ls -la {{ nfs_mount_path }}
   ```

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom paths**: Test with different export and mount paths
- **Custom permissions**: Test with different ownership and permissions
- **Custom export options**: Test with different export and mount options
- **Server-only**: Test on hosts in only `nfs_server` group
- **Client-only**: Test on hosts in only `nfs_clients` group
- **Both roles**: Test on hosts in both groups

## Notes

- **Inventory groups required**: Hosts must be properly grouped as `nfs_server` and/or `nfs_clients` in the Ansible inventory for the role to function correctly.
- **Ansible facts required**: The role requires `gather_facts: yes` to discover IP addresses for NFS mounting and firewall rules.
- **Storage prerequisite**: The NFS server should have storage available at the export path. This is typically configured using the LVM role to create the `/nfs` logical volume.
- **Firewall configuration**: The role automatically configures UFW firewall rules on the server to allow NFS clients. Ensure UFW is enabled (via the ufw role) for this to work.
- **NFS version**: Default mount options use NFSv4. Ensure your NFS server supports the specified version.
- **Mount persistence**: The role automatically adds mount entries to `/etc/fstab` for persistent mounting across reboots.
- **Single server assumption**: The client configuration assumes a single NFS server (uses the first host in `nfs_server` group). For multiple servers, additional configuration may be needed.
- **Sudo privileges**: The role requires elevated privileges to install packages, create directories, configure services, and modify system files.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
