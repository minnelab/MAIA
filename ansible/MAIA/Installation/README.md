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
**Kubernetes tools:**
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh

VERSION=$(curl -s https://api.github.com/repos/argoproj/argo-cd/releases/latest | grep tag_name | cut -d '"' -f 4)
curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/download/$VERSION/argocd-linux-amd64
chmod +x /usr/local/bin/argocd
```

And verify the installations:
```bash
kubectl version
helm version
argocd version
```

### Minimum Hardware Requirements

To successfully deploy a minimal MAIA environment, your host should meet at least the following hardware specifications:

- **Memory:** 8 GB RAM
- **CPU:** 4 CPU cores
- **Disk:** 20 GB available storage

**Operating System:**  
MAIA installation has been fully tested on Ubuntu 22.04 and 24.04 LTS.

> **Note:**  
> These requirements are **ONLY** for deploying and running the MAIA platform and a basic Kubernetes cluster. If you plan to run large projects or host resource-intensive workloads, you should scale up CPU, memory, disk space, and add GPUs as needed for your use case.

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

### Example `inventory` file:
```yaml
[control-plane]
maia-dev-node-0 ansible_host=127.0.0.1 ansible_connection=local ansible_user=ansible-user ansible_become_password=ansible ansible_become=true ansible_become_method=sudo
```

### Example `config.yaml`

```yaml
# List of steps to execute in sequence, each of them is a playbook
steps:
  - prepare_hosts
  - configure_hosts
  - install_microk8s
  - install_maia_core
  - install_maia_admin
  - configure_oidc_authentication
  - get_kubeconfig_from_rancher_local
  - configure_maia_dashboard

# Playbook-specific configuration options

prepare_hosts:
  nvidia_drivers: false
  ufw: true
  nfs: false
  cifs: false

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

# Environment variables used during the execution of the script MAIA_Configure_Installation.sh
env:
  MAIA_PRIVATE_REGISTRY: ""
  CLUSTER_DOMAIN: "example.maia.com"        
  CLUSTER_NAME: "maia-cluster"             
  INGRESS_RESOLVER_EMAIL: ""
  K8S_DISTRIBUTION: "microk8s"

# Additional cluster configuration options
cluster_config_extra_env:
  selfsigned: true
  shared_storage_class: microk8s-hostpath
```

### Run the Installation

From your terminal, execute:

```bash
MAIA_install --config-folder /path/to/config_folder
```
Once the installation is complete, you can access the MAIA Dashboard at `https://maia.<cluster_domain>`.
Wait for the dashboard to be ready by checking the `maia-dashboard` namespace:

```bash
export KUBECONFIG=<CONFIG_FOLDER>/<CLUSTER_NAME>-kubeconfig.yaml
kubectl get pod -n maia-dashboard
```
Output:
```bash
NAME                                               READY   STATUS    RESTARTS   AGE
admin-minio-tenant-pool-0-0                        2/2     Running   0          44m
maia-admin-maia-dashboard-b87475666-2vs77          1/1     Running   0          3m15s
maia-admin-maia-dashboard-mysql-5fffdd655c-5x92x   1/1     Running   0          3m57s
```

For first-access, you can use the following credentials:
```bash
username: admin@maia.se
password [Temporary]: Admin
```

## Installation on Windows Subsystem for Linux (WSL)

To install MAIA on Windows Subsystem for Linux (WSL), you can use the following one-command installer:
```bash
# To fetch and use the latest release of the installer automatically, you can use the following command:
LATEST=$(curl -s https://api.github.com/repos/minnelab/MAIA/releases/latest | grep tag_name | cut -d '"' -f4)
wget "https://github.com/minnelab/MAIA/releases/download/${LATEST}/install_MAIA_WSL.sh" && chmod +x install_MAIA_WSL.sh && ./install_MAIA_WSL.sh
```

To access all the features of MAIA, verify that all the subdomains are mapped in your Windows hosts file:


```bash
# Add the following lines to your Windows hosts file:
# C:\Windows\System32\drivers\etc\hosts
<WSL_IP> <domain>
<WSL_IP> traefik.<domain>
<WSL_IP> dashboard.<domain>
<WSL_IP> grafana.<domain>
<WSL_IP> iam.<domain>
<WSL_IP> registry.<domain>
<WSL_IP> mgmt.<domain>
<WSL_IP> minio.<domain>
<WSL_IP> argocd.<domain>
<WSL_IP> maia.<domain>
<WSL_IP> test.<domain>
<WSL_IP> minio.test.<domain>
<WSL_IP> login.<domain>
```