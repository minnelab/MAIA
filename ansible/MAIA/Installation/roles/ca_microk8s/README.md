# CA MicroK8s Role

This Ansible role configures the Kubernetes CA (Certificate Authority) certificate and key from MicroK8s to be used with cert-manager. It creates a TLS secret in the cert-manager namespace containing the MicroK8s CA certificate and private key, which is required for cert-manager to issue certificates signed by the Kubernetes CA.

## Description

The `ca_microk8s` role automates the configuration of the Kubernetes CA certificate for cert-manager. It performs the following tasks:

1. **Verifies CA certificate and key exist** at the specified paths
2. **Creates cert-manager namespace** if it doesn't already exist
3. **Creates TLS secret** containing the CA certificate and key in the cert-manager namespace

This role is designed to be used as part of the MAIA installation process, particularly in the `install_microk8s.yaml` playbook after MicroK8s is installed, but can also be used standalone for CA certificate configuration.

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
- **MicroK8s CA certificate and key**: Must exist at the default paths (`/var/snap/microk8s/current/certs/ca.crt` and `/var/snap/microk8s/current/certs/ca.key`)
- **MicroK8s kubectl access**: The role uses `microk8s.kubectl` to create namespace and secrets

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `kubernetes_ca_crt_path` | `/var/snap/microk8s/current/certs/ca.crt` | string | Path to MicroK8s CA certificate file |
| `kubernetes_ca_key_path` | `/var/snap/microk8s/current/certs/ca.key` | string | Path to MicroK8s CA private key file |
| `cert_manager_namespace` | `cert-manager` | string | Namespace for cert-manager |
| `kubernetes_ca_secret_name` | `kubernetes-ca` | string | Name of the TLS secret to create |

## Required Values

**None** - All variables have default values and are optional. The role can be used without specifying any variables.

**Note**: The MicroK8s CA certificate and key files must exist at the specified paths. The role will fail if these files are missing.

## Optional Values

All variables are optional and can be overridden when using the role:

### `kubernetes_ca_crt_path`
- **Type**: `string`
- **Default**: `/var/snap/microk8s/current/certs/ca.crt`
- **Description**: Path to the MicroK8s CA certificate file. This is the certificate that will be used by cert-manager to sign certificates.
- **Example**: `kubernetes_ca_crt_path: /var/snap/microk8s/current/certs/ca.crt`

### `kubernetes_ca_key_path`
- **Type**: `string`
- **Default**: `/var/snap/microk8s/current/certs/ca.key`
- **Description**: Path to the MicroK8s CA private key file. This is the private key corresponding to the CA certificate.
- **Example**: `kubernetes_ca_key_path: /var/snap/microk8s/current/certs/ca.key`

### `cert_manager_namespace`
- **Type**: `string`
- **Default**: `cert-manager`
- **Description**: Kubernetes namespace where cert-manager is deployed and where the CA secret will be created.
- **Example**: `cert_manager_namespace: cert-manager`

### `kubernetes_ca_secret_name`
- **Type**: `string`
- **Default**: `kubernetes-ca`
- **Description**: Name of the TLS secret that will be created in the cert-manager namespace. This secret contains both the CA certificate and private key.
- **Example**: `kubernetes_ca_secret_name: kubernetes-ca`

## Usage

### Basic Usage

Include the role in a playbook with default settings:

```yaml
- name: Configure Kubernetes CA for cert-manager
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.ca_microk8s
```

### Custom CA Certificate Paths

Specify custom paths for the CA certificate and key:

```yaml
- name: Configure Kubernetes CA
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.ca_microk8s
      vars:
        kubernetes_ca_crt_path: /custom/path/ca.crt
        kubernetes_ca_key_path: /custom/path/ca.key
```

### Custom Namespace and Secret Name

Specify a different namespace or secret name:

```yaml
- name: Configure Kubernetes CA
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.ca_microk8s
      vars:
        cert_manager_namespace: my-cert-manager
        kubernetes_ca_secret_name: my-kubernetes-ca
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e cert_manager_namespace=my-cert-manager \
  -e kubernetes_ca_secret_name=my-ca-secret
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
    - role: maia.installation.ca_microk8s
```

### Standalone Playbook Example

Create a dedicated playbook for CA configuration:

```yaml
---
- name: Configure Kubernetes CA for cert-manager
  hosts: control-plane
  become: true
  roles:
    - role: maia.installation.ca_microk8s
      vars:
        kubernetes_ca_crt_path: /var/snap/microk8s/current/certs/ca.crt
        kubernetes_ca_key_path: /var/snap/microk8s/current/certs/ca.key
        cert_manager_namespace: cert-manager
        kubernetes_ca_secret_name: kubernetes-ca
```

## Tasks

The role performs the following tasks:

1. **Check CA certificate exists**: Verifies that the CA certificate file exists at the specified path
2. **Check CA key exists**: Verifies that the CA private key file exists at the specified path
3. **Fail if files missing**: Terminates the playbook if either the certificate or key is missing
4. **Create cert-manager namespace**: Creates the cert-manager namespace if it doesn't exist (idempotent)
5. **Create TLS secret**: Creates a TLS secret in the cert-manager namespace containing the CA certificate and key
6. **Show result**: Displays the result of the secret creation

## CA Configuration Details

### Secret Structure

The role creates a Kubernetes TLS secret with:
- **Type**: `kubernetes.io/tls`
- **Data**:
  - `tls.crt`: Base64-encoded CA certificate
  - `tls.key`: Base64-encoded CA private key

### Namespace Creation

The cert-manager namespace is created if it doesn't exist. The role handles the case where the namespace already exists gracefully (idempotent operation).

### Secret Creation

The TLS secret is created using `microk8s.kubectl create secret tls`. If the secret already exists, the operation is skipped (idempotent).

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - ca_microk8s
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory.ini` contains your test hosts:
   ```ini
   [all]
   localhost
   ```

2. **Ensure MicroK8s is installed**: The test requires MicroK8s to be installed and running with CA certificate and key files present.

3. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml
   ```

4. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e cert_manager_namespace=my-cert-manager \
     -e kubernetes_ca_secret_name=my-ca-secret
   ```

### Manual Verification

After running the role, verify the CA configuration:

1. **Check cert-manager namespace exists**:
   ```bash
   microk8s.kubectl get namespace {{ cert_manager_namespace }}
   ```

2. **Check the kubernetes-ca secret exists**:
   ```bash
   microk8s.kubectl get secret {{ kubernetes_ca_secret_name }} -n {{ cert_manager_namespace }}
   ```

3. **Verify the secret contains both certificate and key**:
   ```bash
   microk8s.kubectl get secret {{ kubernetes_ca_secret_name }} -n {{ cert_manager_namespace }} -o jsonpath='{.data.tls\.crt}' | base64 -d | head -n 1
   microk8s.kubectl get secret {{ kubernetes_ca_secret_name }} -n {{ cert_manager_namespace }} -o jsonpath='{.data.tls\.key}' | base64 -d | head -n 1
   ```
   Both commands should output certificate/key data.

4. **Verify the secret type is correct**:
   ```bash
   microk8s.kubectl get secret {{ kubernetes_ca_secret_name }} -n {{ cert_manager_namespace }} -o jsonpath='{.type}'
   ```
   Should output: `kubernetes.io/tls`

5. **Check CA certificate file exists**:
   ```bash
   ls -l {{ kubernetes_ca_crt_path }}
   ```

6. **Check CA key file exists**:
   ```bash
   ls -l {{ kubernetes_ca_key_path }}
   ```

7. **Verify secret details**:
   ```bash
   microk8s.kubectl describe secret {{ kubernetes_ca_secret_name }} -n {{ cert_manager_namespace }}
   ```

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom paths**: Test with different CA certificate and key paths
- **Custom namespace**: Test with different cert-manager namespace
- **Custom secret name**: Test with different secret name
- **Missing CA files**: Test error handling when CA certificate or key is missing
- **Existing namespace**: Test idempotency when namespace already exists
- **Existing secret**: Test idempotency when secret already exists

## Notes

- **MicroK8s prerequisite**: MicroK8s must be installed and running before running this role. Install MicroK8s using the `microk8s` role first.
- **CA certificate and key**: The MicroK8s CA certificate and key must exist at the specified paths. These are typically created when MicroK8s is installed.
- **Idempotency**: The role is idempotent - it can be run multiple times safely. If the namespace or secret already exists, they will not be recreated.
- **Secret type**: The secret is created as type `kubernetes.io/tls`, which is the standard type for TLS certificates and keys in Kubernetes.
- **cert-manager integration**: This secret is used by cert-manager to issue certificates signed by the Kubernetes CA. Ensure cert-manager is configured to use this secret.
- **Sudo privileges**: The role requires elevated privileges to read certificate files and create Kubernetes resources.
- **Namespace creation**: The role creates the cert-manager namespace if it doesn't exist. If you prefer to manage namespaces separately, ensure the namespace exists before running the role.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
