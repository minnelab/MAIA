# Deploy an Application in MAIA Namespace

The script to deploy custom applications uses Helm charts to deploy the applications, and it is available as a Helm chart: [MAIA](https://github.com/minnelab/MAIA).

With the **MAIA** chart it is possible to deploy any *Docker Image* as a Pod, expose the required ports as services, mount persistent volumes on the specified locations and optionally create Ingress resources to expose the application to the external traffic using the HTTPS protocol.

To add the chart to Helm, run:

```
helm repo add maia https://minnelab.github.io/MAIA/
helm repo update
```

## Custom Helm values

A number of custom parameters can be specified for the Helm chart, including the Docker image to deploy, the port to expose, etc.

The custom configuration is set in a JSON configuration file, following the conventions described below.

## General Configuration

### Namespace [Required]

Specify the Cluster Namespace where to deploy the resources

```json
{
    "namespace": "NAMESPACE_NAME"
}
```

### Chart Name [Required]

Specify the Helm Chart Release name

```json
{
    "chart_name": "Helm_Chart_name"
}
```

### Docker image [Required]

To specify the Docker image to deploy

```json
{
    "docker_image": "DOCKER_IMAGE"
}
```

### Requested Resources

To request resources (RAM, CPU and optionally GPU).

```json
{
    "memory_request": "REQUESTED_RAM_SIZE",
    "cpu_request": "REQUESTED_CPUs"
}
```

Optionally, to request GPU usage:

```json
{
    "gpu_request": "NUMBER_OF_GPUs"
}
```

### Allocation Time [Required]

Since each environment is deployed as a Job with a fixed allocation time, the user can specify the requested allocation time (default in days) in the following field:

```json
{
    "allocationTime": "2"
}
```

### Services

To specify which ports (and corresponding services) can be reached from outside the pod.

```json
{
    "ports": {
        "SERVICE_NAME_1": [
            "PORT_NUMBER"
        ],
        "SERVICE_NAME_2": [
            "PORT_NUMBER"
        ]
    }
}
```

The default *Service Type* is **ClusterIP**. To expose a service as a type **NodePort**:

```json
{
    "service_type": "NodePort",
    "ports": {
        "SERVICE_NAME_1": [
            "PORT_NUMBER",
            "NODE_PORT_NUMBER"
        ],
        "SERVICE_NAME_2": [
            "PORT_NUMBER",
            "NODE_PORT_NUMBER"
        ]
    }
}
```

### Persistent Volumes

Two different types of persistent volumes are available: **hostPath** (local folder) and **nfs** (shared nfs folder). For each of these types, it is possible to request a Persistent Volume via a Persistent Volume Claim.

The *"readOnly"* options can be added to specify the mounted folder as read-only.

Request PVC:

```json
{
    "persistent_volume": [
        {
            "mountPath": "/mount/path_1",
            "size": "VOLUME_SIZE",
            "access_mode": "ACCESS_TYPE",
            "pvc_type": "STORAGE_CLASS"
        },
        {
            "mountPath": "/mount/path_2",
            "size": "VOLUME_SIZE",
            "access_mode": "ACCESS_TYPE",
            "pvc_type": "STORAGE_CLASS"
        }
    ]
}
```

**"STORAGE_CLASS"** can be any of the storage classes available on the cluster:

```
kubectl get sc
```

### Existing Persistent Volumes

Previously created pv can be mounted into multiple pods (ONLY if the *access mode* was previously set to **ReadWriteMany**)

```json
{
    "existing_persistent_volume": [
        {
            "name": "EXISTING_PVC_NAME",
            "mountPath": "/mount/path"
        }
    ]
}
```

### Mounted files

Single files can be mounted inside the Pod. First, a ConfigMap including the file is created, and then it is mounted into the Pod.

```json
{
    "mount_files": {
        "file_name": [
            "/local/file/path",
            "/file/mount/path"
        ]
    }
}
```

### Node Selection

To optionally select which node in the cluster to use for deploying the application.

```json
{
    "node_selector": "NODE_NAME"
}
```

### GPU Selection

To optionally select which available GPUs in the cluster to request. `product` attribute can be specified. Example: `product: "RTX-2070-Super"`

```json
{
    "gpu_selector": {
        "product": "GPU_TYPE"
    }
}
```

### Ingress

Used to create an Ingress resources to access the application at the specified port by using an HTTPS address. Two types of Ingress are currently supported: **NGINX** and **TRAEFIK**.

IMPORTANT! The specified DNS needs to be active and connected to the cluster DNS (**".maia.cloud.cbh.kth.se"**)

IMPORTANT! When working with the **TRAEFIK** Ingress, the *traefik_middleware* and *traefik_resolver* should be explicitly specified, since only oauth-based authenticated users can be authorized through the ingress. Contact the MAIA admin to retrieve this information.

IMPORTANT! When working with the **NGINX** Ingress, the *oauth_url* and *nginx_issuer* should be explicitly specified, since only oauth-based authenticated users can be authorized through the ingress. Contact the MAIA admin to retrieve this information.

```json
{
    "ingress": {
        "host": "SUBDOMAIN.maia.cloud.cbh.kth.se",
        "port": "SERVICE_PORT",
        "path": "/<PATH>",
        "oauth_url": "SUBDOMAIN.maia.cloud.cbh.kth.se",
        "nginx_issuer": "<NGINX_ISSUER_NAME>"
    }
}
```

```json
{
    "ingress": {
        "host": "SUBDOMAIN.maia.cloud.cbh.kth.se",
        "port": "SERVICE_PORT",
        "path": "/<PATH>",
        "traefik_middleware": "<MIDDLEWARE_NAME>",
        "traefik_resolver": "<TRAEFIK_RESOLVER_NAME>"
    }
}
```

### Environment variables

To add environment variables, used during the creation and deployment of the pod (i.e., environment variables to specify for the Docker Image).

```json
{
    "env_variables": {
        "KEY_1": "VAL_1",
        "KEY_2": "VAL_2"
    }
}
```

### Deployment

By default, the deployment is done as a Job. To deploy as a Deployment, the following field should be added:

```json
{
    "deployment": "true"
}
```

### Command

To specify a custom command to run inside the container:

```json
{
    "command": [
        "command",
        "arg1",
        "arg2"
    ]
}
```

### Image Pull Secret

If the Docker image is stored in a private repository, the user can specify the secret to use to pull the image.

```json
{
    "image_pull_secret": "SECRET NAME"
}
```

### User info

When deploying MAIA-based applications, it is possible to create single/multiple user account in the environment. For each of the users, *username*, *password*, and, optionally, an *ssh public key* are required. This information is stored inside Secrets:

```
USER_1_SECRET:
        user: USER_1
        password: pw
        ssh_publickey [Optional]: "ssh-rsa ..." 
```

To provide the user information to the Pod:

```json
{
    "user_secret": [
        "user-1-secret",
        "user-2-secret"
    ],
    "user_secret_params": [
        "user",
        "password",
        "ssh_publickey"
    ]
}
```

## Configuration File Example

```json
{
    "namespace": "demo",
    "chart_name": "jupyterlab-1-v1",
    "docker_image": "jupyter/scipy-notebook",
    "tag": "latest",
    "memory_request": "4Gi",
    "allocationTime": "2",
    "cpu_request": "5000m",
    "ports": {
        "jupyter": [
            8888
        ]
    },
    "persistent_volume": [
        {
            "mountPath": "/home/jovyan",
            "size": "100Gi",
            "access_mode": "ReadWriteOnce",
            "pvc_type": "microk8s-hostpath"
        }
    ]
}
```

## Tools

Install the **MAIA** package running:

```
pip install maia-tookit
```

Requirements:

```
kubectl  # Kubernetes CLI
helm     # Kubernetes Package Manager
```

## Deploy Charts

To deploy a Hive Chart, first create a config file according to the specific requirements (as described [above](#custom-helm-values)).

After creating the config file, run:

```shell
MAIA_deploy_helm_chart --config-file <PATH/TO/CONFIG/FILE>
```
