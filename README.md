# MAIA Toolkit

[![Article-NPJ Artificial Intelligence](https://img.shields.io/badge/NPJ_Artificial_Intelligence-black)](https://www.nature.com/articles/s44387-025-00042-6)
[![arXiv](https://img.shields.io/badge/arXiv-2507.19489-b31b1b.svg)](https://arxiv.org/abs/2507.19489)

[![Build](https://github.com/minnelab/MAIA/actions/workflows/build.yaml/badge.svg)](https://github.com/minnelab/MAIA/actions/workflows/build.yaml)

[![Documentation Status](https://readthedocs.org/projects/maia-toolkit/badge/?version=latest)](https://maia-toolkit.readthedocs.io/en/latest/?badge=latest)
![Version](https://img.shields.io/badge/MAIA-v2.0.0-blue)
[![License](https://img.shields.io/badge/license-GPL%203.0-green.svg)](https://opensource.org/licenses/GPL-3.0)
![Python](https://img.shields.io/badge/python-3.8+-orange)


![GitHub Release Date - Published_At](https://img.shields.io/github/release-date/minnelab/MAIA?logo=github)
![GitHub contributors](https://img.shields.io/github/contributors/minnelab/MAIA?logo=github)
![GitHub top language](https://img.shields.io/github/languages/top/minnelab/MAIA?logo=github)
![GitHub language count](https://img.shields.io/github/languages/count/minnelab/MAIA?logo=github)
![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/minnelab/MAIA/publish_release.yaml?logo=github)
![GitHub all releases](https://img.shields.io/github/downloads/minnelab/MAIA/total?logo=github)
![PyPI - Downloads](https://img.shields.io/pypi/dm/maia-toolkit?logo=pypi)
![GitHub](https://img.shields.io/github/license/minnelab/MAIA?logo=github)
![PyPI - License](https://img.shields.io/pypi/l/maia-toolkit?logo=pypi)


![GitHub repo size](https://img.shields.io/github/repo-size/minnelab/MAIA?logo=github)
![GitHub release (with filter)](https://img.shields.io/github/v/release/minnelab/MAIA?logo=github)
![PyPI](https://img.shields.io/pypi/v/maia-toolkit?logo=pypi)

<p align="center">
  <img src="https://raw.githubusercontent.com/minnelab/maia/master/MAIA.png" width="80%" alt='MAIA'>
</p>

MAIA Toolkit is the main tool for deploying and managing MAIA, a platform for collaborative research in medical AI. 

MAIA is a Kubernetes-based platform designed to facilitate collaborative medical AI research. It supports the entire AI development lifecycle, including data preparation, model training, active learning, deployment, and evaluation. MAIA offers a secure and scalable environment with tools and services that are easy to use and flexible, enabling deployment and management of AI models across various environments, from local workstations to cloud-based clusters. Developed by the Biomedical Imaging Division at KTH Royal Institute of Technology in Stockholm, Sweden, MAIA aims to streamline the development and deployment of AI models in medical research.

MAIA serves two main purposes:

1. **Clinical Research Environment**: MAIA provides a standardized and scalable platform for developing, training, and deploying AI models in medical research. It offers a secure and collaborative environment for researchers to work on AI projects, share data, and collaborate on research projects. Furthermore, MAIA specifically focuses on the final model deployment, enabling researchers to deploy their models in real-world clinical settings.

2. **Educational Environment**: MAIA provides a platform for teaching and learning medical AI. It offers a hands-on learning experience for students and researchers to develop, train, and deploy AI models in a real-world setting.

The toolkit provides a set of scripts and tools to deploy and manage the MAIA platform as a Kubernetes cluster.

## Citation

If you use the MAIA platform in your work, please cite the following [paper](https://www.nature.com/articles/s44387-025-00042-6):

```
Bendazzoli, S., Persson, S., Astaraki, M. et al. MAIA: a collaborative medical AI platform for integrated healthcare innovation. npj Artif. Intell. 1, 45 (2025). https://doi.org/10.1038/s44387-025-00042-6
```

## Quickstart: Install MAIA in 10 Minutes

MAIA ships with a **one-command installer** that sets up everything you need: Kubernetes, its configuration, the MAIA Core and Admin layers, and the MAIA Dashboard so you can start building projects immediately.

The installer is powered by the **`MAIA.Installation` Ansible collection**, which provides roles and playbooks to install and configure the MAIA platform on a Kubernetes cluster.

For more details, please refer to the [MAIA.Installation]() documentation.

To run the installer, you must prepare a **configuration folder** containing:

- **Inventory**: an Ansible inventory file (or folder) defining your hosts and their roles.
- **Configuration file**: a `config.yaml` file describing the installation steps and options.

### Minimal Installation

Below is a minimal example that installs a full MAIA stack on a fresh **Ubuntu 24.04** server named `maia-node-0`.

#### Example `config.yaml`

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
  nfs: false
  cifs: false

configure_hosts:
  auto_sync: true

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
  kubeconfig_file: "local-from-rancher.yaml"

configure_maia_dashboard:
  auto_sync: true

env:
  MAIA_PRIVATE_REGISTRY: ""
  CLUSTER_DOMAIN: "example.maia.com"
  CLUSTER_NAME: "maia-cluster"
  INGRESS_RESOLVER_EMAIL: ""
  K8S_DISTRIBUTION: "microk8s"

cluster_config_extra_env:
  selfsigned: true
  shared_storage_class: microk8s-hostpath
```

#### Example `inventory`

```ini
[control-plane]
maia-dev-node-0 ansible_host=127.0.0.1 ansible_connection=local ansible_user=ansible-user ansible_become_password=ansible ansible_become=true ansible_become_method=sudo
```

#### Run the installer

```bash
MAIA_Install --config-folder <CONFIG_FOLDER>
```

Replace `<CONFIG_FOLDER>` with the path to the folder containing your `config.yaml` and `inventory`.

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

## MAIA Architecture

MAIA is built on top of Kubernetes, a popular open-source container orchestration platform. The platform is designed to be modular and extensible, allowing users to customize and extend its functionality to suit their needs. 
MAIA is composed of three different layers, each serving a specific purpose:

### MAIA Core:

<p align="center">
  <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/image/README/MAIA_Core.png" width="70%" alt='MAIA'>
</p>

The `MAIA Core` layer includes the core components that provide the basic functionality of the platform.

The core components of MAIA include:
- **ArgoCD**: A GitOps continuous delivery tool for Kubernetes that allows users to deploy applications and manage the cluster's configuration using Git repositories.
- **Traefik**: A reverse proxy and load balancer that allows users to access the services deployed on the Kubernetes cluster.
- **Cert-Manager**: A Kubernetes add-on that automates the management and issuance of TLS certificates.
- **MetalLB**: A load balancer implementation for bare metal Kubernetes clusters.
- **Kubernetes Dashboard**: A web-based UI for managing the Kubernetes cluster, including viewing the cluster's status, deploying applications, and managing the cluster's configuration.
- **Rancher**: A Kubernetes management platform that allows users to manage the Kubernetes cluster, deploy applications, and monitor the cluster's status.
- **Grafana**: A monitoring and observability platform that allows users to monitor the cluster's status, including the CPU, Memory, and GPU usage.
- **Loki**: A log aggregation system that allows users to collect, store, and query logs from the Kubernetes cluster.
- **Prometheus**: A monitoring and alerting toolkit that allows users to monitor the cluster's status and set up alerts based on predefined rules.
- **Tempo**: A distributed tracing system that allows users to trace requests through the Kubernetes cluster.
- **NVIDIA GPU Operator**: A Kubernetes operator that allows users to deploy NVIDIA GPU drivers and device plugins on the Kubernetes cluster.


### MAIA Admin:


<p align="center">
  <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/image/README/MAIA-Admin.png" width="70%" alt='MAIA'>
</p>


The `MAIA Admin` layer includes the administrative components that provide the administrative functionality of the MAIA platform.

The admin components of MAIA include:

- **MinIO Operator**: A Kubernetes operator that allows users to deploy MinIO, a high-performance object storage server, on the Kubernetes cluster.
- **Login App**: A Django app that allows users to log in to the MAIA API using OpenID Connect authentication.
- **Keycloak**: An open-source identity and access management tool that allows users to manage the users and roles associated with the MAIA API.
- **Harbor**: A container image registry that allows users to store and distribute container images.
- **MAIA Dashboard**: A web-based dashboard that allows users to register projects, request resources, and access the different MAIA services deployed on the Kubernetes cluster.

### MAIA Namespaces:

The `MAIA Namespaces` layer is designed to be project-specific, allowing users to create isolated environments for their projects.
This layers is designed to provide the external interfaces for the users to interact with the platform, making the MAIA platform remotely accessible to the users.

<p align="center">
  <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/image/README/MAIA_Workspace.png" width="70%" alt='MAIA'>
</p>



The MAIA platform provides a range of applications and tools that you can use to develop your projects, grouped into a *MAIA Workspace*.

#### Workspace Credentials Configuration

The MAIA Workspace supports customizable user credentials. You can set your preferred username and password by creating a `.env` file in your home directory with `MAIA_USERNAME` and `MAIA_PASSWORD` variables. For detailed information, see the [Workspace Credentials Documentation](docker/MAIA-Workspace/WORKSPACE_CREDENTIALS.md).

The MAIA Workspace includes:
- **Jupyter Notebook**: A web-based interactive development environment for Python, R, and other programming languages.
- **Remote Desktop**: A remote desktop to access your workspace.
- **SSH**: Secure Shell access to your workspace.
- **Visual Studio Code**: A powerful code editor with support for debugging, syntax highlighting, and more.
- **RStudio**: An integrated development environment for R.
- **3D Slicer**: A medical image analysis software for visualization and analysis of medical images.
- **FreeSurfer**: A software suite for the analysis and visualization of structural and functional neuroimaging data.
- **QuPath**: A software for digital pathology image analysis.
- **ITK-SNAP**: A software for segmentation of anatomical structures in medical images.
- **MatLab**: A high-level programming language and interactive environment for numerical computation, visualization, and programming.
- **Anaconda**: A distribution of Python and R programming languages for scientific computing.

Additionally, the MAIA platform provides access to a range of cloud services and tools, including:

- **MinIO**: An object storage server for storing large amounts of data.
- **MLFlow**: An open-source platform for managing the end-to-end machine learning lifecycle.
- **Orthanc**: An open-source DICOM server for medical imaging.
- **OHIF**: An open-source platform for viewing and annotating medical images.
- **XNAT [Experimental]** : An open-source platform for managing and sharing medical imaging data.
- **Label Studio**: An open-source platform for data labeling and annotation.
- **KubeFlow**: An open-source platform for deploying machine learning workflows on Kubernetes.
- **MONAI Deploy [Experimental]**: An open-source platform for deploying deep learning models for medical imaging in clinical production settings.

<p align="center">
  <img src="https://raw.githubusercontent.com/minnelab/maia/master/Workspace.png" width="70%" alt='MAIA'>
</p>




