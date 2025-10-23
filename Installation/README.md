# Installation

To install MAIA, we provide a set of Ansible playbooks that automate the installation process. The playbooks are designed to be run on a fresh Ubuntu installation (we have currently tested it for Ubuntu 20.04, Ubuntu 22.04 and Ubuntu 24.04).

## 🚀 New to MAIA?

If you're setting up MAIA for the first time, check out our [**Quick Start Guide**](QUICKSTART.md) for a streamlined installation experience with step-by-step instructions.

## Quick Start - Complete Installation

For a streamlined installation experience, use our comprehensive installation script that automates all steps from Kubernetes installation through MAIA-Core deployment:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e ansible_user=maia-admin \
  -e microk8s_version=1.31/stable \
  -e nvidia_driver_package=nvidia-driver-570 \
  -e cluster_config=/path/to/maia-cluster.yaml \
  -e config_folder=/path/to/config \
  -e ARGOCD_KUBECONFIG=/path/to/argocd-kubeconfig.yaml \
  -e DEPLOY_KUBECONFIG=/path/to/deploy-kubeconfig.yaml \
  -e MAIA_PRIVATE_REGISTRY=registry.maia-cloud.com
```

This script will:
1. Install Kubernetes via MicroK8s on all nodes
2. Install NVIDIA drivers (if GPU nodes are present)
3. Configure LVM storage
4. Set up NFS storage (if configured)
5. Configure firewall rules
6. Install MAIA-Core components via ArgoCD

For step-by-step installation or customization, continue with the detailed instructions below.

## Prerequisites
- OpenSSH server should be installed on all nodes.
- Ansible should be installed locally on the machine from which you will run the playbooks (minimum version 2.9+).
- The hosts should have access to the internet to download necessary packages and dependencies.
- For GPU support: NVIDIA-capable GPUs installed on worker nodes.
- Sufficient disk space for local storage (recommended: at least 100GB per node).

## Inventory

The inventory folder is used to define the hosts and their roles in the MAIA installation. The inventory file is structured in a way that allows you to specify different groups of hosts, such as `nfs_server`, `nfs_clients`, `k8s_master`, `k8s_worker`, and `k8s_storage`. Each group can have multiple hosts, and you can define variables specific to each host or group.

See an example inventory file in `Ansible/inventory`.

### Inventory Structure for MicroK8s

For a MicroK8s-based installation, your inventory file should define at least one master node and optionally worker nodes:

```ini
[k8s_master]
maia-server-0

[k8s_worker]
maia-server-1
maia-server-2
maia-server-3

[nfs_server]
maia-server-0

[nfs_clients]
maia-server-1
maia-server-2
maia-server-3
```

The `k8s_master` group should contain exactly one node that will serve as the Kubernetes control plane. The `k8s_worker` group contains additional nodes that will join the cluster as worker nodes.

## Prepare Hosts

As a first step, you need to edit the `Ansible/inventory/hosts` file to define the hosts and their roles. For example, to simply add a group of hosts without any specific roles, you can add them as follows:

```ini
maia-server-0
maia-server-1
maia-server-2
maia-server-3
```

Be sure to replace `maia-server-0`, `maia-server-1`, etc., with the actual hostnames or IP addresses of your servers.
For convenience you can add the hosts to the `.ssh/config` file as aliases, so you can use them in the playbooks without specifying the full hostname or IP address.
Be sure to get SSH access to the hosts through their aliases by running the following command:

```bash
ssh maia-server-0
ssh maia-server-1
ssh maia-server-2
ssh maia-server-3   
```

## Step-by-Step Installation

### Step 1: Install Kubernetes with MicroK8s

**IMPORTANT ASSUMPTION:** MAIA-Core is designed to run on Kubernetes installed through MicroK8s. We provide an Ansible playbook to automate the MicroK8s installation and configuration.

To install MicroK8s on all nodes, use the [Ansible/Playbooks/install_microk8s.yaml](Ansible/Playbooks/install_microk8s.yaml) playbook:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_microk8s.yaml -e ansible_user=maia-admin -e microk8s_version=1.31/stable
```

Where:
- `ansible_user` is the user with sudo privileges on the hosts
- `microk8s_version` specifies the MicroK8s release channel (default: `1.31/stable`)

This playbook will:
- Install MicroK8s on all nodes via snap
- Configure the master node specified in the `k8s_master` group
- Join worker nodes to the cluster (if `k8s_worker` group is defined)
- Enable essential addons: dns, storage, rbac, metallb
- Configure kubectl access for the specified user
- Generate kubeconfig files for cluster management

After installation, verify the cluster status:
```bash
ssh maia-server-0  # or your master node
microk8s kubectl get nodes
```

### Step 2: NVIDIA Driver Installation

To install the NVIDIA driver on GPU-enabled hosts, you can use the [Ansible/Playbooks/install_nvidia_drivers.yaml](Ansible/Playbooks/install_nvidia_drivers.yaml) playbook. This playbook will install the NVIDIA driver on all hosts defined in the inventory file. You can run the playbook with the following command:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_nvidia_drivers.yaml -e ansible_user=maia-admin -e nvidia_driver_package=nvidia-driver-570
```

Where:
- `nvidia_driver_package` can be set to the desired NVIDIA driver package version (default: `nvidia-driver-570`)
- `ansible_user` is the user with sudo privileges on the hosts

**Note:** This step is optional and only required if your cluster includes GPU nodes.

### Step 3: Create LVMs for Local Storage
To create LVMs for local storage on the hosts, you can use the [Ansible/Playbooks/create_LVM.yaml](Ansible/Playbooks/create_LVM.yaml) playbook.
For each host, a LVM group named `MAIA_Storage` will be created, and the specified disk devices will be used to create logical volumes (`maia_0_local`) for local storage. Optionally, you can also select one of the hosts to create an NFS storage volume (`maia_0`) that can be used for shared storage across the cluster.
For each host, you need to specify the disk devices to be used for LVM in the `inventory/host_vars` folder. For example, you can create a file named `maia-server-0.yml` in the `inventory/host_vars` folder with the following content:

```yaml
device_list:
- /dev/sda1
- /dev/sdc2
local_storage_size: 300g
nfs_storage_size: 1.8t #OPTIONAL, add only if you want to create an NFS storage in the host
```
You can then run the playbook with the following command:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/create_LVM.yaml -e ansible_user=maia-admin
```
To persistently mount the LVM volumes, you can use the [Ansible/Playbooks/mount_LVM.yaml](Ansible/Playbooks/mount_LVM.yaml) playbook. This playbook will create mount points for the LVM volumes and add them to the `/etc/fstab` file for automatic mounting on boot. You can run the playbook with the following command:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/mount_LVM.yaml -e ansible_user=maia-admin
```
#### NFS Storage
If you have created an NFS storage volume in one of the hosts, you can use the [Ansible/Playbooks/nfs_storage.yaml](Ansible/Playbooks/nfs_storage.yaml) playbook to configure the NFS server and clients. This playbook will set up the NFS server on the host with the NFS storage volume and configure the clients to mount the NFS storage. 
To specify which host will be the NFS server, you can set the `nfs_server` group in the inventory file and the `nfs_clients` group for the clients. For example, you can add the following to your inventory file:
```ini
[nfs_server]
maia-server-0

[nfs_clients]
maia-server-1
maia-server-2
```

You can run the playbook with the following command: 

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/nfs_storage.yaml -e ansible_user=maia-admin
```

### Step 4: Firewall Configuration
One last step before deploying the Kubernetes cluster is to configure the firewall on the hosts. You need to allow full connectivity between the hosts.
You can use the [Ansible/Playbooks/create_ufw_roles.yaml](Ansible/Playbooks/create_ufw_roles.yaml) playbook to configure the firewall on the hosts. This playbook will allow all traffic between the hosts. You can run the playbook with the following command:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/create_ufw_roles.yaml -e ansible_user=maia-admin
```

### Step 5: CIFS Configuration (Optional)
If you want to use CIFS for shared storage, you can use the [Ansible/Playbooks/enable_CIFS.yaml](Ansible/Playbooks/enable_CIFS.yaml) playbook. This playbook will install the necessary packages and configure the CIFS server on the host. You can run the playbook with the following command:

```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/enable_CIFS.yaml -e ansible_user=maia-admin -e private_key_path=<PATH_TO_PRIVATE_KEY>
``` 
Where `private_key_path` is the path to the private key file used for credential encryption of CIFS accounts.

### Step 6: Configure Local Storage Provisioner

After the Kubernetes cluster is deployed via MicroK8s, configure the local storage provisioner. MicroK8s comes with basic storage, but for production use, we recommend deploying the Rancher Local Path Provisioner:

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.31/deploy/local-path-storage.yaml
```

This creates a StorageClass that uses the local storage from the LVM volumes created earlier at `/opt/local-path-provisioner`.

Verify the storage provisioner is running:
```bash
kubectl get pods -n local-path-storage
kubectl get storageclass
```

## Post-Deployment Rancher Cluster

After deploying the Kubernetes cluster via Rancher, some additional steps are required to finalize the MAIA-specific setup:
- Connect ArgoCD to the Rancher cluster.
- Connect the MAIA Dashboard to the Rancher cluster.

### Connect ArgoCD to the Rancher Cluster
To connect ArgoCD to the Rancher cluster, you can add the new Rancher cluster information to the Helm Chart values for the `maia-admin-admin-toolkit` application in ArgoCD, in the `maia-admin` ArgoCD project:
```yaml
additional_clusters:
    - name: "maia-cluster-name"
      server: "https://<RANCHER_CLUSTER_API_SERVER>"
      token: "<RANCHER_CLUSTER_API_TOKEN>"
```

## Step 7: MAIA Core Installation
We are now ready to install the first layer of MAIA, named `MAIA Core`. This layer provides the basic functionality of MAIA to manage the cluster and deploy applications. The installation is done via an Ansible playbook that uses the `maia-core-project` Helm Chart.
MAIA Core interacts with ArgoCD to prepare and deploy the following components:
- [Cert-Manager](https://cert-manager.io/), for managing TLS certificates.
- [MetalLB](https://metallb.io/), for providing load balancing capabilities.
- MAIA Core Toolkit, to deploy a [ClusterIssuer](https://cert-manager.io/docs/concepts/issuer/), a [Kubernetes Dashboard](https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/), and a [Metrics Server](https://github.com/kubernetes-sigs/metrics-server)
- [GPU Booking System](https://github.com/kthcloud/MAIA/blob/master/GPU_Booking_System.md), to manage GPU resources in the cluster.
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html), to provide GPU capabilities in the cluster.
- [Nginx Ingress Controller](https://docs.nginx.com/nginx-ingress-controller/) or [Traefik Ingress Controller](https://traefik.io/traefik), to manage ingress traffic. Dpeloy one of the two, depending on your preference. By default, when deploying a new Rancher cluster, the Nginx Ingress Controller is already installed, so you can skip this deployment.
- [Login App](https://github.com/fydrah/loginapp), to provide users a JWT-based authentication interface and retrieve a JWT token for accessing the MAIA services.
- [Loki](https://grafana.com/oss/loki/), for logging capabilities.
- [Prometheus](https://prometheus.io/), for monitoring capabilities, including Graphana dashboards.
-  [Tempo](https://grafana.com/oss/tempo/), for distributed tracing capabilities.
- [MinIO Operator](https://min.io/docs/minio/kubernetes/upstream/operations/installation.html), for providing object storage capabilities.
- [NFS Provisioner](https://github.com/kubernetes-sigs/nfs-subdir-external-provisioner), to provide NFS-based storage capabilities.

To install MAIA Core, you need to prepare two configuration files, one with the cluster configuration and another with the MAIA-specific configuration:

```yaml
cluster_name: "maia-cluster-name" # Name of the cluster 
argocd_destination_cluster_address:   "https://<RANCHER_CLUSTER_API_SERVER>" # Address of the Rancher cluster API server
ingress_class: "nginx" # Alternative:  "maia-core-traefik"
traefik_resolver: "maiaresolver" # Optional, to only set if using Traefik
traefik_dashboard_password: "" # Optional, Password for Traefik dashboard, generated randomly
ingress_resolver_email: ""  # Email for Let's Encrypt resolver
nginx_cluster_issuer: "cluster-issuer" #If using Nginx Ingress Controller
domain: "" # Cluster Domain, e.g., "maia.example.com"
k8s_distribution: rke2" # Alternative: "microk8s"
nfs_server: "" # NFS Server IP or hostname, if using NFS-based storage
nfs_path: "/nfs" # NFS Path, if using NFS-based storage
keycloak:
  client_secret: "" # Keycloak Client Secret for MAIA, if using Keycloak for authentication
```

```yaml
argocd_namespace: "argocd" # Namespace for ArgoCD in the Admin Cluster
admin_group_ID: "MAIA:admin" # Admin Group ID in Keycloak
dashboard_api_secret: "" # API Secret used to communicate with the MAIA Dashboard
core_project_chart: "maia-core-project" # Helm Chart for the MAIA Core project
core_project_repo: "" # Helm Repository for the MAIA Core project
core_project_version: "0.1.7" # Version of the MAIA Core project
```
Save these configurations in two separate files, under the same configuration folder. The MAIA-specific configuration file should be named `maia_config.yaml`, and the cluster configuration file should be named the same as the `cluster_name` in the cluster configuration file, e.g., `maia-cluster.yaml`.
Also, to get access to the MAIA Helm Charts and MAIA Docker images, you need to be able to access the private MAIA registry. You can do this by creating a `maia_private.json` file in the same configuration folder with the following content:

```json
{
  "harbor_username": "your_username",
  "harbor_password": "your_password"
}
```
To summarize, your configuration folder should contain the following files:
- `maia_config.yaml`: The MAIA-specific configuration file.
- `maia-cluster.yaml`: The cluster configuration file.
- `maia_private.json`: The private registry credentials file.

Finally, you can run the Ansible playbook to install MAIA Core:

```bash
export MAIA_PRIVATE_REGISTRY=<MAIA_PRIVATE_REGISTRY> # URL to the private MAIA registry, e.g., "maia-registry.example.com/maia-private"
ansible-playbook Ansible/Playbooks/install_maia_core.yaml -e cluster_config=<CONFIG_FOLDER>/maia-cluster.yaml -e config_folder=<CONFIG_FOLDER> -e ARGOCD_KUBECONFIG=<ADMIN_KUBECONFIG> -e DEPLOY_KUBECONFIG=<DEPLOY_KUBECONFIG>
```
Where `<ADMIN_KUBECONFIG>` is the kubeconfig file for the ArgoCD admin cluster, and `<DEPLOY_KUBECONFIG>` is the kubeconfig file for the Rancher cluster where MAIA Core will be deployed.

After successful installation, you can access ArgoCD and deploy the single applications that you need in your cluster.

## Configure MAIA Dashboard with New Cluster
The final step to complete the MAIA installation on the new cluster is to configure the MAIA Dashboard to connect to the new cluster. This can be done by adding the new cluster information to the ConfigMap `maia-admin-dashboard-maia-dashboard` in the namespace of the MAIA Dashboard:

```yaml
cluster_name: maia-cluster-name # Name of the cluster
api: https://<RANCHER_CLUSTER_API_SERVER> # Address of the Rancher cluster API server
maia_dashboard:
  enabled: true # Whether the Cluster should be managed by the MAIA Dashboard
  token: # Optional Token for the MAIA Dashboard, to be used if RBAC is disabled (as in Rancher deployments)
services: # List of links to services in the cluster
  argocd:  N/A
  dashboard: N/A
  grafana: N/A
  keycloak: N/A
  login: N/A
  rancher: N/A
  registry: N/A
  traefik: N/A
# For Deploying Projects in the Cluster
argocd_destination_cluster_address: https://<RANCHER_CLUSTER_API_SERVER> # Address of the Rancher cluster API server, usually the same as `api`
maia_metallb_ip: "" # Optional, MetalLB IP address for the cluster, if using MetalLB and Services of type LoadBalancer
metallb_shared_ip: "" #Optional, MetalLB Shared IP for the cluster, if using MetalLB and Services of type LoadBalancer
metallb_ip_pool: "" # Optional, MetalLB IP Pool for the cluster, if using MetalLB and Services of type LoadBalancer
ingress_class: "nginx" # Alternative:  "maia-core-traefik"
ssh_port_type: NodePort # LoadBalancer or NodePort
port_range: # LoadBalancer or NodePorts range assigned to the cluster for SSH access and Orthanc DICOM API
- 2022
- 2122
imagePullSecrets: docker-registry-secret-name # Default Docker registry secret name for pulling images in the cluster
docker_email: admin@maia.se  # Email for Docker registry authentication
docker_password: docker-password # Password for Docker registry authentication
docker_server: docker-registry-url # URL for the Docker registry, e.g., "registry.maia-cloud.com"
docker_username: docker-username # Username for Docker registry authentication
domain: cluster.domain # Domain for the cluster, e.g., "maia-cloud.com"
shared_storage_class: nfs-client # StorageClass for shared storage
storage_class: local-path # StorageClass for local storage
keycloak: # Keycloak configuration for authentication
  client_id: keycloak-client-id
  client_secret: keycloak-client-secret
  issuer_url: https://<keycloak_url>/realms/<realm_name>
  authorize_url: https://<keycloak_url>/realms/<realm_name>/protocol/openid-connect/auth
  token_url: https://<keycloak_url>/realms/<realm_name>/protocol/openid-connect/token
  userdata_url: https://<keycloak_url>/realms/<realm_name>/protocol/openid-connect/userinfo
traefik_resolver: maiaresolver # If using Traefik Ingress Controller
nginx_cluster_issuer: cluster-issuer # If using Nginx Ingress Controller
url_type: subdomain # Subpath or Subdomain
hub_storage_class: deploy-maia-storage # Optional StorageClass for the JupyterHub, Default is same as shared_storage_class
hub_image: maia-hub # Optional Custom JupyterHub image
hub_tag: latest # Optional Custom JupyterHub image tag
admins:         # Default: MAIA:admin group in Keycloak
- list
- of
- admin
- emails
ssh_hostname:  cluster.domain # Domain for SSH access
# Optional MinIO configuration to deploy Custom Python Environments, stored in MinIO
minio_url: minio.maia-cloud.com # URL for MinIO
minio_access_key: minio-access-key # Access key for MinIO
minio_secret_key: minio-secret-key # Secret key for MinIO
minio_secure: true # Whether to use HTTPS for MinIO
bucket_name: maia-bucket # Bucket name for MinIO, containing the custom Python environment
```
Additionally, you can specify the GPU resources available in the cluster in the `gpu_specs` section of the `maia_config.yaml` file in the same ConfigMap. This is useful for the GPU Booking System to manage GPU resources effectively. Here is an example of how to specify the GPU resources:

```yaml
gpu_specs:
- name: NVIDIA-GeForce-GTX-1080-Ti
  replicas: 1 
  count: 1
- name: NVIDIA-GeForce-RTX-2070-SUPER
- name: NVIDIA-GeForce-GTX-1070
- name: NVIDIA-RTX-A6000
  replicas: 1
  count: 6
```
Specify replicas and count only if you want to manage the GPU resources with the GPU Booking System.

The GPU Information can be retrieved using the following commands:
```bash
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.capacity.nvidia\.com/gpu}{"\n"}{end}'
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.nvidia\.com/gpu\.replicas}{"\n"}{end}'
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.nvidia\.com/gpu\.product}{"\n"}{end}'
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.nvidia\.com/gpu\.count}{"\n"}{end}'
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.nvidia\.com/gpu\.memory}{"\n"}{end}' | awk '{print $1 "\t" $2/1024 " GiB"}'
```

## Complete Installation Script

For convenience, we provide a comprehensive installation script that automates all the steps described above. The [install_maia_core_complete.yaml](Ansible/Playbooks/install_maia_core_complete.yaml) playbook orchestrates the entire installation process.

### Usage

The complete installation script supports different installation phases:

#### Full Installation (Recommended for New Deployments)
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=all \
  -e ansible_user=maia-admin \
  -e microk8s_version=1.31/stable \
  -e nvidia_driver_package=nvidia-driver-570 \
  -e cluster_config=/path/to/maia-cluster.yaml \
  -e config_folder=/path/to/config \
  -e ARGOCD_KUBECONFIG=/path/to/argocd-kubeconfig.yaml \
  -e DEPLOY_KUBECONFIG=/path/to/deploy-kubeconfig.yaml \
  -e MAIA_PRIVATE_REGISTRY=registry.maia-cloud.com
```

#### Kubernetes Only Installation
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=k8s-only \
  -e ansible_user=maia-admin \
  -e microk8s_version=1.31/stable
```

#### Host Preparation Only
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=prepare-only \
  -e ansible_user=maia-admin \
  -e nvidia_driver_package=nvidia-driver-570
```

#### MAIA Core Only Installation
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=core-only \
  -e cluster_config=/path/to/maia-cluster.yaml \
  -e config_folder=/path/to/config \
  -e ARGOCD_KUBECONFIG=/path/to/argocd-kubeconfig.yaml \
  -e DEPLOY_KUBECONFIG=/path/to/deploy-kubeconfig.yaml \
  -e MAIA_PRIVATE_REGISTRY=registry.maia-cloud.com
```

### Installation Phases

The complete installation script is organized into four phases:

1. **Phase 1: Kubernetes Installation**
   - Installs MicroK8s on all nodes
   - Configures master and worker nodes
   - Enables essential addons (dns, storage, rbac, metallb)

2. **Phase 2: Host Preparation**
   - Installs NVIDIA drivers (if GPU nodes are present)
   - Creates and configures LVM storage
   - Sets up NFS storage (if configured)
   - Configures firewall rules for cluster communication

3. **Phase 3: Post-Kubernetes Configuration**
   - Deploys local storage provisioner
   - Verifies cluster readiness
   - Configures storage classes

4. **Phase 4: MAIA Core Installation**
   - Creates required namespaces
   - Deploys MAIA Core components via ArgoCD
   - Configures Cert-Manager, MetalLB, and other core services

### Configuration Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `installation_phase` | Installation phase to execute | No | `all` |
| `ansible_user` | User with sudo privileges on hosts | Yes | `maia-admin` |
| `microk8s_version` | MicroK8s release channel | No | `1.31/stable` |
| `nvidia_driver_package` | NVIDIA driver package version | No | `nvidia-driver-570` |
| `cluster_config` | Path to cluster configuration file | Yes (for core) | - |
| `config_folder` | Path to configuration folder | Yes (for core) | - |
| `ARGOCD_KUBECONFIG` | Path to ArgoCD kubeconfig | Yes (for core) | - |
| `DEPLOY_KUBECONFIG` | Path to deployment kubeconfig | Yes (for core) | - |
| `MAIA_PRIVATE_REGISTRY` | Private registry URL | Yes (for core) | `registry.maia-cloud.com` |

## Troubleshooting

### Common Issues

#### MicroK8s Installation Issues
- **Issue**: MicroK8s fails to start
  - **Solution**: Check system resources (CPU, memory, disk space). Ensure snap is properly installed and running.
  - **Command**: `sudo systemctl status snapd`

- **Issue**: Worker nodes fail to join the cluster
  - **Solution**: Verify network connectivity between nodes. Check firewall rules allow communication on MicroK8s ports.
  - **Command**: `sudo ufw status`

#### Storage Issues
- **Issue**: Local path provisioner pods are not running
  - **Solution**: Verify the local-path-storage namespace exists and check pod logs.
  - **Command**: `kubectl get pods -n local-path-storage` and `kubectl logs <pod-name> -n local-path-storage`

#### GPU Issues
- **Issue**: NVIDIA GPU Operator fails to deploy
  - **Solution**: Verify NVIDIA drivers are properly installed on GPU nodes.
  - **Command**: `nvidia-smi` on each GPU node

### Verification Commands

After installation, verify the deployment with these commands:

```bash
# Check cluster nodes
kubectl get nodes

# Check all pods across namespaces
kubectl get pods --all-namespaces

# Check MAIA Core components
kubectl get pods -n observability
kubectl get pods -n cert-manager
kubectl get pods -n metallb-system
kubectl get pods -n gpu-operator
kubectl get pods -n maia-core-toolkit

# Check storage classes
kubectl get storageclass

# Check cluster resources
kubectl top nodes
kubectl top pods --all-namespaces
```

## Support and Documentation

For additional help and documentation:
- **MAIA Documentation**: https://maia-toolkit.readthedocs.io
- **MicroK8s Documentation**: https://microk8s.io/docs
- **Kubernetes Documentation**: https://kubernetes.io/docs
- **Ansible Documentation**: https://docs.ansible.com

## Contributing

If you encounter issues or have suggestions for improving the installation process, please open an issue on the [MAIA GitHub repository](https://github.com/kthcloud/MAIA).