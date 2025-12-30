# UFW Role

This Ansible role configures UFW (Uncomplicated Firewall) on Ubuntu/Debian systems to allow SSH access and inter-node communication for Kubernetes clusters. It handles firewall rule configuration and ensures proper network connectivity between cluster nodes.

## Description

The `ufw` role automates the configuration of UFW firewall on Linux hosts. It performs the following tasks:

1. **Enables UFW firewall** (if configured)
2. **Allows SSH access** on the specified port and protocol
3. **Allows inter-node communication** between all nodes in the inventory (bidirectional)
4. **Configures additional firewall rules** as specified

This role is designed to be used as part of the MAIA installation process, particularly in the `prepare_hosts.yaml` playbook, but can also be used standalone for UFW firewall configuration.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions (uses UFW)
- **Tested on**: Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **No role dependencies**: This role has no dependencies on other Ansible roles
- **Ansible facts**: Requires `gather_facts: yes` to discover IP addresses for inter-node communication

### System Requirements
- UFW package must be available (typically pre-installed on Ubuntu)
- SSH access to target hosts
- Network connectivity between nodes

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `ufw_enabled` | `true` | boolean | Enable UFW firewall |
| `ufw_allow_ssh` | `true` | boolean | Allow SSH access |
| `ufw_ssh_port` | `22` | integer | SSH port number |
| `ufw_ssh_proto` | `tcp` | string | SSH protocol (tcp or udp) |
| `ufw_allow_inter_node_communication` | `true` | boolean | Allow all nodes to communicate with all nodes |
| `ufw_additional_rules` | `[]` | list | Additional UFW rules to allow |

## Required Values

**None** - All variables have default values and are optional. The role can be used without specifying any variables.

## Optional Values

All variables are optional and can be overridden when using the role:

### `ufw_enabled`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether UFW firewall should be enabled. Set to `false` to skip UFW configuration entirely.
- **Example**: `ufw_enabled: false`

### `ufw_allow_ssh`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether SSH access should be allowed. Set to `false` to skip SSH rule configuration.
- **Example**: `ufw_allow_ssh: false`

### `ufw_ssh_port`
- **Type**: `integer`
- **Default**: `22`
- **Description**: Specifies the SSH port number to allow through the firewall.
- **Example**: `ufw_ssh_port: 2222`

### `ufw_ssh_proto`
- **Type**: `string`
- **Default**: `tcp`
- **Description**: Specifies the protocol for SSH (typically `tcp`). Can be `tcp` or `udp`.
- **Example**: `ufw_ssh_proto: tcp`

### `ufw_allow_inter_node_communication`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether all nodes in the inventory should be allowed to communicate with each other bidirectionally. This is essential for Kubernetes clusters where nodes need to communicate. Set to `false` to disable inter-node communication rules.
- **Example**: `ufw_allow_inter_node_communication: false`

### `ufw_additional_rules`
- **Type**: `list` (of dictionaries)
- **Default**: `[]`
- **Description**: List of additional UFW rules to allow. Each rule is a dictionary with:
  - `port` (required): Port number or service name
  - `proto` (required): Protocol (`tcp`, `udp`, or `any`)
  - `from_ip` (optional): Source IP address (if not specified, allows from anywhere)
- **Example**: 
  ```yaml
  ufw_additional_rules:
    - port: 6443
      proto: tcp
    - port: 80
      proto: tcp
    - port: 443
      proto: tcp
    - port: 16443
      proto: tcp
      from_ip: 192.168.1.0/24
  ```

## Usage

### Basic Usage

Include the role in a playbook with default settings:

```yaml
- name: Configure UFW firewall
  hosts: all
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.ufw
```

### Custom SSH Port

Specify a different SSH port:

```yaml
- name: Configure UFW firewall
  hosts: all
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.ufw
      vars:
        ufw_ssh_port: 2222
```

### With Additional Ports

Allow additional ports for Kubernetes or other services:

```yaml
- name: Configure UFW firewall
  hosts: all
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.ufw
      vars:
        ufw_additional_rules:
          - port: 6443
            proto: tcp
          - port: 80
            proto: tcp
          - port: 443
            proto: tcp
```

### Without Inter-Node Communication

Disable automatic inter-node communication rules:

```yaml
- name: Configure UFW firewall
  hosts: all
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.ufw
      vars:
        ufw_allow_inter_node_communication: false
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e ufw_ssh_port=2222 \
  -e 'ufw_additional_rules=[{"port": 6443, "proto": "tcp"}]'
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

Create a dedicated playbook for UFW configuration:

```yaml
---
- name: Configure UFW firewall on all hosts
  hosts: all
  become: true
  gather_facts: yes
  roles:
    - role: maia.installation.ufw
      vars:
        ufw_enabled: true
        ufw_allow_ssh: true
        ufw_ssh_port: 22
        ufw_ssh_proto: tcp
        ufw_allow_inter_node_communication: true
        ufw_additional_rules:
          - port: 6443
            proto: tcp
          - port: 80
            proto: tcp
          - port: 443
            proto: tcp
```

## Tasks

The role performs the following tasks:

1. **Enable UFW**: Enables the UFW firewall if `ufw_enabled` is `true`
2. **Allow SSH**: Configures SSH access rule if `ufw_allow_ssh` is `true`
3. **Allow inter-node communication**: Creates bidirectional firewall rules between all nodes in the inventory if `ufw_allow_inter_node_communication` is `true`
4. **Allow additional ports**: Configures additional firewall rules from `ufw_additional_rules` list

## Firewall Configuration Details

### Inter-Node Communication

The role automatically discovers all hosts in the `all` group and creates bidirectional firewall rules allowing:
- Traffic from each node to all other nodes
- Traffic from all other nodes to each node

This ensures full connectivity between all nodes, which is essential for Kubernetes clusters.

**Note**: The number of rules created is `(number_of_nodes - 1) * 2` per node (bidirectional communication).

### SSH Access

By default, the role allows SSH access on port 22/tcp. This can be customized via `ufw_ssh_port` and `ufw_ssh_proto` variables.

### Additional Rules

Additional rules can be specified via the `ufw_additional_rules` list. Each rule can specify:
- Port number or service name
- Protocol (tcp, udp, or any)
- Optional source IP address or network

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  gather_facts: yes
  roles:
    - ufw
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory` contains your test hosts:
   ```ini
   [all]
   maia-dev-node-0 ansible_user=root ansible_become=true
   maia-dev-node-1 ansible_user=root ansible_become=true
   ```

2. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml
   ```

3. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory tests/test.yml \
     -e ufw_ssh_port=2222 \
     -e ufw_allow_inter_node_communication=false
   ```

### Manual Verification

After running the role, verify the firewall configuration:

1. **Check UFW status**:
   ```bash
   ufw status
   ```
   Should show `Status: active` if `ufw_enabled` is `true`.

2. **Verify SSH rule**:
   ```bash
   ufw status | grep "{{ ufw_ssh_port }}"
   ```
   Should show a rule allowing the SSH port.

3. **Check all rules**:
   ```bash
   ufw status numbered
   ```
   Should show all configured rules including inter-node communication rules.

4. **Verify inter-node communication**:
   ```bash
   # From node1, test connectivity to node2
   ping -c 3 <node2_ip>
   ```

5. **Check UFW service**:
   ```bash
   systemctl status ufw
   ```
   Should show the service is enabled and running.

6. **Test SSH access**:
   ```bash
   ssh -p {{ ufw_ssh_port }} <other_node>
   ```
   Should successfully connect.

7. **Verify firewall rules are persistent**:
   ```bash
   ufw status verbose
   ```
   Should show all configured rules with details.

8. **Check rule count**:
   - For each node, verify that rules exist for all other nodes' IP addresses
   - The number of inter-node rules should match: `(number_of_nodes - 1) * 2` per node

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom SSH port**: Test with different SSH port numbers
- **Disable inter-node communication**: Test with `ufw_allow_inter_node_communication: false`
- **Additional rules**: Test with various additional port configurations
- **Disable UFW**: Test with `ufw_enabled: false` to verify no changes are made

## Notes

- **Ansible facts required**: The role requires `gather_facts: yes` to discover IP addresses for inter-node communication. Ensure facts are gathered before running the role.
- **Inter-node communication**: By default, the role allows full bidirectional communication between all nodes. This is necessary for Kubernetes clusters but may need to be restricted in production environments based on security requirements.
- **Rule ordering**: UFW rules are processed in order. The role creates rules in a specific order: SSH first, then inter-node communication, then additional rules.
- **Firewall state**: The role enables UFW but does not reload or restart the firewall service. Rules are applied immediately.
- **IP address discovery**: The role uses `ansible_default_ipv4.address` from Ansible facts. Ensure this fact is available for all hosts.
- **Sudo privileges**: The role requires elevated privileges to configure firewall rules.
- **Network connectivity**: After enabling UFW, ensure that required ports are open before the role completes, or you may lose SSH connectivity.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
