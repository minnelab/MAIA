# Ansible Collection - MAIA.Installation

Documentation for the MAIA.Installation Ansible collection, which provides roles and playbooks for installing and configuring MAIA (Medical AI Assistant) infrastructure on Kubernetes clusters.

## Requirements

The following packages and tools are required before using this collection:

**Python packages:**
```bash
pip install maia-toolkit ansible jmespath
```

**System packages:**
```bash
apt install jq yq apache2-utils
```

## Installation

To install the MAIA.Installation collection, run the following command:
```bash
ansible-galaxy collection install MAIA.Installation
```

## Quickstart: Full MAIA Installation in 10 Minutes

Use the MAIA Toolkit’s one-command installer to deploy the `MAIA.Installation` collection and perform a full installation in about 10 minutes.

To run this installer, you must provide a **configuration folder** containing:

- **Inventory**: An Ansible inventory file or folder defining your hosts and their roles.
- **Configuration file**: A `config.yaml` file describing the installation steps and options.

### Example `config.yaml`

```yaml
steps:
  - prepare_hosts
  - configure_hosts
  - install_microk8s
  - install_maia_core
  - install_maia_admin
  - configure_oidc_authentication
  - get_kubeconfig_from_rancher_local
  - configure_maia_dashboard

prepare_hosts:
  nvidia_drivers: true
  ufw: true
  nfs: true
  cifs: true

install_microk8s:
  install_microk8s: true
  enable_oidc_microk8s: true
  enable_ca_microk8s: true
  install_argocd: true
  connect_to_microk8s: false
  connect_to_argocd: false

install_maia_core:
  auto_sync: true

install_maia_admin:
  auto_sync: true

configure_oidc_authentication:
  configure_rancher: true
  configure_harbor: true
  harbor_admin_user: admin
  harbor_admin_pass: Harbor12345

get_kubeconfig_from_rancher_local:
  kubeconfig_file: "local.yaml" # kubeconfig from the Rancher local cluster, stored in the config folder

configure_maia_dashboard:
  auto_sync: true

# Environment variables used during cluster configuration
env:
  MAIA_PRIVATE_REGISTRY: ""
  CLUSTER_DOMAIN: "dev.maia.se"         # Cluster domain
  CLUSTER_NAME: "maia-dev"              # Cluster name
  INGRESS_RESOLVER_EMAIL: "admin@maia.se" # Email for the ingress resolver
  K8S_DISTRIBUTION: "microk8s"

# Additional cluster configuration options
cluster_config_extra_env:
  selfsigned: true       # Use self-signed certificates instead of Let's Encrypt
  nfs_server: "X.X.X.X"  # NFS server IP
  nfs_path: "/nfs"       # NFS export path
  gpu_list:              # GPU list (name, count, replicas)
  ssh_port_type: NodePort # SSH service type: NodePort or LoadBalancer
  port_range:            # Port range for SSH services
```

### Run the Installation

From your terminal, execute:

```bash
MAIA_install --config-folder /path/to/config_folder
```