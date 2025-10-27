# MAIA-Core Quick Start Guide

This guide will help you get MAIA-Core up and running quickly using the automated installation scripts.

## Prerequisites

Before you begin, ensure you have:

1. **Ubuntu hosts** (20.04, 22.04, or 24.04)
   - At least one host for a single-node setup
   - Multiple hosts for a production multi-node cluster
   - SSH access to all hosts

2. **Ansible installed** on your local machine
   ```bash
   pip install ansible
   ```

3. **Host configuration**:
   - OpenSSH server installed on all nodes
   - User with sudo privileges
   - Internet connectivity for downloading packages

4. **For GPU support** (optional):
   - NVIDIA GPUs installed on worker nodes
   - Compatible NVIDIA driver available

## Step 1: Prepare Your Inventory

1. Copy the example inventory file:
   ```bash
   cd Installation/Ansible/inventory
   cp hosts.example hosts
   ```

2. Edit the `hosts` file and replace the example hostnames with your actual hosts:
   ```ini
   [k8s_master]
   your-master-node

   [k8s_worker]
   your-worker-node-1
   your-worker-node-2
   ```

3. Add your hosts to `~/.ssh/config` for easier access:
   ```
   Host your-master-node
       HostName 192.168.1.10
       User maia-admin

   Host your-worker-node-1
       HostName 192.168.1.11
       User maia-admin
   ```

4. Test SSH connectivity:
   ```bash
   ssh your-master-node
   ssh your-worker-node-1
   ```

## Step 2: Configure Host Variables (Optional but Recommended)

For hosts that will use local storage:

1. Copy the example host variables:
   ```bash
   cd Installation/Ansible/inventory/host_vars
   cp maia-server-0.yaml.example your-master-node.yaml
   ```

2. Edit the file to match your disk configuration:
   ```yaml
   device_list:
     - /dev/sdb    # Adjust to your actual devices
     - /dev/sdc
   
   local_storage_size: 300g
   
   # If this host will be the NFS server:
   nfs_storage_size: 1.8t
   ```

3. Repeat for each host that needs storage configuration.

## Step 3: Prepare Configuration Files

For MAIA Core installation, you need three configuration files in a folder:

1. **Cluster configuration** (`maia-cluster.yaml`):
   ```yaml
   cluster_name: "my-maia-cluster"
   argocd_destination_cluster_address: "https://your-cluster-api:6443"
   ingress_class: "nginx"
   ingress_resolver_email: "admin@example.com"
   nginx_cluster_issuer: "cluster-issuer"
   domain: "maia.example.com"
   k8s_distribution: "microk8s"
   nfs_server: "192.168.1.10"  # IP of your NFS server
   nfs_path: "/nfs"
   keycloak:
     client_secret: "your-keycloak-secret"  # Generate a secure random secret
   ```

2. **MAIA configuration** (`maia_config.yaml`):
   ```yaml
   argocd_namespace: "argocd"
   admin_group_ID: "MAIA:admin"
   dashboard_api_secret: "your-dashboard-secret"
   core_project_chart: "maia-core-project"
   core_project_repo: "your-helm-repo-url"
   core_project_version: "0.1.7"
   ```

3. **Private registry credentials** (`maia_private.json`):
   ```json
   {
     "harbor_username": "your_username",
     "harbor_password": "your_password"
   }
   ```

## Step 4: Run the Installation

### Option A: Complete Installation (Recommended)

Install everything from scratch:

```bash
cd Installation

ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=all \
  -e ansible_user=maia-admin \
  -e microk8s_version=1.31/stable \
  -e nvidia_driver_package=nvidia-driver-570 \
  -e cluster_config=~/maia-config/maia-cluster.yaml \
  -e config_folder=~/maia-config \
  -e ARGOCD_KUBECONFIG=~/maia-config/argocd-kubeconfig.yaml \
  -e DEPLOY_KUBECONFIG=~/maia-config/deploy-kubeconfig.yaml \
  -e MAIA_PRIVATE_REGISTRY=registry.maia-cloud.com
```

The `-k` flag prompts for SSH password, `-K` for sudo password.

### Option B: Phased Installation

If you prefer to install in phases:

#### Phase 1: Install Kubernetes Only
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_microk8s.yaml \
  -e ansible_user=maia-admin \
  -e microk8s_version=1.31/stable
```

#### Phase 2: Install Remaining Components
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=prepare-only \
  -e ansible_user=maia-admin \
  -e nvidia_driver_package=nvidia-driver-570
```

#### Phase 3: Install MAIA Core
```bash
ansible-playbook -i Ansible/inventory -kK Ansible/Playbooks/install_maia_core_complete.yaml \
  -e installation_phase=core-only \
  -e cluster_config=~/maia-config/maia-cluster.yaml \
  -e config_folder=~/maia-config \
  -e ARGOCD_KUBECONFIG=~/maia-config/argocd-kubeconfig.yaml \
  -e DEPLOY_KUBECONFIG=~/maia-config/deploy-kubeconfig.yaml \
  -e MAIA_PRIVATE_REGISTRY=registry.maia-cloud.com
```

## Step 5: Verify Installation

After installation completes:

1. **Check cluster status**:
   ```bash
   ssh your-master-node
   kubectl get nodes        # Using the alias configured during installation
   kubectl get pods --all-namespaces
   ```

2. **Verify MAIA Core components**:
   ```bash
   kubectl get pods -n observability
   kubectl get pods -n cert-manager
   kubectl get pods -n metallb-system
   kubectl get pods -n gpu-operator
   kubectl get pods -n maia-core-toolkit
   ```

3. **Check storage**:
   ```bash
   kubectl get storageclass
   kubectl get pv
   ```

4. **Verify GPU nodes** (if applicable):
   ```bash
   kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.capacity.nvidia\.com/gpu}{"\n"}{end}'
   ```

## Troubleshooting

### Installation fails during Kubernetes setup
- Ensure all hosts have sufficient resources (CPU, memory, disk)
- Check network connectivity between nodes
- Verify firewall rules allow cluster communication

### Worker nodes don't join the cluster
- Check that the join token was generated correctly on the master
- Verify network connectivity from workers to master
- Check firewall rules

### Storage provisioner not working
- Verify LVM volumes were created correctly: `sudo lvs`
- Check that mount points exist: `df -h`
- Look at provisioner logs: `kubectl logs -n local-path-storage <pod-name>`

### GPU operator fails
- Verify NVIDIA drivers are installed: `nvidia-smi`
- Check GPU operator logs: `kubectl logs -n gpu-operator <pod-name>`

## Next Steps

After successful installation:

1. Access ArgoCD to manage applications
2. Configure the MAIA Dashboard with your cluster information
3. Deploy your first MAIA workspace
4. Review the full [Installation README](README.md) for advanced configuration

## Getting Help

- Full documentation: [Installation README](README.md)
- MAIA documentation: https://maia-toolkit.readthedocs.io
- Report issues: https://github.com/kthcloud/MAIA/issues

## Summary of Created Resources

After installation, your cluster will have:

- ✅ MicroK8s Kubernetes cluster
- ✅ Local storage provisioner
- ✅ NFS shared storage (if configured)
- ✅ NVIDIA GPU support (if configured)
- ✅ MAIA Core components:
  - Cert-Manager for TLS certificates
  - MetalLB for load balancing
  - NVIDIA GPU Operator
  - Monitoring stack (Prometheus, Grafana, Loki)
  - ArgoCD for GitOps deployments
  - And more...

Congratulations! Your MAIA-Core installation is complete. 🎉
