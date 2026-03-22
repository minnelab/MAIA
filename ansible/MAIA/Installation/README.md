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
  enable_ca: true
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
  coredns_mappings:
    - subdomain: "iam"
      coredns_ip: "<IP_ADDRESS>"
    - subdomain: "registry"
      coredns_ip: "<IP_ADDRESS>"
    - subdomain: "mgmt"
      coredns_ip: "<IP_ADDRESS>"
    - subdomain: "kubeflow"
      coredns_ip: "<IP_ADDRESS>"
  externalCA:
    name: "external-ca-secret"
    cert: "<PATH_TO_CERTIFICATE>"
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
username: admin@maia.io
password [Temporary]: admin
```

## Installation on Linux and Windows Subsystem for Linux (WSL)

To install MAIA on Linux and Windows Subsystem for Linux (WSL), you can use the following one-command installer:
```bash
# To fetch and use the latest release of the installer automatically, you can use the following command:
LATEST=$(curl -s https://api.github.com/repos/minnelab/MAIA/releases/latest | grep tag_name | cut -d '"' -f4)
wget "https://github.com/minnelab/MAIA/releases/download/${LATEST}/install_MAIA.sh" && chmod +x install_MAIA.sh && ./install_MAIA.sh
```

To access all the features of MAIA, verify that all the subdomains are mapped in your Windows or Linux hosts files:


```bash
# Add the following lines to your Windows hosts file:
# C:\Windows\System32\drivers\etc\hosts
# Add the following lines to your Linux hosts file:
# /etc/hosts
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

<!-- DOCS-START -->
<!-- DOCS-END -->

<!-- DOCS-EXAMPLE-START -->

<!-- DOCS-EXAMPLE-END -->

## MAIA Dashboard and MAIA Workspace Dev Environment

To deploy the dev environment for the MAIA Dashboard and MAIA Workspace, you can set the following environment variables before running the installer:
```bash
export DEV_BRANCH=<branch_name>
export GIT_EMAIL=<email>
export GIT_NAME=<name>
export GPG_KEY=<path/to/gpg.key>
```

The DEV_BRANCH is the branch that will be used to deploy the MAIA Dashboard and install the `maia-toolkit` package.
The GIT_EMAIL and GIT_NAME are the email and name of the user that will be used to commit the changes to the repository.
The GPG_KEY is the path to the GPG key that will be used to sign the commits.

## Extra Configuration

### Deploy MAIA-Admin without Rancher

If you want to deploy MAIA-Admin without Rancher, you can set in your config.yaml file the following variable, to force the user OIDC authentication for the MAIA Dashboard to connect with the k8s cluster (by default, the connection is done through Rancher).

```yaml
env:
  MAIA_DASHBOARD_OIDC_AUTHENTICATION: true
```

### Move Let's Encrypt staging to production

After validating the Ingress certificate with the staging CA, you can move the Let's Encrypt staging to production by performing the following steps:

1. Set the OIDC_CA_BUNDLE environment variable to True in the maia-admin-maia-dashboard Application from ArgoCD:

```yaml
env:
  - name: OIDC_CA_BUNDLE
    value: True
```

2. Remove the rootCA environment variable from the ArgoCD `argocd-cm` ConfigMap, entry `oidc.config`.

3. Remove the `--oidc-ca-file` configuration from the apiserver args (kube-apiserver) and restart the kubernetes service. In microk8s, you can find the apiserver-args in the `/var/snap/microk8s/current/args/kube-apiserver` file, while in k0s, you can find it in the `/etc/k0s/k0s.yaml` file, in k3s, you can find it in the `/etc/rancher/k3s/config.yaml` file.

4. From the `maia-admin-maia-dashboard` ConfigMap in the `maia-dashboard` namespace, edit the <cluster_name>.yaml file and set the selfsigned variable to False:

```yaml
selfsigned: false
```

From the `<cluster_name>.yaml` file in the config folder, set the `staging_certificates` variable to False and delete the `externalCA` variable:

```yaml
staging_certificates: false
externalCA: null
```

5. Restart the kubernetes service.

6. From the `maia-admin-maia-dashboard` ConfigMap in the `maia-dashboard` namespace, edit the <cluster_name>.yaml file and set the selfsigned variable to False:

```yaml
selfsigned: false
```

### Set MAIA Registry

The default MAIA Registry is ghcr.io/minnelab, but you can set it to any other registry by setting the MAIA_REGISTRY environment variable in your config.yaml file:

```yaml
env:
  MAIA_REGISTRY: maiacloudai
```

### Set Dev Environment

To enable the dev environment for the MAIA Dashboard, allowing to install, deploy and update the MAIA ecosystem with the latest changes from the dev branch, and also contributing to the MAIA Github repository, you can set the following environment variables in your config.yaml file:

```yaml
env:
  DEV_BRANCH: master
  GIT_EMAIL: <email>
  GIT_NAME: <name>
  GPG_KEY: <path/to/gpg.key>
```

### Set Webhook and Support URL

The WEBHOOK_URL is the URL of the webhook that will be used to send notifications to the admin channel, notifying the administrators about the new project registrations and user registrations.
The SUPPORT_URL is the URL for registering to the support channels, such as Discord, Slack, Mattermost, etc.

```yaml
env:
  WEBHOOK_URL: <WEBHOOK_URL>
  SUPPORT_URL: <SUPPORT_URL>
```

### Set OpenWebAI API Key and URL

To enable the OpenWebAI API for the MAIA Chatbot, you can set the following environment variables in your config.yaml file:

```yaml
env:
  OPENWEBAI_API_KEY: <OPENWEBAI_API_KEY>
  OPENWEBAI_URL: <OPENWEBAI_URL>
  OPENWEBAI_MODEL: <OPENWEBAI_MODEL>
```

The OPENWEBAI_API_KEY is the API key for the OpenWebAI API.
The OPENWEBAI_URL is the URL for the OpenWebAI API.
The OPENWEBAI_MODEL is the model to use for the OpenWebAI API.

### Set Email Notification System

The email notification system is used to send notifications to users about the user and project notifications in MAIA, such as project approval, user approval, project registration, user registration, etc.
To enable the email notification system for the MAIA Dashboard, you can set the following environment variables in your config.yaml file:

```yaml
env:
  SMTP_SENDER_EMAIL: <SMTP_SENDER_EMAIL>
  SMTP_SERVER: <SMTP_SERVER>
  SMTP_PORT: <SMTP_PORT>
  SMTP_PASSWORD: <SMTP_PASSWORD>
```

The SMTP_SENDER_EMAIL is the email address that will be used to send the notifications.
The SMTP_SERVER is the SMTP server address.
The SMTP_PORT is the SMTP server port.
The SMTP_PASSWORD is the SMTP server password.

### Select which ArgoCD applications to automatically synchronize

For the MAIA core and admin layers, you can select which ArgoCD applications to automatically synchronize by setting the following environment variables in your config.yaml file:

```yaml
install_maia_core:
  auto_sync: true
  maia_core_argocd_applications: ["maia-core-traefik", "maia-core-local-path", "maia-core-cert-manager","maia-core-metallb",  "maia-core-toolkit", "maia-core-minio-operator", "maia-core-kubeflow"]

install_maia_admin:
  auto_sync: true
  maia_admin_argocd_applications: ["maia-core-loginapp", "maia-admin-keycloak", "maia-admin-admin-toolkit"]
```

### Override default cluster configuration

To override the default cluster configuration, you can set the following variables in your config.yaml file (e.g., to set the shared storage class to microk8s-hostpath and the port range to 32000-32767):

```yaml
cluster_config_extra_env:
  shared_storage_class: microk8s-hostpath
  jupyterhub_username_claim: "email"
  port_range:
  - 32000
  - 32767
```

### Project Configuration:

To add a project to the MAIA Dashboard, you can set the following variables in your <project_id>.yaml file (or JSON file):

```yaml
name: <project_id>
  <key>: <value>
  env:
    <env_key>: <env_value>
```

and the following variables in your config.yaml file:

```yaml
env:
  maia_projects: "<path/to/project_id_1>.yaml,<path/to/project_id_2>.yaml,<path/to/project_id_3>.yaml"
```

#### Enable CIFS shared storage support

Use to enable the CIFS shared storage support for the project, creating a CIFS secret in the namespace for the CIFS encryption public key, CIFS volumes will be mounted to the JupyterHub and FileBrowser Apps.

```yaml
env:
  enable_cifs: true
```

#### MLflow and FileBrowser App Credentials

```yaml
mlflow_user: "<mlflow_user>"
mlflow_password: "<mlflow_password>"
```

#### MinIO App Credentials

```yaml
minio_user: "<minio_user>"
minio_password: "<minio_password>"
minio_console_access_key: "<minio_console_access_key>"
minio_console_secret_key: "<minio_console_secret_key>"
```

#### MySQL App Credentials

For both the MySQL deployments associated with MLFlow and Orthanc. For the Orthanc MySQL deployment, the user is `maia-admin` and the password is the same as the one for the MLFlow MySQL database.

```yaml
mysql_user: "<mysql_user>"
mysql_password: "<mysql_password>"
```

#### Load Balancer IP Whitelist

Use to whitelist the IP addresses that will be allowed to access the project services. Specifically, if the Orthanc and SSH Services are deployed as LoadBalancer, the IP addresses will be allowed to access the Orthanc and SSH Services. The IP addresses will be also allowed to access the Kubeflow project through the Authorization Policies, if Kubeflow is deployed.

```yaml
ip_whitelist:
  - "<ip_address>"
  - "<ip_address>"
```

#### Override default GPU request

Use to override the default GPU request for the project. 

```yaml
gpu_request: <gpu_request>
```


#### JupyterHub Configuration

```yaml
admins:  # List of admin emails for the JupyterHub Environment
  - "<admin_email>"
  - "<admin_email>"

password: "<password>" # Default assigned password set for all the users in the JupyterHub Environment
allow_ssh_password_authentication: "True" # Allow SSH password authentication for the JupyterHub Environment
active_server_limit: 1 # Active server limit for the JupyterHub Environment
concurrent_spawn_limit: 1 # Concurrent spawn limit for the JupyterHub Environment
shared_server_user: "<shared_server_user>" # Shared server user for the JupyterHub Environment
jupyterhub_extraEnv:
  INSTALL_SLICER: "1" # Install Slicer for the JupyterHub Environment
```

#### Resources Limits and Requests

```yaml
env:
  ORTHANC_CPU_REQUEST: "4000m"
  ORTHANC_CPU_LIMIT: "4000m"
  ORTHANC_MEMORY_REQUEST: "4Gi"
  ORTHANC_MEMORY_LIMIT: "4Gi"
  ORTHANC_MYSQL_CPU_REQUEST: "500m"
  ORTHANC_MYSQL_CPU_LIMIT: "500m"
  ORTHANC_MYSQL_MEMORY_REQUEST: "2Gi"
  ORTHANC_MYSQL_MEMORY_LIMIT: "2Gi"
  MLFLOW_CPU_REQUEST: "500m"
  MLFLOW_CPU_LIMIT: "500m"
  MLFLOW_MEMORY_REQUEST: "2Gi"
  MLFLOW_MEMORY_LIMIT: "2Gi"
  MYSQL_CPU_REQUEST: "500m"
  MYSQL_CPU_LIMIT: "500m"
  MYSQL_MEMORY_REQUEST: "2Gi"
  MYSQL_MEMORY_LIMIT: "2Gi"
```

#### MONAI Label Authentication for Orthanc

To be set only if the MONAI Label servers linked to the Orthanc deployment are protected by authentication.

```yaml
env:
  MONAI_LABEL_AUTH_USERNAME: <username>
  MONAI_LABEL_AUTH_PASSWORD: <password>
```

#### MONAI Label Models for Orthanc

To set the MONAI Label models for the Orthanc deployment, you can set the following environment variable in your config.yaml file:

```yaml
monai_label_models:
  <model_name>:
    label_info:
      params:
        label_info:
          - name: <label_1_name>
            model_name: <model_name>
          - name: <label_2_name>
            model_name: <model_name>
    host: <host>
```

#### NVFlare Dashboard

To enable the NVFlare Dashboard for the project, you can set the following environment variables in your config.yaml file:

```yaml
env:
  DEPLOY_NVFLARE_DASHBOARD: "True"
  nvflare_dashboard_admin_username: <username>
  nvflare_dashboard_admin_password: <password>
```

#### Kubeflow Project

To deploy the project as a Kubeflow project, you can set the following environment variable in your config.yaml file:

```yaml
env:
  DEPLOY_KUBEFLOW: "True"
```

#### Email to Username Map

Used to set the username when registering a new user in Keycloak.

```yaml
email_to_username_map:
  "email_1": "username_1"
  "email_2": "username_2"
  "email_3": "username_3"
```