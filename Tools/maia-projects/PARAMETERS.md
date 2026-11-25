# MAIA Project Parameters

Generated from `Tools/maia-projects/lib/catalog.py` (`python Tools/maia-projects/maia_projects.py reference --markdown`). Do not edit by hand.

A project request is the JSON body of `POST /maia/user-management/project-chart/` (deploy) or `POST /maia/user-management/create-group/` (register only). See `templates/` for complete examples.

How `project_configuration` is applied: every top-level key is copied into the project form read by the chart generators; every `env` entry `KEY: value` is exported as the environment variable `KEY_<namespace>` and read back by the generators. Keys are case-sensitive and `env` values must be strings.

## Request fields

### Identity

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `namespace` | string | yes |  | Project ID. Becomes the Kubernetes namespace, the Keycloak group 'MAIA:&lt;namespace&gt;', the ArgoCD application prefix and the project subdomain. Lowercase alphanumerics and '-', must start/end alphanumeric, max 63 characters. |
| `email` | email | yes |  | Requesting admin / owner. Used as the username in the kubeconfig the dashboard generates for the deployment. Created if missing and added to the project members (both deploy and register). |
| `description` | string |  |  | Free-text project description (max 5000 characters). |
| `date` | date (YYYY-MM-DD) | yes |  | Project end / expiry date. |

### Members

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `users` | list[email] |  |  | Project members. Missing users are created in the dashboard and Keycloak (username from email_to_username_map, otherwise the email) and added to the project group. The supervisor is prepended and the owner email appended; the first member (the supervisor) becomes the Kubeflow profile owner. |
| `supervisor` | email |  |  | Project supervisor / PI. Created if missing and added as the first member. Defaults to the owner email on deploy. |
| `email_to_username_map` | dict[email, string] |  |  | Username to use when a member has to be created in Keycloak. Defaults to the email. |

### Placement

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `cluster` | string | yes |  | Target cluster: the 'cluster_name' of a cluster config file (&lt;CLUSTER_CONFIG_PATH&gt;/&lt;cluster&gt;.yaml) known to the dashboard. |
| `project_tier` | string | yes |  | 'Base' deploys a minimal stack (namespace, JupyterHub/Kubeflow, FileBrowser). Any other value (use 'Pro') adds MinIO, MySQL, MLflow and Orthanc and switches to the Pro workspace image. Values: `Base`, `Pro`. |

### Resources

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `gpu` | string | yes |  | GPU type label: 'NO' or a GPU name from the cluster's gpu_specs (the dashboard's GPU_SPECS). Only a label: it is not converted to a GPU count. To give each workspace GPUs set project_configuration.gpu_request. |
| `memory_limit` | quantity | yes |  | Per-user workspace memory limit. 'Gi' and ' Gi' are accepted (converted to 'G'). |
| `memory_request` | quantity | yes |  | Per-user workspace memory guarantee. |
| `cpu_limit` | cpu | yes |  | Per-user workspace CPU limit (cores or millicores, e.g. '2' or '500m'). |
| `cpu_request` | cpu | yes |  | Per-user workspace CPU guarantee. |

### Deployment

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `auto_deploy` | boolean |  | `False` | true: create the namespace (a Kubeflow profile when DEPLOY_KUBEFLOW), RBAC and the ArgoCD applications. false: register the project and users and only return the rendered values. |
| `auto_deploy_apps` | list[string] |  |  | ArgoCD applications to sync right after deployment (application '&lt;namespace&gt;-&lt;app&gt;'). Others are created but left unsynced (manual sync policy). Only used with auto_deploy. Values: `namespace`, `jupyterhub`, `kubeflow`, `filebrowser`, `mysql`, `mlflow`, `orthanc`, `ehrbase`, `nvflare-dashboard`. |
| `project_configuration` | dict |  |  | Per-project overrides: see the project_configuration and env sections. |
| `env_file` | file (multipart only) |  |  | Environment file uploaded to MinIO and mounted in the workspaces. Only via multipart form upload, not in a JSON request. |

### `auto_deploy_apps` values

| App | Meaning |
|-----|---------|
| `namespace` | Namespace chart: quotas, SSH/LoadBalancer services, MinIO tenant (Pro), registry secret. |
| `jupyterhub` | JupyterHub (only when DEPLOY_KUBEFLOW is not 'True'). |
| `kubeflow` | Kubeflow profile + notebooks (when env.DEPLOY_KUBEFLOW == 'True'). |
| `filebrowser` | FileBrowser. |
| `mysql` | MySQL for MLflow (Pro tier). |
| `mlflow` | MLflow tracking server (Pro tier). |
| `orthanc` | Orthanc PACS + its MySQL (Pro tier). |
| `ehrbase` | EHRbase openEHR server (when env.DEPLOY_EHRBASE == 'True'). |
| `nvflare-dashboard` | NVFlare dashboard (when env.DEPLOY_NVFLARE_DASHBOARD == 'True'). |

## `project_configuration` keys

### Resources

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `gpu_request` | string|int |  |  | GPUs per workspace (nvidia.com/gpu). Defaults to int(gpu), i.e. 0 for 'NO' or a GPU name. |
| `node_selector` | dict |  |  | Node selector for the JupyterHub user pods. Only the first key/value pair is used. |

### JupyterHub

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `admins` | list[email] |  |  | JupyterHub admin users. |
| `password` | string |  |  | Default password set in every workspace (PASSWD and SELKIES_BASIC_AUTH_PASSWORD). *(secret)* |
| `allow_ssh_password_authentication` | string |  |  | Allow SSH password authentication into the workspaces (ALLOW_PASSWORD_AUTHENTICATION). Values: `True`, `False`. |
| `active_server_limit` | int |  | `1` | JupyterHub activeServerLimit. |
| `concurrent_spawn_limit` | int |  | `1` | JupyterHub concurrentSpawnLimit. |
| `shared_server_user` | string |  | `user@maia.se` | User whose server is shared with the project. |
| `jupyterhub_extraEnv` | dict[string, string] |  |  | Extra environment variables for every workspace. |

### Networking

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `ip_whitelist` | list[string] |  |  | Source IPs allowed on LoadBalancer services (SSH, Orthanc) and in the Kubeflow AuthorizationPolicies. |

### Credentials

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `mlflow_user` | string |  |  | MLflow / FileBrowser user. Generated when unset; existing values are kept on redeploy. *(secret)* |
| `mlflow_password` | string |  |  | MLflow / FileBrowser password. *(secret)* |
| `minio_user` | string |  |  | MinIO access key (Pro tier). Default 'admin'. *(secret)* |
| `minio_password` | string |  |  | MinIO secret key (Pro tier). Generated when unset. *(secret)* |
| `minio_console_access_key` | string |  |  | MinIO console access key. *(secret)* |
| `minio_console_secret_key` | string |  |  | MinIO console secret key. *(secret)* |
| `mysql_user` | string |  |  | MySQL user for the MLflow database. *(secret)* |
| `mysql_password` | string |  |  | MySQL password for MLflow and for the Orthanc database (user 'maia-admin'). *(secret)* |

### Orthanc

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `ae_title` | string |  |  | Orthanc DICOM AE title. Defaults to the namespace. |
| `monai_label_models` | dict |  |  | MONAI Label models made available in Orthanc. |

### NVFlare

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `nvflare_dashboard_admin_username` | string |  |  | NVFlare dashboard admin user (with env.DEPLOY_NVFLARE_DASHBOARD). Generated when unset; an existing deployment's value wins. Top-level key, not under env. *(secret)* |
| `nvflare_dashboard_admin_password` | string |  |  | NVFlare dashboard admin password. Generated when unset. Top-level key, not under env. *(secret)* |

### General

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `env` | dict[string, string] |  |  | Per-project environment overrides: each KEY is exported as &lt;KEY&gt;_&lt;namespace&gt; (see env section). Values should be strings; booleans and numbers are converted ('True'/'False'). |

### Advanced overrides

| Key | Effect |
|-----|--------|
| `group_subdomain` | Subdomain used for the project URLs (default: namespace). |
| `resources_limits` | {'memory': [request, limit], 'cpu': [request, limit]} (default: from the request). |
| `minio_env_name` | MinIO env file name (default: from env_file). |
| `users` | Overrides the member list passed to the charts. |

### Not settable

| Key | Why |
|-----|-----|
| `extra_configs` | Recomputed during deployment; use env.enable_cifs. |
| `ssh_users` | Computed from the namespace values. |
| `minio_access_key` | Computed from minio_user. |
| `minio_secret_key` | Computed from minio_password. |

## `project_configuration.env` keys

### Optional apps

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `DEPLOY_KUBEFLOW` | string |  |  | Deploy the project as a Kubeflow profile with Kubeflow notebooks instead of JupyterHub. Values: `True`. |
| `DEPLOY_EHRBASE` | string |  |  | Deploy EHRbase (openEHR). Values: `True`. |
| `DEPLOY_NVFLARE_DASHBOARD` | string |  |  | Deploy the NVFlare dashboard (also set nvflare_dashboard_admin_* at top level). Values: `True`. |

### Storage

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `enable_cifs` | string |  |  | Create the CIFS secret and mount CIFS volumes in JupyterHub and FileBrowser. Values: `True`. Enabled by 'True', 'true', '1', 'yes' or 'on'; anything else disables it. |
| `MINIO_EXTERNAL_CA` | string |  |  | Copy an external CA certificate into the namespace for MinIO (secret 'kubernetes-ca-minio'). Values: `True`. |
| `MINIO_EXTERNAL_CA_SECRET_NAME` | string |  | `kubernetes-ca` | Source secret of the external CA. |
| `MINIO_EXTERNAL_CA_NAMESPACE` | string |  | `cert-manager` | Namespace of the external CA secret. |

### Images

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `maia_workspace_image` | string |  |  | Workspace image (Base tier). |
| `maia_workspace_version` | string |  |  | Workspace image tag (Base tier). |
| `maia_workspace_pro_image` | string |  |  | Workspace image (Pro tier; overrides the default Pro workspace image). |
| `maia_workspace_pro_version` | string |  |  | Workspace image tag (Pro tier). |
| `hub_image` | string |  |  | JupyterHub hub image. Requires hub_tag as well (KeyError otherwise). |
| `hub_tag` | string |  |  | JupyterHub hub image tag. |
| `JHUB_IMAGE` | string |  |  | Alternative hub image (tag '1.0', pull secret derived from the image name). |
| `maia_monai_toolkit_image` | string |  |  | MONAI toolkit workspace profile image. |
| `maia_orthanc_image` | string |  |  | Orthanc image. |
| `maia_orthanc_version` | string |  |  | Orthanc image tag. |

### Networking

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `base_url` | string |  |  | JupyterHub base URL. |

### Registry

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `MAIA_PRIVATE_REGISTRY` | string |  |  | Private registry / chart repository used for this project's images and charts. |
| `imagePullSecrets` | string |  |  | Name of a docker registry secret to create in the namespace, from registry_server / registry_username / registry_password (per project, falling back to the dashboard's global values). |
| `registry_server` | string |  |  | Registry server for imagePullSecrets. |
| `registry_username` | string |  |  | Registry user for imagePullSecrets. |
| `registry_password` | string |  |  | Registry password for imagePullSecrets. *(secret)* |
| `JSON_KEY_PATH` | string |  |  | Path (on the dashboard) of registry credentials used to pull OCI charts. |

### App resources

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `ORTHANC_CPU_REQUEST` | string |  | `4000m` | Orthanc cpu request (Pro tier). |
| `ORTHANC_CPU_LIMIT` | string |  | `4000m` | Orthanc cpu limit (Pro tier). |
| `ORTHANC_MEMORY_REQUEST` | string |  | `4Gi` | Orthanc memory request (Pro tier). |
| `ORTHANC_MEMORY_LIMIT` | string |  | `4Gi` | Orthanc memory limit (Pro tier). |
| `ORTHANC_MYSQL_CPU_REQUEST` | string |  | `500m` | Orthanc MySQL cpu request (Pro tier). |
| `ORTHANC_MYSQL_CPU_LIMIT` | string |  | `500m` | Orthanc MySQL cpu limit (Pro tier). |
| `ORTHANC_MYSQL_MEMORY_REQUEST` | string |  | `2Gi` | Orthanc MySQL memory request (Pro tier). |
| `ORTHANC_MYSQL_MEMORY_LIMIT` | string |  | `2Gi` | Orthanc MySQL memory limit (Pro tier). |
| `MLFLOW_CPU_REQUEST` | string |  | `500m` | MLflow cpu request (Pro tier). |
| `MLFLOW_CPU_LIMIT` | string |  | `500m` | MLflow cpu limit (Pro tier). |
| `MLFLOW_MEMORY_REQUEST` | string |  | `2Gi` | MLflow memory request (Pro tier). |
| `MLFLOW_MEMORY_LIMIT` | string |  | `2Gi` | MLflow memory limit (Pro tier). |
| `MYSQL_CPU_REQUEST` | string |  | `500m` | MLflow MySQL cpu request (Pro tier). |
| `MYSQL_CPU_LIMIT` | string |  | `500m` | MLflow MySQL cpu limit (Pro tier). |
| `MYSQL_MEMORY_REQUEST` | string |  | `2Gi` | MLflow MySQL memory request (Pro tier). |
| `MYSQL_MEMORY_LIMIT` | string |  | `2Gi` | MLflow MySQL memory limit (Pro tier). |

### Orthanc

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `MONAI_LABEL_AUTH_USERNAME` | string |  |  | MONAI Label basic-auth user for Orthanc (set together with the password). *(secret)* |
| `MONAI_LABEL_AUTH_PASSWORD` | string |  |  | MONAI Label basic-auth password for Orthanc. *(secret)* |

### EHRbase

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `EHRBASE_DB_USER` | string |  | `ehrbase_restricted` | EHRbase DB user. |
| `EHRBASE_DB_USER_ADMIN` | string |  | `ehrbase` | EHRbase DB admin user. |
| `EHRBASE_DB_PASSWORD` | string |  |  | EHRbase DB password (generated when unset; existing secret wins). *(secret)* |
| `EHRBASE_DB_PASSWORD_ADMIN` | string |  |  | EHRbase DB admin password. *(secret)* |
| `EHRBASE_SECURITY_AUTHUSER` | string |  |  | EHRbase basic-auth user. |
| `EHRBASE_SECURITY_AUTHPASSWORD` | string |  |  | EHRbase basic-auth password. *(secret)* |
| `EHRBASE_SECURITY_AUTHADMINUSER` | string |  |  | EHRbase basic-auth admin user. |
| `EHRBASE_SECURITY_AUTHADMINPASSWORD` | string |  |  | EHRbase basic-auth admin password. *(secret)* |

### Keys with no per-project effect

| Key | Why |
|-----|-----|
| `MAIA_LAB_PRO_IMAGE_VERSION` | Read only as a global dashboard variable (MAIA/versions.py); per project use maia_workspace_pro_version / maia_workspace_pro_image instead. |
| `nvflare_dashboard_admin_username` | Must be a top-level project_configuration key, not under env. |
| `nvflare_dashboard_admin_password` | Must be a top-level project_configuration key, not under env. |

## Conventions

- **disabled_keys**: Append ':&lt;anything&gt;' to a key name (e.g. 'DEPLOY_KUBEFLOW:NO') to keep it in the file but disable it: the dashboard ignores unknown top-level keys and the env reader looks up the exact name.
- **upsert**: Deploying an existing namespace updates its configuration (create-or-update).
- **namespace_file**: The same keys can live in &lt;CLUSTER_CONFIG_PATH&gt;/&lt;namespace&gt;.yaml on the dashboard; project_configuration is applied afterwards and wins.

