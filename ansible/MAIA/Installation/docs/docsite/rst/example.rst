Example: Complete Cluster Setup – Components and Roles
======================================================

.. code-block:: ini

    [control-plane]
    maia-node-0 ansible_user=root ansible_become=true

    [nfs_server]
    maia-node-0 ansible_user=root ansible_become=true

    [nfs_clients]
    maia-node-1 ansible_user=root ansible_become=true
    maia-node-2 ansible_user=root ansible_become=true

With corresponding host variable files:

`host_vars/maia-node-0.yml` (control-plane and NFS server):

.. code-block:: yaml

    device_list:
      - /dev/sda1
      - /dev/sdc2
    local_storage_size: 300g
    nfs_storage_size: 1.8t

`host_vars/maia-node-1.yml` (NFS client):

.. code-block:: yaml

    device_list:
      - /dev/sda1
    local_storage_size: 500g

`host_vars/maia-node-2.yml` (NFS client):

.. code-block:: yaml

    device_list:
      - /dev/sda1
    local_storage_size: 500g

Usage
-----

The MAIA installation with MicroK8s consists of three main playbooks that should be executed in sequence:

1. Prepare Hosts
~~~~~~~~~~~~~~~~

.. code-block:: bash
    
        ansible-playbook -i inventory playbooks/prepare_hosts.yaml -e "config_folder=<CONFIG_FOLDER>" #Options -e nvidia_drivers=false -e lvm=false -e ufw=false -e nfs=false -e cifs=false


The `prepare_hosts.yaml` playbook configures the base system requirements for MAIA installation. Each component can be enabled or disabled based on your specific needs:


**Optional flags** to skip specific components:

- `-e nvidia_drivers=false` - Skip NVIDIA driver installation

- `-e lvm=false` - Skip LVM volume creation

- `-e ufw=false` - Skip UFW firewall configuration

- `-e nfs=false` - Skip NFS server/client setup

- `-e cifs=false` - Skip CIFS plugin installation

This playbook installs NVIDIA drivers (if GPUs are present), configures LVM storage, sets up firewall rules, configures NFS for shared storage, and installs the CIFS plugin for Windows-compatible storage.

Install NVIDIA Drivers
^^^^^^^^^^^^^^^^^^^^^^	

**Description**: Installs and configures NVIDIA GPU drivers on Ubuntu/Debian systems using the apt package manager. The role handles driver installation and optionally reboots the system to activate the newly installed drivers.

**Use Cases**: 
- Clusters with NVIDIA GPUs requiring GPU support for workloads
- GPU-accelerated machine learning, deep learning, or scientific computing workloads
- Kubernetes deployments using GPU operators or GPU scheduling features

**Benefits**:
- Enables GPU access for containerized workloads in Kubernetes
- Required for GPU resource allocation and scheduling
- Supports GPU monitoring and management tools
- Can be skipped if your cluster doesn't have GPUs or doesn't need GPU support

**Configuration**: Optional - can be disabled with `-e nvidia_drivers=false`

Install LVM
^^^^^^^^^^^

**Description**: Configures LVM (Logical Volume Manager) to create volume groups and logical volumes for local and NFS storage. It creates a volume group (`MAIA_Storage`) from specified physical volumes, creates logical volumes for local storage (`maia_0_local`) and optionally NFS storage (`maia_0`), formats them, and configures automatic mounting.

**Use Cases**:
- Environments requiring flexible storage management with the ability to resize volumes later
- Deployments needing to partition disk space between local storage and NFS storage
- Systems where storage requirements may change over time
- Scenarios where you want to avoid directly assigning all available disk space to the cluster

**Benefits**:
- Provides storage flexibility - volumes can be resized without reformatting
- Allows better disk space management and allocation
- Enables separation of local storage (for local-path-provisioner) and NFS storage
- Supports dynamic storage expansion as needs grow
- Prevents locking all disk space to a single purpose

**Configuration**: Recommended for production deployments - can be disabled with `-e lvm=false`

Install UFW
^^^^^^^^^^^

**Description**: Configures UFW (Uncomplicated Firewall) to allow SSH access and enable bidirectional communication between all nodes in the inventory. It automatically discovers all hosts and creates firewall rules to allow inter-node traffic, which is essential for Kubernetes cluster communication.

**Use Cases**:
- Hosts with UFW firewall enabled (default on Ubuntu)
- Kubernetes clusters where nodes need to communicate with each other
- Deployments requiring proper network connectivity between cluster nodes
- Security-conscious environments that require firewall configuration

**Benefits**:
- Ensures Kubernetes nodes can communicate with each other (required for cluster functionality)
- Maintains SSH access while configuring firewall rules
- Automatically configures rules for all nodes in the inventory
- Prevents firewall from blocking essential Kubernetes traffic (API server, kubelet, etc.)
- Can be configured to allow additional ports for specific services

**Configuration**: Recommended for most deployments - can be disabled with `-e ufw=false` if firewall is managed differently

Install NFS
^^^^^^^^^^^

**Description**: Configures NFS (Network File System) server and client components. For hosts in the `nfs_server` group, it installs NFS server packages, creates export directories, configures exports, and sets up firewall rules. For hosts in the `nfs_clients` group, it installs NFS client packages, creates mount points, and mounts the NFS share persistently.

**Use Cases**:
- Deployments requiring shared storage across multiple Kubernetes nodes
- Persistent volumes that need to be accessible from any node
- Kubernetes clusters using NFS-based storage classes
- Applications that require shared filesystem access

**Benefits**:
- Provides shared storage that can be accessed from any node in the cluster
- Enables persistent volumes that survive pod migrations
- Supports ReadWriteMany (RWX) access mode for Kubernetes volumes
- Useful for shared data, logs, or application state
- Works well with the LVM role to provide the underlying storage

**Configuration**: Required if using NFS storage - can be disabled with `-e nfs=false`

Install CIFS
^^^^^^^^^^^^

**Description**: Installs and configures CIFS (Common Internet File System) support for Kubernetes. It sets up the CIFS volume plugin that allows Kubernetes to mount CIFS/SMB shares as persistent volumes using flexVolume drivers. The role installs required packages, downloads the CIFS plugin scripts, and configures the plugin with a private key for credential decryption.

**Use Cases**:
- Deployments requiring Windows SMB/CIFS shares mounted in Kubernetes pods
- Accessing network-attached storage (NAS) devices that use SMB/CIFS protocol
- Integration with existing Windows file servers or Samba shares
- Workloads that require access to CIFS-based storage systems

**Benefits**:
- Enables Kubernetes to use existing CIFS/SMB shares as persistent volumes
- Supports encrypted credentials for secure access to CIFS shares
- Allows integration with Windows-based storage infrastructure
- Provides persistent storage option when NFS is not available
- Useful for hybrid environments with mixed storage protocols

**Configuration**: Optional - only needed if using CIFS storage. Can be disabled with `-e cifs=false` or by not providing the `cifs_private_key` variable


2. Install MicroK8s
~~~~~~~~~~~~~~~~~~~	

.. code-block:: bash

   ansible-playbook -i inventory playbooks/install_microk8s.yaml -e "config_folder=<CONFIG_FOLDER>"

The `install_microk8s.yaml` playbook installs and configures MicroK8s, a lightweight Kubernetes distribution, along with essential authentication and tooling components. Each component is executed in sequence to set up a fully functional Kubernetes cluster:

This playbook installs MicroK8s, enables OIDC authentication, creates the CA certificate in cert-manager, and installs ArgoCD for GitOps-based application management.

Install MicroK8s
^^^^^^^^^^^^^^^^^

**Description**: Installs and configures MicroK8s, a lightweight, single-package Kubernetes distribution. The role installs MicroK8s via snap, enables essential addons (hostpath-storage, rbac), configures kubeconfig for local access, sets up firewall rules, and establishes SSH port forwarding for API server access.

**Use Cases**:
- Single-node or small multi-node Kubernetes clusters
- Development and testing environments requiring quick Kubernetes setup
- Edge computing deployments needing lightweight Kubernetes
- Local development clusters for application testing

**Benefits**:
- Fast and simple Kubernetes installation via snap package manager
- Minimal resource footprint compared to full Kubernetes distributions
- Includes essential addons for storage and RBAC out of the box
- Automatic kubeconfig generation and configuration
- Built-in port forwarding for easy local access
- Supports standard Kubernetes APIs and tools

**Configuration**: Required - this is the core Kubernetes installation step

Enable OIDC
^^^^^^^^^^^

**Description**: Configures OIDC (OpenID Connect) authentication for MicroK8s, enabling integration with identity providers like Keycloak. The role configures the Kubernetes API server with OIDC parameters, allowing users to authenticate using JWT tokens from the OIDC provider.

**Use Cases**:
- Clusters requiring centralized identity management
- Integration with existing identity providers (Keycloak, Okta, etc.)
- Multi-user environments needing role-based access control
- Enterprise deployments with SSO requirements

**Benefits**:
- Enables single sign-on (SSO) for Kubernetes cluster access
- Integrates with existing identity management infrastructure
- Supports group-based authorization for RBAC
- Allows users to authenticate without managing separate Kubernetes credentials
- Provides audit trail through identity provider logs

**Configuration**: Required for OIDC-enabled clusters - ensures users can authenticate via Keycloak

Create CA in Cert-manager
^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Configures the Kubernetes CA (Certificate Authority) certificate and key from MicroK8s for use with cert-manager. Creates a TLS secret in the cert-manager namespace containing the MicroK8s CA certificate and private key, enabling cert-manager to issue certificates signed by the Kubernetes CA.

**Use Cases**:
- Clusters using cert-manager for certificate management
- Applications requiring TLS certificates signed by the cluster CA
- Secure service-to-service communication within the cluster
- Automated certificate provisioning and renewal

**Benefits**:
- Enables cert-manager to issue cluster-signed certificates
- Automates TLS certificate management for applications
- Provides secure communication between services
- Supports automatic certificate renewal
- Integrates with Let's Encrypt and other certificate authorities

**Configuration**: Required if using cert-manager - enables automated certificate management

Install ArgoCD
^^^^^^^^^^^^^^

**Description**: Installs and configures ArgoCD (Argo Continuous Delivery), a declarative GitOps continuous delivery tool for Kubernetes. The role installs ArgoCD manifests, configures the admin password, creates service accounts for automation, and sets up port forwarding for UI access.

**Use Cases**:
- GitOps-based deployment workflows
- Automated application deployment from Git repositories
- Multi-environment deployment management (dev, staging, production)
- Continuous delivery pipelines requiring declarative configuration

**Benefits**:
- Enables GitOps workflows for application deployment
- Provides declarative application management
- Supports automatic synchronization from Git repositories
- Offers web UI and CLI for application management
- Tracks application state and provides rollback capabilities
- Supports multi-cluster deployments

**Configuration**: Required for GitOps workflows - essential for MAIA's application deployment model

3. Install MAIA-Core Layer
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    ansible-playbook -i inventory playbooks/install_maia_core.yaml -e "config_folder=<CONFIG_FOLDER>"

This playbook installs the MAIA Core Toolkit, Prometheus stack for observability, and synchronizes all ArgoCD applications for core components including Traefik, cert-manager, GPU operator, MetalLB, Loki, Tempo, metrics server, GPU booking system, MinIO operator, and NFS provisioner.

**Note**: All playbooks require the `config_folder` variable to be set, which should point to the directory created by `MAIA_Configure_Installation.sh` containing `env.json` and the cluster configuration files.

The `install_maia_core.yaml` playbook installs and configures the MAIA-Core layer components on a Kubernetes cluster. This playbook deploys essential infrastructure components including ingress controllers, storage solutions, observability stack, GPU support, and core toolkit applications via ArgoCD. Each component is deployed as an ArgoCD application for GitOps-based management:

MAIA Core Toolkit Installer
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Executes the `MAIA_install_core_toolkit` command which creates and configures ArgoCD applications for all MAIA Core components. The installer reads cluster configuration and environment variables to deploy core infrastructure applications including Traefik, cert-manager, GPU operator, MetalLB, observability stack (Loki, Tempo), metrics server, GPU booking system, MinIO operator, and NFS provisioner. It also creates the necessary namespaces and configures ArgoCD project settings.

**Use Cases**:
- Initial MAIA Core infrastructure deployment
- GitOps-based infrastructure management
- Automated application lifecycle management
- Multi-component infrastructure orchestration

**Benefits**:
- Centralized deployment of all core components
- GitOps-based configuration management
- Declarative infrastructure as code
- Automated synchronization from Git repositories
- Consistent deployment across environments

**Configuration**: Required - this is the core deployment mechanism that creates all ArgoCD applications

Traefik (maia-core-traefik)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys Traefik, a modern HTTP reverse proxy and load balancer that serves as the primary ingress controller for MAIA. Traefik automatically discovers services and routes traffic based on Ingress resources, providing TLS termination, load balancing, and advanced routing capabilities. It integrates with cert-manager for automatic SSL certificate management.

**Use Cases**:
- Ingress controller for Kubernetes services
- TLS/SSL termination for HTTPS traffic
- Load balancing across service instances
- Path-based and host-based routing
- Integration with Let's Encrypt for automatic certificates

**Benefits**:
- Automatic service discovery and routing
- Dynamic configuration updates without restarts
- Built-in support for Let's Encrypt certificates
- Web dashboard for monitoring and debugging
- Support for multiple protocols (HTTP, HTTPS, TCP, UDP)

**Configuration**: Required for ingress - provides external access to MAIA services

Cert Manager (maia-core-cert-manager)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Installs cert-manager, a Kubernetes add-on that automates the management and issuance of TLS certificates from various issuing sources. It integrates with Let's Encrypt, HashiCorp Vault, and other certificate authorities to automatically provision and renew certificates for services in the cluster.

**Use Cases**:
- Automatic TLS certificate provisioning
- Certificate renewal management
- Integration with Let's Encrypt for free certificates
- Secure service-to-service communication
- Certificate management for ingress controllers

**Benefits**:
- Automated certificate lifecycle management
- Reduces manual certificate management overhead
- Supports multiple certificate authorities
- Automatic renewal before expiration
- Kubernetes-native certificate management

**Configuration**: Required for TLS - enables automatic certificate management for secure communications

GPU Operator (maia-core-gpu-operator)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys the NVIDIA GPU Operator, which automates the management of all NVIDIA software components needed to provision GPUs in Kubernetes. This includes the NVIDIA device plugin for Kubernetes, NVIDIA Container Runtime, NVIDIA driver, GPU Feature Discovery, and Data Center GPU Manager (DCGM) exporter. The operator supports both MicroK8s and RKE2 Kubernetes distributions.

**Use Cases**:
- GPU-accelerated workloads in Kubernetes
- Machine learning and deep learning training
- High-performance computing (HPC) applications
- GPU resource scheduling and management
- Multi-GPU node support

**Benefits**:
- Automated GPU driver and runtime installation
- Dynamic GPU resource allocation
- Support for multiple GPU models and architectures
- Integration with Kubernetes device plugin framework
- Monitoring and metrics via DCGM

**Configuration**: Required for GPU support - enables GPU workloads in the cluster

MetalLB (maia-core-metallb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Installs MetalLB, a load-balancer implementation for bare metal Kubernetes clusters. MetalLB provides a network load balancer that works with standard network equipment, allowing services of type LoadBalancer to receive external IP addresses. It supports both Layer 2 (ARP/NDP) and BGP modes for IP address assignment.

**Use Cases**:
- LoadBalancer services in bare metal environments
- On-premises Kubernetes deployments
- Cloud-like load balancing without cloud provider
- External IP assignment for services
- Integration with existing network infrastructure

**Benefits**:
- Enables LoadBalancer services in bare metal
- No cloud provider dependency required
- Supports both Layer 2 and BGP protocols
- Automatic IP address management
- Works with standard networking equipment

**Configuration**: Required for LoadBalancer services - provides external IPs for services

Loki (maia-core-loki)
^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys Grafana Loki, a horizontally-scalable, highly-available log aggregation system inspired by Prometheus. Loki is designed to be very cost-effective and easy to operate, indexing only metadata (labels) while storing log content separately. It integrates seamlessly with Grafana for log visualization and querying.

**Use Cases**:
- Centralized log aggregation from all pods
- Log querying and analysis
- Integration with Grafana for log visualization
- Cost-effective log storage
- Application debugging and troubleshooting

**Benefits**:
- Efficient log storage and indexing
- Prometheus-like labeling system
- Seamless Grafana integration
- Horizontal scalability
- Lower storage costs compared to full-text indexing

**Configuration**: Required for observability - provides centralized log aggregation

Tempo (maia-core-tempo)
^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Installs Grafana Tempo, a high-volume, minimal-dependency distributed tracing backend. Tempo is cost-efficient, requiring only object storage to operate, and can be used with any of the open source tracing protocols, including Jaeger, Zipkin, and OpenTelemetry. It integrates with Loki and Prometheus for correlation of traces, logs, and metrics.

**Use Cases**:
- Distributed tracing for microservices
- Performance analysis and optimization
- Request flow visualization across services
- Integration with OpenTelemetry, Jaeger, Zipkin
- Correlation of traces with logs and metrics

**Benefits**:
- Cost-effective distributed tracing
- Minimal infrastructure requirements
- Support for multiple tracing protocols
- Integration with Grafana, Loki, and Prometheus
- High-volume trace ingestion

**Configuration**: Required for observability - provides distributed tracing capabilities

Metrics Server (maia-core-metrics-server)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys Kubernetes Metrics Server, a scalable, efficient source of container resource metrics for Kubernetes built-in autoscaling pipelines. The Metrics Server collects resource usage data (CPU and memory) from each node's kubelet and makes it available via the Kubernetes Metrics API for use by Horizontal Pod Autoscaler (HPA) and Vertical Pod Autoscaler (VPA).

**Use Cases**:
- Resource metrics collection for autoscaling
- Horizontal Pod Autoscaler (HPA) support
- Vertical Pod Autoscaler (VPA) support
- Kubernetes dashboard metrics
- Resource usage monitoring

**Benefits**:
- Enables Kubernetes autoscaling features
- Efficient resource metrics collection
- Standard Kubernetes Metrics API
- Required for HPA and VPA functionality
- Low overhead metrics collection

**Configuration**: Required for autoscaling - enables HPA and VPA functionality

Prometheus Stack
^^^^^^^^^^^^^^^^^

**Description**: Installs the kube-prometheus-stack Helm chart, which includes Prometheus for metrics collection, Grafana for visualization, Alertmanager for alerting, and various exporters. This provides a complete observability solution for monitoring cluster health, application metrics, and infrastructure performance. The stack is installed in the observability namespace.

**Use Cases**:
- Cluster and application metrics collection
- Infrastructure monitoring and alerting
- Performance analysis and capacity planning
- Service level objective (SLO) monitoring
- Integration with Grafana dashboards

**Benefits**:
- Comprehensive monitoring solution
- Pre-configured Grafana dashboards
- Alertmanager for alert routing
- Prometheus Operator for easy management
- Integration with Loki and Tempo

**Configuration**: Required for observability - provides metrics collection and visualization

MAIA Core Toolkit (maia-core-toolkit)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys the MAIA Core Toolkit, which includes essential MAIA components and utilities. This includes webhooks for admission control, authentication components, and core MAIA services that provide the foundation for the MAIA platform. The toolkit provides core functionality required by other MAIA components.

**Use Cases**:
- Core MAIA platform functionality
- Admission control webhooks
- Authentication and authorization components
- Core MAIA services and APIs
- Foundation for MAIA applications

**Benefits**:
- Centralized core MAIA functionality
- Reusable components across MAIA
- Consistent authentication and authorization
- Admission control for security
- Foundation for higher-level MAIA features

**Configuration**: Required - provides core MAIA platform functionality

GPU Booking System (maia-core-gpu-booking)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys the MAIA GPU Booking System, which enables users to reserve and schedule GPU resources in the cluster. The system provides a web interface and API for booking GPUs for specific time periods, managing reservations, and tracking GPU usage. It integrates with the GPU operator and Kubernetes scheduling to allocate GPU resources.

**Use Cases**:
- GPU resource reservation and scheduling
- Multi-user GPU access management
- Time-based GPU allocation
- GPU usage tracking and reporting
- Fair resource distribution

**Benefits**:
- Prevents GPU resource conflicts
- Enables fair GPU sharing
- Time-based reservation system
- Usage tracking and reporting
- Web-based booking interface

**Configuration**: Required for GPU scheduling - enables GPU resource booking

MinIO Operator (maia-core-minio-operator)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Installs the MinIO Operator, which manages MinIO object storage instances in Kubernetes. MinIO is a high-performance, S3-compatible object storage service that can be used for storing datasets, model artifacts, backups, and other unstructured data. The operator simplifies deployment and management of MinIO instances.

**Use Cases**:
- S3-compatible object storage
- Dataset and model artifact storage
- Backup and archival storage
- Data lake infrastructure
- Integration with ML/AI workflows

**Benefits**:
- S3-compatible API
- High-performance object storage
- Kubernetes-native operator
- Simplified deployment and management
- Cost-effective storage solution

**Configuration**: Required for object storage - provides S3-compatible storage for MAIA

NFS Provisioner (maia-core-nfs-provisioner)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys an NFS server provisioner that dynamically creates PersistentVolumes for Kubernetes using an existing NFS server. The provisioner automatically creates PersistentVolumeClaims and binds them to NFS-backed PersistentVolumes, enabling dynamic storage provisioning for applications that require shared file storage.

**Use Cases**:
- Dynamic NFS storage provisioning
- Shared file storage for applications
- PersistentVolumeClaim automation
- Multi-pod shared storage
- Integration with existing NFS infrastructure

**Benefits**:
- Automatic storage provisioning
- Shared storage across pods
- Dynamic volume creation
- Integration with existing NFS servers
- Simplifies storage management

**Configuration**: Required for NFS storage - enables dynamic NFS volume provisioning

4. Install MAIA Admin Layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    ansible-playbook -i inventory playbooks/install_maia_admin.yaml -e "config_folder=<CONFIG_FOLDER>"

This playbook installs the MAIA Admin layer, deploying identity, registry, dashboards, and supporting services through the MAIA Admin Toolkit and ArgoCD applications.

**Note**: All playbooks require the `config_folder` variable to be set, pointing to the directory created by `MAIA_Configure_Installation.sh` containing `env.json` and the cluster configuration files.

The `install_maia_admin.yaml` playbook configures admin-facing components using the MAIA Admin Toolkit and ArgoCD synchronization:

MAIA Admin Toolkit Installer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Executes the `MAIA_install_admin_toolkit` command using cluster configuration and required secrets to create ArgoCD applications and supporting resources for the admin stack.

**Use Cases**:
- Initial deployment of admin-facing MAIA services
- GitOps-based lifecycle management of admin apps
- Automated provisioning of identity, registry, and dashboards

**Benefits**:
- Centralized deployment of admin services
- Declarative configuration via ArgoCD
- Consistent, repeatable rollouts across environments

**Configuration**: Required — drives creation of admin ArgoCD applications and supporting resources.

Harbor (maia-admin-harbor)
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys Harbor registry for container images and Helm charts, including project bootstrap performed by the Admin Toolkit.

**Use Cases**:
- Private image and chart registry for MAIA workloads
- Image scanning and access control
- Registry replication and retention policies

**Benefits**:
- Secure, role-based registry with scanning
- Central artifact storage for MAIA deployments
- Supports Helm/OIDC integrations

**Configuration**: Required for private registry needs and MAIA image distribution.

Keycloak (maia-admin-keycloak)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys Keycloak for identity and access management. The playbook can patch images, import the MAIA realm config map, and run `MAIA_configure_keycloak`.

**Use Cases**:
- SSO and OIDC provider for the MAIA platform
- Group-based RBAC across MAIA services
- Credential and client management

**Benefits**:
- Centralized identity with OIDC/SAML
- Realm bootstrap and automated configuration
- Integration with ArgoCD, dashboard, and other apps

**Configuration**: Required for authentication/authorization across MAIA components.

Rancher (maia-admin-rancher)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys Rancher for cluster and application lifecycle management, bootstrapped through ArgoCD.

**Use Cases**:
- Multi-cluster operations and UI
- Centralized Kubernetes management
- RBAC and policy control

**Benefits**:
- GUI-driven cluster administration
- GitOps-friendly management
- Integrated auth with Keycloak

**Configuration**: Optional but recommended for graphical cluster operations.

MAIA Admin Toolkit (maia-admin-admin-toolkit)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys admin-specific toolkit components (projects, policies, supporting services) used by the admin layer.

**Use Cases**:
- Bootstrap of admin projects and resources
- Helper services consumed by other admin apps

**Benefits**:
- Consistent baseline for admin workloads
- Preconfigured policies and resources

**Configuration**: Required — foundational pieces for other admin apps.

Login App (maia-core-loginapp)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Synchronizes the MAIA login application providing user-facing authentication UI integrated with Keycloak.

**Use Cases**:
- End-user login portal
- Integration with MAIA dashboards and services

**Benefits**:
- Unified entrypoint for MAIA users
- Works with Keycloak and ArgoCD-managed configs

**Configuration**: Recommended for user-facing access to MAIA services.

MAIA Dashboard (maia-dashboard)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Deploys the MAIA Dashboard application and supporting services for admin-facing UI and APIs (including database and secrets such as `dashboard_api_secret` and `mysql_dashboard_password` provided via the Admin Toolkit).

**Use Cases**:
- Central UI for administrators to monitor and manage MAIA resources
- Surfacing status of admin services (Harbor, Keycloak, Rancher)
- Entry point for admin workflows that rely on Keycloak authentication

**Benefits**:
- Consolidated admin experience
- Integrates with Keycloak/SSO and ArgoCD-managed configuration
- Uses GitOps to keep dashboard components in sync

**Configuration**: Recommended for operational visibility of MAIA Admin components.

MinIO Admin Tenant (maia-dashboard namespace)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Ensures the MinIO tenant pod is running, creates the `maia-envs` bucket, and applies an admin policy via `mc` commands.

**Use Cases**:
- Object storage for environment artifacts and configs
- Admin-level access for MAIA ops tasks

**Benefits**:
- S3-compatible storage scoped for admin workflows
- Automated bucket creation and policy setup

**Configuration**: Required when admin components rely on MinIO-backed storage.

5. Configure OIDC Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    ansible-playbook -i inventory playbooks/configure_oidc_authentication.yaml -e "config_folder=<CONFIG_FOLDER>"

This playbook configures OIDC-related settings for the MAIA environment, primarily by preparing Rancher (and optionally Harbor) using values from the cluster configuration.

**Note**: As with other playbooks, `config_folder` must point to the directory created by `MAIA_Configure_Installation.sh` that contains `env.json` and the cluster configuration files.

The `configure_oidc_authentication.yaml` playbook runs the `configure_oidc_authentication` role, which performs the following:

Rancher OIDC Preparation
^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Reads the cluster configuration, extracts the `domain` and `rancher_password`, logs into Rancher at `https://mgmt.domain`, obtains a token, and accepts the Rancher EULA. This is a prerequisite step before enabling full OIDC integration with Keycloak.

**Use Cases**:
- Initial Rancher bootstrap for MAIA clusters
- Preparing Rancher for later OIDC configuration and SSO

**Benefits**:
- Automates Rancher login and EULA acceptance
- Ensures Rancher is in a known good state before further configuration

**Configuration**: Controlled by `configure_rancher` (default `true`) in the role; when set to `false`, Rancher configuration is skipped.

Harbor OIDC Preparation
^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Optionally configures Harbor for OIDC authentication using the provided admin credentials and cluster configuration.

**Use Cases**:
- Preparing Harbor to use Keycloak/OIDC for authentication
- Aligning registry access control with the rest of the MAIA platform

**Benefits**:
- Centralized identity via OIDC for the registry
- Consistent access control model across MAIA components

**Configuration**: Controlled by `configure_harbor` (default `true`). Admin credentials are provided via `harbor_admin_user` and `harbor_admin_pass`.

6. Get Kubeconfig from Rancher Local
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    ansible-playbook -i inventory playbooks/get_kubeconfig_from_rancher_local.yaml -e "config_folder=<CONFIG_FOLDER>"

This playbook retrieves a kubeconfig for the local Rancher-managed cluster using the Rancher API and stores it in the MAIA configuration folder.

**Note**: `config_folder` must point to the directory created by `MAIA_Configure_Installation.sh` and contain `env.json` and the cluster configuration YAML (`{{ cluster_name }}.yaml`).

The `get_kubeconfig_from_rancher_local.yaml` playbook performs the following steps:

Obtain Rancher API Token
^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Reads the cluster configuration, extracts `domain` and `rancher_password`, and uses them to call the Rancher public login endpoint at `https://mgmt.domain` to obtain an authentication token. The token is stored in the cluster configuration file as `rancher_token`.

**Use Cases**:
- Authenticating to Rancher without manual UI interaction
- Automating API access for subsequent operations

**Benefits**:
- Eliminates manual login for CLI/API usage
- Provides a reusable token for further Rancher API calls within the play

Create Rancher API Key
^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Uses the login token to create a Rancher API key (`type: token`) and extracts the secret key from the response.

**Use Cases**:
- Issuing a dedicated API token for kubeconfig generation
- Enabling scripted Rancher API calls

**Benefits**:
- Scoped API access token managed by Rancher
- Clear separation between login credentials and API usage

Generate and Save Kubeconfig
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Calls the Rancher `generateKubeconfig` action on the `local` cluster using the API key, extracts the kubeconfig YAML from the response, and writes it to `{{ config_folder }}/local.yaml` (or the file specified by `kubeconfig_file`).

**Use Cases**:
- Producing a kubeconfig for local development or automation
- Feeding kubeconfig into subsequent MAIA tooling or playbooks

**Benefits**:
- Fully automated kubeconfig retrieval
- Ensures kubeconfig is stored alongside other MAIA configuration artifacts

Write Rancher Token to Cluster Config
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Writes the Rancher token to the cluster configuration file.

**Use Cases**:
- Providing a Rancher token for subsequent operations
- Ensuring the Rancher token is available for other playbooks

**Benefits**:
- Provides a reusable Rancher token for further Rancher API calls within the play
- Ensures the Rancher token is stored alongside other MAIA configuration artifacts

7. Configure MAIA Dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    ansible-playbook -i inventory playbooks/configure_maia_dashboard.yaml -e "config_folder=<CONFIG_FOLDER>"

This playbook configures the MAIA Dashboard by running the Admin Toolkit installer and synchronizing the dashboard ArgoCD application.

**Note**: `config_folder` must point to the directory created by `MAIA_Configure_Installation.sh` and contain `env.json` and the cluster configuration YAML (`{{ cluster_name }}.yaml`). The playbook requires various environment variables to be set in `env.json`, including `DEPLOY_KUBECONFIG`, `argocd_namespace`, `admin_group_ID`, `admin_project_chart`, `admin_project_repo`, `admin_project_version`, `keycloak_client_secret`, `minio_admin_password`, `minio_root_password`, `dashboard_api_secret`, `mysql_dashboard_password`, and `ARGOCD_PASSWORD`.

The `configure_maia_dashboard.yaml` playbook performs the following steps:

Run MAIA Admin Toolkit Installer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Executes `MAIA_install_admin_toolkit` with the cluster configuration and required environment variables to configure the MAIA Dashboard and related admin components. The installer reads the cluster configuration YAML and uses environment variables for secrets and configuration values.

**Use Cases**:
- Initial configuration of the MAIA Dashboard after admin layer installation
- Updating dashboard configuration with new settings or secrets
- Ensuring dashboard components are properly configured with Keycloak, MinIO, and database credentials

**Benefits**:
- Centralized dashboard configuration through the Admin Toolkit
- Ensures all required secrets and environment variables are properly set
- Configures dashboard integration with Keycloak, MinIO, and MySQL

Login to ArgoCD
^^^^^^^^^^^^^^^

**Description**: Logs into ArgoCD using the CLI, attempting first with `localhost:8080` and falling back to `argocd.<domain>` if the local connection fails. Uses the `ARGOCD_PASSWORD` from environment variables.

**Use Cases**:
- Authenticating to ArgoCD for application synchronization
- Enabling automated ArgoCD operations without manual login

**Benefits**:
- Automated ArgoCD authentication for subsequent operations
- Fallback mechanism ensures connection even if port forwarding is not active
- Enables scripted ArgoCD application management

Synchronize MAIA Dashboard Application
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Synchronizes the `maia-admin-maia-dashboard` ArgoCD application to ensure the dashboard deployment matches the desired state defined in Git. This step is conditional on `auto_sync` being enabled (default: `true`).

**Use Cases**:
- Ensuring dashboard is deployed and up-to-date with Git configuration
- Applying configuration changes from Git repositories
- Recovering from deployment drift or failures

**Benefits**:
- GitOps-based dashboard deployment management
- Ensures dashboard matches declared configuration
- Automatic synchronization from Git repositories

Restart Dashboard Deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Description**: Performs a rollout restart of the `maia-admin-maia-dashboard` deployment in the `maia-dashboard` namespace to apply configuration changes and ensure pods are running with the latest settings. This step is conditional on `auto_sync` being enabled (default: `true`).

**Use Cases**:
- Applying configuration changes that require pod restart
- Refreshing dashboard pods after secret or config updates
- Ensuring dashboard is running with latest configuration

**Benefits**:
- Ensures configuration changes are applied immediately
- Refreshes dashboard pods to pick up new environment variables or secrets
- Maintains dashboard availability during restart process