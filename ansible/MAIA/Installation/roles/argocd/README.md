# ArgoCD Role

This Ansible role installs and configures ArgoCD (Argo Continuous Delivery) on a Kubernetes cluster. ArgoCD is a declarative GitOps continuous delivery tool for Kubernetes that automates the deployment of applications from Git repositories.

## Description

The `argocd` role automates the installation and configuration of ArgoCD on Kubernetes clusters. It performs the following tasks:

1. **Loads environment variables** from `env.json` in the config folder (including `argocd_bcrypt_password` and `DEPLOY_KUBECONFIG`)
2. **Installs required Python packages** (pip, python3-kubernetes) for Kubernetes API access
3. **Creates ArgoCD namespace** if it doesn't exist
4. **Configures ArgoCD admin password** using bcrypt-hashed password from environment variables
5. **Installs ArgoCD manifests** from the official ArgoCD repository
6. **Creates service account** for automation with admin role binding
7. **Sets up SSH port forwarding** to access the ArgoCD UI from localhost

This role is designed to be used as part of the MAIA installation process, particularly in the `install_microk8s.yaml` playbook, but can also be used standalone for ArgoCD installation.

## Requirements

### Ansible Version
- **Minimum Ansible version**: 2.1

### Target Systems
- **Operating System**: Ubuntu/Debian-based Linux distributions
- **Tested on**: Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04
- **Privileges**: Requires root/sudo access (use `become: true`)

### Dependencies
- **Ansible Collections**: 
  - `kubernetes.core` (for Kubernetes API access)
  - Install with: `ansible-galaxy collection install kubernetes.core`
- **No role dependencies**: This role has no dependencies on other Ansible roles

### System Requirements
- **Kubernetes cluster**: Must be accessible via kubeconfig file
- **Kubeconfig access**: `DEPLOY_KUBECONFIG` must be set in `env.json` or `KUBECONFIG` environment variable must be set
- **SSH access**: Required for port forwarding to access ArgoCD UI
- **Internet access**: Required to download ArgoCD manifests from GitHub
- **Config folder**: Must contain `env.json` with `argocd_bcrypt_password` and `DEPLOY_KUBECONFIG`

## Default Values

The following variables are set by default in `defaults/main.yml`:

| Variable | Default Value | Type | Description |
|----------|---------------|------|-------------|
| `argocd_namespace` | `argocd` | string | Namespace where ArgoCD will be installed |
| `argocd_service_account` | `argocd-sa` | string | Service account name for automation |
| `argocd_role_name` | `admin` | string | Role name for the service account |
| `argocd_manifest_url` | `https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml` | string | ArgoCD manifest URL |
| `argocd_ui_url` | `http://localhost:8080` | string | URL to access ArgoCD UI |
| `argocd_kubeconfig` | `{{ DEPLOY_KUBECONFIG \| default(lookup('env', 'KUBECONFIG'), true) }}` | string | Path to kubeconfig file |
| `argocd_port_forward_port` | `8080` | integer | Local port for SSH port forwarding |
| `argocd_enable_port_forwarding` | `true` | boolean | Enable SSH port forwarding for UI access |

## Required Values

### `config_folder`
- **Type**: `string`
- **Required**: `true`
- **Description**: Path to the configuration folder containing `env.json` with:
  - `argocd_bcrypt_password`: Bcrypt-hashed password for the ArgoCD admin user
  - `DEPLOY_KUBECONFIG`: Path to the kubeconfig file for Kubernetes cluster access
- **Example**: `config_folder: /opt/maia/config`

**Note**: The `env.json` file must exist and contain `argocd_bcrypt_password` and `DEPLOY_KUBECONFIG`. The role will fail if these are missing.

## Optional Values

All other variables are optional and can be overridden when using the role:

### `argocd_namespace`
- **Type**: `string`
- **Default**: `argocd`
- **Description**: Kubernetes namespace where ArgoCD will be installed. All ArgoCD resources will be created in this namespace.
- **Example**: `argocd_namespace: my-argocd`

### `argocd_service_account`
- **Type**: `string`
- **Default**: `argocd-sa`
- **Description**: Name of the service account created for automation. This service account is bound to the admin role for ArgoCD operations.
- **Example**: `argocd_service_account: automation-sa`

### `argocd_role_name`
- **Type**: `string`
- **Default**: `admin`
- **Description**: Role name for the service account. The service account will be bound to this role in the ArgoCD namespace.
- **Example**: `argocd_role_name: admin`

### `argocd_manifest_url`
- **Type**: `string`
- **Default**: `https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml`
- **Description**: URL to the ArgoCD installation manifests. Use this to specify a different version or custom manifests.
- **Example**: `argocd_manifest_url: https://raw.githubusercontent.com/argoproj/argo-cd/v2.8.0/manifests/install.yaml`

### `argocd_ui_url`
- **Type**: `string`
- **Default**: `http://localhost:8080`
- **Description**: URL to access the ArgoCD UI. This is used for display purposes and should match the port forwarding configuration.
- **Example**: `argocd_ui_url: http://localhost:9090`

### `argocd_kubeconfig`
- **Type**: `string`
- **Default**: `{{ DEPLOY_KUBECONFIG | default(lookup('env', 'KUBECONFIG'), true) }}`
- **Description**: Path to the kubeconfig file for accessing the Kubernetes cluster. Defaults to `DEPLOY_KUBECONFIG` from `env.json`, or falls back to `KUBECONFIG` environment variable.
- **Example**: `argocd_kubeconfig: /path/to/kubeconfig.yaml`

### `argocd_port_forward_port`
- **Type**: `integer`
- **Default**: `8080`
- **Description**: Local port number for SSH port forwarding to the ArgoCD server. The ArgoCD UI will be accessible at `http://localhost:{{ argocd_port_forward_port }}`.
- **Example**: `argocd_port_forward_port: 9090`

### `argocd_enable_port_forwarding`
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Controls whether SSH port forwarding should be set up for ArgoCD UI access. When enabled, creates an SSH tunnel from localhost to the ArgoCD server service.
- **Example**: `argocd_enable_port_forwarding: false`

## Usage

### Basic Usage

Include the role in a playbook with the required `config_folder` variable:

```yaml
- name: Install ArgoCD
  hosts: localhost
  become: true
  roles:
    - role: maia.installation.argocd
      vars:
        config_folder: /opt/maia/config
```

**Important**: Ensure `env.json` exists in the config folder and contains:
- `argocd_bcrypt_password`: Bcrypt-hashed password for ArgoCD admin
- `DEPLOY_KUBECONFIG`: Path to kubeconfig file

### Custom Namespace

Specify a different namespace for ArgoCD:

```yaml
- name: Install ArgoCD
  hosts: localhost
  become: true
  roles:
    - role: maia.installation.argocd
      vars:
        config_folder: /opt/maia/config
        argocd_namespace: my-argocd
```

### Custom Manifest URL

Use a specific ArgoCD version:

```yaml
- name: Install ArgoCD
  hosts: localhost
  become: true
  roles:
    - role: maia.installation.argocd
      vars:
        config_folder: /opt/maia/config
        argocd_manifest_url: https://raw.githubusercontent.com/argoproj/argo-cd/v2.8.0/manifests/install.yaml
```

### Without Port Forwarding

Disable SSH port forwarding:

```yaml
- name: Install ArgoCD
  hosts: localhost
  become: true
  roles:
    - role: maia.installation.argocd
      vars:
        config_folder: /opt/maia/config
        argocd_enable_port_forwarding: false
```

### Custom Port Forwarding

Use a different port for port forwarding:

```yaml
- name: Install ArgoCD
  hosts: localhost
  become: true
  roles:
    - role: maia.installation.argocd
      vars:
        config_folder: /opt/maia/config
        argocd_port_forward_port: 9090
        argocd_ui_url: http://localhost:9090
```

### Using Extra Variables

You can also pass variables via command line using `-e` or `--extra-vars`:

```bash
ansible-playbook -i inventory playbook.yaml \
  -e config_folder=/opt/maia/config \
  -e argocd_namespace=my-argocd
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
    - role: maia.installation.argocd
```

### Standalone Playbook Example

Create a dedicated playbook for ArgoCD installation:

```yaml
---
- name: Install ArgoCD on Kubernetes cluster
  hosts: localhost
  become: true
  roles:
    - role: maia.installation.argocd
      vars:
        config_folder: /opt/maia/config
        argocd_namespace: argocd
        argocd_service_account: argocd-sa
        argocd_role_name: admin
        argocd_manifest_url: https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
        argocd_ui_url: http://localhost:8080
        argocd_port_forward_port: 8080
        argocd_enable_port_forwarding: true
```

## Tasks

The role performs the following tasks:

1. **Load environment variables**: Loads `env.json` from config folder to get `argocd_bcrypt_password` and `DEPLOY_KUBECONFIG`
2. **Install pip**: Installs python3-pip package
3. **Install python3-kubernetes**: Installs python3-kubernetes package for Kubernetes API access
4. **Create ArgoCD namespace**: Creates the ArgoCD namespace if it doesn't exist
5. **Configure admin password**: Creates or updates the ArgoCD admin secret with bcrypt-hashed password
6. **Install ArgoCD manifests**: Installs ArgoCD from the official manifest URL
7. **Display UI URL**: Shows the ArgoCD UI URL for access
8. **Create service account**: Creates the automation service account in ArgoCD namespace
9. **Create role binding**: Binds the service account to the admin role
10. **Setup port forwarding** (conditional): Sets up SSH port forwarding if enabled

## ArgoCD Configuration Details

### Admin Password

The ArgoCD admin password is set using a bcrypt-hashed password from `env.json`. The password must be bcrypt-hashed before being stored in `env.json`. The role creates or updates the `argocd-secret` with:
- `admin.password`: Bcrypt-hashed password
- `admin.passwordMtime`: Current timestamp in UTC

### Service Account

The role creates a service account (`argocd-sa` by default) with admin role binding. This service account can be used for automation and API access to ArgoCD.

### Port Forwarding

The role sets up SSH port forwarding to allow accessing the ArgoCD UI from localhost:
- Local port: `8080` (configurable via `argocd_port_forward_port`)
- Remote service: `argocd-server` service in ArgoCD namespace
- Remote port: `443` (HTTPS)
- The UI is accessible at `http://localhost:8080` (or the configured port)

### Manifest Installation

ArgoCD is installed using the official installation manifests from the ArgoCD GitHub repository. The default URL points to the stable branch, but you can specify a specific version or custom manifests.

## Testing

### Test Playbook

The role includes a test playbook located at `tests/test.yml`:

```yaml
---
- hosts: all
  remote_user: root
  roles:
    - argocd
```

### Running Tests

1. **Prepare test inventory**: Ensure `tests/inventory.ini` contains your test hosts:
   ```ini
   [all]
   localhost
   ```

2. **Prepare config folder**: Ensure the config folder contains `env.json` with:
   ```json
   {
     "argocd_bcrypt_password": "$2a$10$...",
     "DEPLOY_KUBECONFIG": "/path/to/kubeconfig.yaml"
   }
   ```

3. **Ensure Kubernetes cluster is accessible**: The test requires a valid kubeconfig and accessible Kubernetes cluster.

4. **Run the test playbook**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e config_folder=/path/to/config
   ```

5. **Test with custom variables**:
   ```bash
   ansible-playbook -i tests/inventory.ini tests/test.yml \
     -e config_folder=/path/to/config \
     -e argocd_namespace=my-argocd \
     -e argocd_enable_port_forwarding=false
   ```

### Manual Verification

After running the role, verify the ArgoCD installation:

1. **Check ArgoCD namespace exists**:
   ```bash
   kubectl get namespace {{ argocd_namespace }}
   ```

2. **Check ArgoCD pods are running**:
   ```bash
   kubectl get pods -n {{ argocd_namespace }}
   ```
   All pods should be in `Running` state. Common pods include:
   - `argocd-application-controller-*`
   - `argocd-repo-server-*`
   - `argocd-server-*`
   - `argocd-redis-*`

3. **Check ArgoCD services**:
   ```bash
   kubectl get svc -n {{ argocd_namespace }}
   ```
   The `argocd-server` service should be present.

4. **Check ArgoCD secret exists**:
   ```bash
   kubectl get secret argocd-secret -n {{ argocd_namespace }}
   ```

5. **Check service account and role binding**:
   ```bash
   kubectl get serviceaccount {{ argocd_service_account }} -n {{ argocd_namespace }}
   kubectl get rolebinding {{ argocd_service_account }}-binding -n {{ argocd_namespace }}
   ```

6. **Access ArgoCD UI** (if port forwarding is enabled):
   - The role sets up SSH port forwarding to `http://localhost:{{ argocd_port_forward_port }}`
   - Open a browser and navigate to the UI URL
   - Login with username `admin` and the password from `ARGOCD_PASSWORD` in `env.json` (before bcrypt hashing)

7. **Verify ArgoCD server is responding**:
   ```bash
   curl -k https://localhost:{{ argocd_port_forward_port }}
   ```
   Or check the ArgoCD server logs:
   ```bash
   kubectl logs -n {{ argocd_namespace }} -l app.kubernetes.io/name=argocd-server
   ```

8. **Check ArgoCD application controller**:
   ```bash
   kubectl logs -n {{ argocd_namespace }} -l app.kubernetes.io/name=argocd-application-controller
   ```

### Test Scenarios

- **Default installation**: Test with all default values
- **Custom namespace**: Test with different namespace
- **Custom manifest URL**: Test with different ArgoCD version
- **Without port forwarding**: Test with `argocd_enable_port_forwarding: false`
- **Custom port**: Test with different port forwarding port
- **Custom service account**: Test with different service account name
- **Missing env.json**: Test error handling when env.json is missing
- **Invalid kubeconfig**: Test error handling when kubeconfig is invalid

## Notes

- **env.json requirement**: The role requires `env.json` in the config folder with `argocd_bcrypt_password` and `DEPLOY_KUBECONFIG`. Ensure these are set before running the role.
- **Bcrypt password**: The `argocd_bcrypt_password` must be a bcrypt-hashed password. Use a tool like `htpasswd` or ArgoCD CLI to generate the hash.
- **Kubernetes cluster**: The role requires access to a Kubernetes cluster via kubeconfig. Ensure the cluster is accessible and the kubeconfig is valid.
- **kubernetes.core collection**: The role requires the `kubernetes.core` Ansible collection. Install it with `ansible-galaxy collection install kubernetes.core`.
- **Port forwarding**: SSH port forwarding is enabled by default to allow accessing the ArgoCD UI from localhost. This requires SSH access to the control node.
- **Manifest installation**: ArgoCD is installed from the official manifests. The installation may take several minutes for all pods to become ready.
- **Idempotency**: The role is idempotent - it can be run multiple times safely. If resources already exist, they will not be recreated.
- **Service account**: The service account is created with admin role binding, providing full access to ArgoCD operations. Use with caution in production.
- **Sudo privileges**: The role requires elevated privileges to install packages and access Kubernetes resources.

## License

GPL-3.0-only

## Author Information

This role is part of the MAIA project installation automation.
