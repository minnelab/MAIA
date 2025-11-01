# MAIA Dashboard Environment Variables Guide

This guide provides comprehensive documentation for all environment variables used by the MAIA Dashboard and its integration with the MAIA package. Variables are organized by functional category for easy reference.

## Table of Contents
1. [Core Configuration](#core-configuration)
2. [Authentication & Authorization (OIDC/OAuth)](#authentication--authorization-oidcoauth)
3. [Database Configuration](#database-configuration)
4. [MinIO Object Storage](#minio-object-storage)
5. [ArgoCD Deployment](#argocd-deployment)
6. [Notifications & Communication](#notifications--communication)
7. [AI & Chatbot Integration](#ai--chatbot-integration)
8. [Kubernetes & Cluster Configuration](#kubernetes--cluster-configuration)
9. [MAIA Package Integration Variables](#maia-package-integration-variables)
10. [Docker Registry & Images](#docker-registry--images)
11. [Advanced Configuration](#advanced-configuration)

---

## Core Configuration

### DEBUG
- **Type**: Boolean
- **Default**: `True` (in environ.Env), `False` (recommended for production)
- **Usage**: Controls Django debug mode and configuration loading location
- **Details**: 
  - When `True`: Loads configuration from `<BASE_DIR>/config/`
  - When `False`: Loads configuration from `/mnt/dashboard-config/`
  - Affects error reporting, static file handling, and security settings
- **Location**: `dashboard/core/settings.py`

### SECRET_KEY
- **Type**: String
- **Default**: `S#perS3crEt_007`
- **Usage**: Django secret key for cryptographic signing
- **Details**: 
  - **IMPORTANT**: Must be changed in production for security
  - Used for session management, CSRF protection, and password reset tokens
  - Should be a long, random string
- **Location**: `dashboard/core/settings.py`

### SERVER
- **Type**: String (URL/hostname)
- **Default**: `localhost` or empty string
- **Usage**: Public FQDN (Fully Qualified Domain Name) for generating full URLs
- **Details**:
  - Used in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
  - Required for proper URL generation in production
  - Example: `maia.example.com`
- **Location**: `dashboard/core/settings.py`

### ASSETS_ROOT
- **Type**: String (file path)
- **Default**: `/maia/static/assets`
- **Usage**: Root directory for static asset files
- **Details**: Path where static assets (CSS, JS, images) are served from
- **Location**: `dashboard/core/settings.py`

### MAX_MEMORY
- **Type**: Integer (power of 2)
- **Default**: `7` (represents 2^7 = 128GB)
- **Usage**: Maximum memory allocation for GPU booking
- **Details**: 
  - Value represents the power of 2 (e.g., 7 = 128GB, 6 = 64GB, 8 = 256GB)
  - Used in GPU scheduling and resource allocation
- **Location**: `dashboard/core/settings.py`

### MAX_CPU
- **Type**: Integer (power of 2)
- **Default**: `5` (represents 2^5 = 32 CPUs)
- **Usage**: Maximum CPU allocation for GPU booking
- **Details**: 
  - Value represents the power of 2 (e.g., 5 = 32 CPUs, 4 = 16 CPUs)
  - Used in GPU scheduling and resource allocation
- **Location**: `dashboard/core/settings.py`

---

## Authentication & Authorization (OIDC/OAuth)

### OIDC_RP_CLIENT_ID
- **Type**: String
- **Default**: `None`
- **Required**: Yes (for OIDC authentication)
- **Usage**: OpenID Connect Relying Party client ID
- **Details**: Client ID registered with your OIDC provider (e.g., Keycloak)
- **Location**: `dashboard/core/settings.py`

### OIDC_RP_CLIENT_SECRET
- **Type**: String
- **Default**: `None`
- **Required**: Yes (for OIDC authentication)
- **Usage**: OpenID Connect Relying Party client secret
- **Details**: Client secret from your OIDC provider
- **Location**: `dashboard/core/settings.py`

### OIDC_USERNAME
- **Type**: String
- **Default**: `None`
- **Usage**: OIDC username claim field
- **Details**: Specifies which claim to use as the username
- **Location**: `dashboard/core/settings.py`

### OIDC_ISSUER_URL
- **Type**: String (URL)
- **Default**: `None`
- **Required**: Yes (for OIDC authentication)
- **Usage**: OIDC issuer URL
- **Details**: 
  - Base URL of your OIDC provider
  - Example: `https://keycloak.example.com/realms/maia`
- **Location**: `dashboard/core/settings.py`

### OIDC_SERVER_URL
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: OIDC server base URL
- **Details**: Base URL of the OIDC server (may differ from issuer URL)
- **Location**: `dashboard/core/settings.py`

### OIDC_REALM_NAME
- **Type**: String
- **Default**: `None`
- **Usage**: OIDC realm name (Keycloak-specific)
- **Details**: Name of the realm in Keycloak
- **Location**: `dashboard/core/settings.py`

### OIDC_OP_AUTHORIZATION_ENDPOINT
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: OIDC provider authorization endpoint
- **Details**: 
  - URL for OAuth2 authorization
  - Example: `https://keycloak.example.com/realms/maia/protocol/openid-connect/auth`
- **Location**: `dashboard/core/settings.py`

### OIDC_OP_TOKEN_ENDPOINT
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: OIDC provider token endpoint
- **Details**: 
  - URL for OAuth2 token exchange
  - Example: `https://keycloak.example.com/realms/maia/protocol/openid-connect/token`
- **Location**: `dashboard/core/settings.py`

### OIDC_OP_USER_ENDPOINT
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: OIDC provider user info endpoint
- **Details**: 
  - URL to retrieve user information
  - Example: `https://keycloak.example.com/realms/maia/protocol/openid-connect/userinfo`
- **Location**: `dashboard/core/settings.py`

### OIDC_OP_JWKS_ENDPOINT
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: OIDC provider JWKS (JSON Web Key Set) endpoint
- **Details**: 
  - URL for public keys used to verify JWT signatures
  - Example: `https://keycloak.example.com/realms/maia/protocol/openid-connect/certs`
- **Location**: `dashboard/core/settings.py`

### OIDC_RP_SIGN_ALGO
- **Type**: String
- **Default**: `None`
- **Usage**: Signing algorithm for OIDC tokens
- **Details**: 
  - Common values: `RS256`, `HS256`
  - Should match your OIDC provider configuration
- **Location**: `dashboard/core/settings.py`

### OIDC_RP_SCOPES
- **Type**: String (space-separated)
- **Default**: `None`
- **Usage**: OAuth2 scopes to request
- **Details**: 
  - Example: `openid profile email`
  - Determines what user information is accessible
- **Location**: `dashboard/core/settings.py`

### GITHUB_ID
- **Type**: String
- **Default**: `None`
- **Usage**: GitHub OAuth application client ID
- **Details**: Optional GitHub OAuth integration for authentication
- **Location**: `dashboard/core/settings.py`

### GITHUB_SECRET
- **Type**: String
- **Default**: `None`
- **Usage**: GitHub OAuth application client secret
- **Details**: Required if GitHub OAuth is enabled
- **Location**: `dashboard/core/settings.py`

---

## Database Configuration

The dashboard supports both MySQL and SQLite databases. Choose one based on your deployment needs.

### DB_ENGINE
- **Type**: String
- **Default**: `mysql` (if set), otherwise SQLite
- **Usage**: Database backend engine
- **Details**: 
  - Set to `mysql` to use MySQL
  - Leave unset or set to any other value to use SQLite
- **Location**: `dashboard/core/settings.py`

### MySQL Configuration (when DB_ENGINE=mysql)

#### DB_NAME
- **Type**: String
- **Default**: `appseed_db`
- **Required**: Yes (for MySQL)
- **Usage**: MySQL database name
- **Location**: `dashboard/core/settings.py`

#### DB_USERNAME
- **Type**: String
- **Default**: `appseed_db_usr`
- **Required**: Yes (for MySQL)
- **Usage**: MySQL database username
- **Location**: `dashboard/core/settings.py`

#### DB_PASS
- **Type**: String
- **Default**: `pass`
- **Required**: Yes (for MySQL)
- **Usage**: MySQL database password
- **Location**: `dashboard/core/settings.py`

#### DB_HOST
- **Type**: String (hostname/IP)
- **Default**: `localhost`
- **Required**: Yes (for MySQL)
- **Usage**: MySQL database host
- **Location**: `dashboard/core/settings.py`

#### DB_PORT
- **Type**: Integer
- **Default**: `3306`
- **Required**: Yes (for MySQL)
- **Usage**: MySQL database port
- **Location**: `dashboard/core/settings.py`

### SQLite Configuration (when DB_ENGINE is not mysql)

#### LOCAL_DB_PATH
- **Type**: String (directory path)
- **Default**: `BASE_DIR` (dashboard root directory)
- **Usage**: Directory where SQLite database file is stored
- **Details**: 
  - Database file will be created at `{LOCAL_DB_PATH}/db.sqlite3`
  - Used only when MySQL is not configured
- **Location**: `dashboard/core/settings.py`

---

## MinIO Object Storage

MinIO is optionally used for storing custom PIP/Conda environments when registering projects. If not configured, project registration will work without custom environment support.

### MINIO_URL
- **Type**: String (URL)
- **Default**: Empty string
- **Required**: No (optional for custom PIP/Conda environment support)
- **Usage**: MinIO server URL for internal connections
- **Details**: 
  - Example: `minio.example.com:9000` or `http://minio-service:9000`
  - Used for uploading and managing custom environment packages
  - If not configured, custom environment upload features will be disabled
- **Location**: `dashboard/core/settings.py`

### MINIO_PUBLIC_URL
- **Type**: String (URL)
- **Default**: Same as `MINIO_URL`
- **Usage**: MinIO server URL for public/shareable links
- **Details**: 
  - Used to generate public URLs for downloading environments
  - Can differ from MINIO_URL if accessing through different endpoints
- **Location**: `dashboard/core/settings.py`

### MINIO_ACCESS_KEY
- **Type**: String
- **Default**: `N/A`
- **Required**: No (required only if MinIO is used)
- **Usage**: MinIO access key (username)
- **Location**: `dashboard/core/settings.py`

### MINIO_SECRET_KEY
- **Type**: String
- **Default**: `N/A`
- **Required**: No (required only if MinIO is used)
- **Usage**: MinIO secret key (password)
- **Location**: `dashboard/core/settings.py`

### MINIO_SECURE
- **Type**: Boolean
- **Default**: `True`
- **Usage**: Use HTTPS for MinIO connections
- **Details**: Set to `False` for HTTP-only connections
- **Location**: `dashboard/core/settings.py`

### MINIO_PUBLIC_SECURE
- **Type**: Boolean
- **Default**: Same as `MINIO_SECURE`
- **Usage**: Use HTTPS for public MinIO URLs
- **Details**: Can differ from MINIO_SECURE if public endpoint uses different protocol
- **Location**: `dashboard/core/settings.py`

### BUCKET_NAME
- **Type**: String
- **Default**: Empty string
- **Required**: No (required only if MinIO is used)
- **Usage**: MinIO bucket name for storing environments
- **Details**: The bucket must exist or be auto-created if MinIO is configured
- **Location**: `dashboard/core/settings.py`

### MINIO_CONSOLE_URL
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: URL to MinIO console for accessing custom environments
- **Details**: 
  - Used in user/namespace views to provide console access links
  - Example: `https://minio-console.example.com`
- **Location**: `dashboard/apps/user_management/views.py`, `dashboard/apps/namespaces/views.py`

---

## ArgoCD Deployment

ArgoCD is used for GitOps-based deployment of MAIA projects and namespaces.

### ARGOCD_SERVER
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: ArgoCD server URL
- **Details**: 
  - Example: `https://argocd.example.com`
  - Required for project deployment functionality
- **Location**: `dashboard/core/settings.py`

### ARGOCD_CLUSTER
- **Type**: String
- **Default**: `None`
- **Usage**: ArgoCD cluster name
- **Details**: 
  - Should match a cluster name in the cluster configuration files
  - Used to target deployments to specific clusters
- **Location**: `dashboard/core/settings.py`

### ARGOCD_DISABLED
- **Type**: String (Boolean-like)
- **Default**: Not set (ArgoCD enabled)
- **Usage**: Disable ArgoCD deployment, use direct Helm deployment instead
- **Details**: 
  - Set to `"True"` (string) to disable ArgoCD and deploy directly with Helm
  - Used in `dashboard/apps/user_management/views.py`
- **Location**: `dashboard/apps/user_management/views.py`

---

## Notifications & Communication

### DISCORD_URL
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: Discord webhook URL for notifications
- **Details**: 
  - Sends notifications when projects/users are registered
  - Webhook URL from Discord channel settings
- **Location**: `dashboard/core/settings.py`

### DISCORD_SUPPORT_URL
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: Discord support channel invite link
- **Details**: Displayed to users for support access
- **Location**: `dashboard/core/settings.py`

### Email Configuration (MAIA Package)

These variables are used by the MAIA package for sending email notifications.

#### email_account
- **Type**: String (email address)
- **Default**: Not set
- **Usage**: Email account for sending notifications
- **Details**: Used by `MAIA.keycloak_utils` for user notifications
- **Location**: `MAIA/keycloak_utils.py`

#### email_password
- **Type**: String
- **Default**: Not set
- **Usage**: Password for email account
- **Details**: Used for SMTP authentication
- **Location**: `MAIA/keycloak_utils.py`

#### email_smtp_server
- **Type**: String (hostname:port)
- **Default**: Not set
- **Usage**: SMTP server for sending emails
- **Details**: 
  - Example: `smtp.gmail.com:587`
  - Used by `MAIA.keycloak_utils`
- **Location**: `MAIA/keycloak_utils.py`

#### admin_email
- **Type**: String (email address)
- **Default**: Not set
- **Usage**: Administrator email address for notifications
- **Details**: Referenced in authentication views
- **Location**: `dashboard/apps/authentication/views.py` (commented out)

---

## AI & Chatbot Integration

### OPENWEBAI_API_KEY
- **Type**: String
- **Default**: `None`
- **Usage**: OpenAI API key for MAIA Chatbot
- **Details**: Required for AI-powered chatbot functionality
- **Location**: `dashboard/core/settings.py`

### OPENWEBAI_URL
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: OpenAI API endpoint URL
- **Details**: 
  - Custom OpenAI-compatible API endpoint
  - Use for self-hosted or alternative AI services
- **Location**: `dashboard/core/settings.py`

---

## Kubernetes & Cluster Configuration

### CLUSTER_CONFIG_PATH
- **Type**: String (directory path)
- **Default**: Not set
- **Required**: Yes (for namespace deployment)
- **Usage**: Path to cluster configuration folder containing cluster config YAML files
- **Details**: 
  - Contains YAML files with cluster-specific settings
  - Used by namespace and user management views
  - Each file defines cluster connectivity, services, and GPU specs
- **Location**: `dashboard/apps/user_management/views.py`, `dashboard/apps/namespaces/views.py`

### CONFIG_PATH
- **Type**: String (directory path)
- **Default**: Not set
- **Usage**: General configuration folder path
- **Details**: May overlap with CLUSTER_CONFIG_PATH in some deployments
- **Location**: `dashboard/apps/user_management/views.py` (commented out)

### MAIA_CONFIG_PATH
- **Type**: String (file path)
- **Default**: Not set
- **Usage**: Path to MAIA configuration YAML file
- **Details**: Contains MAIA-specific deployment settings
- **Location**: `dashboard/apps/user_management/views.py` (commented out)

### KUBECONFIG_LOCAL
- **Type**: String (file path)
- **Default**: Same as `KUBECONFIG` (auto-set if not provided)
- **Usage**: Local copy of kubeconfig for operations
- **Details**: 
  - Auto-created from KUBECONFIG if not set
  - Used to avoid conflicts with concurrent operations
  - **Note**: KUBECONFIG itself is handled internally by the dashboard based on cluster selection and does not need to be configured externally
- **Location**: `MAIA/maia_admin.py`, `MAIA/maia_fn.py`, `MAIA/kubernetes_utils.py`

### DEPLOY_KUBECONFIG
- **Type**: String (file path)
- **Default**: Falls back to `KUBECONFIG`
- **Usage**: Kubernetes config specifically for deployment operations
- **Details**: Used in `MAIA/maia_core.py` for deployment tasks
- **Location**: `MAIA/maia_core.py`

### GLOBAL_NAMESPACES
- **Type**: String (comma-separated)
- **Default**: Empty list
- **Usage**: Namespaces to search for Kubeflow and XNAT Ingresses
- **Details**: 
  - Example: `xnat,kubeflow,istio-system`
  - Used to discover global services across namespaces
- **Location**: `dashboard/core/settings.py`

### DEFAULT_INGRESS_HOST
- **Type**: String (hostname)
- **Default**: `localhost`
- **Usage**: Default hostname for Kubernetes Ingress
- **Details**: 
  - Used when `spec.rules.host` is not set in ingress.yaml
  - Primarily for Kaapana integration
- **Location**: `dashboard/core/settings.py`

### POD_TERMINATOR_ADDRESS
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: Address of pod-terminator service to delete expired pods
- **Details**: 
  - Service that handles automated pod cleanup
  - Used in resource management views
- **Location**: `dashboard/apps/resources/views.py`

---

## MAIA Package Integration Variables

These variables are primarily used by the MAIA package when called from dashboard views, particularly for project and namespace deployment.

### MAIA_PRIVATE_REGISTRY
- **Type**: String (URL)
- **Default**: `None`
- **Usage**: Private container registry URL for MAIA images
- **Details**: 
  - Example: `registry.example.com/maia`
  - Used for pulling MAIA workspace, Orthanc, and other images
  - Referenced in namespace deployment and MAIA admin functions
- **Location**: `dashboard/apps/user_management/views.py`, `MAIA/maia_admin.py`, `MAIA/maia_fn.py`

### MAIA_SEGMENTATION_PORTAL_NAMESPACE_ID
- **Type**: String
- **Default**: `maia-segmentation`
- **Usage**: Namespace ID for segmentation portal
- **Details**: 
  - Used to retrieve segmentation models
  - Referenced in segmentation portal views
- **Location**: `dashboard/apps/maia_segmentation_portal/views.py`

### JHUB_IMAGE
- **Type**: String (image URL)
- **Default**: Not set
- **Usage**: Custom JupyterHub image repository
- **Details**: 
  - Example: `registry.example.com/jupyterhub-ks-kaapana`
  - Used when creating JupyterHub configurations
- **Location**: `MAIA_scripts/MAIA_create_JupyterHub_config.py`

### Helm Chart & Version Variables

These are used in MAIA admin toolkit and dashboard deployment:

#### admin_group_ID
- **Type**: String
- **Default**: Not set
- **Usage**: Administrator group identifier
- **Location**: `MAIA/maia_core.py`

#### dashboard_api_secret
- **Type**: String
- **Default**: Not set
- **Usage**: API secret for dashboard authentication
- **Location**: `MAIA/maia_core.py`

#### keycloak_client_id
- **Type**: String
- **Default**: Not set
- **Usage**: Keycloak client ID for MAIA services
- **Location**: `MAIA/maia_fn.py`, `MAIA/maia_core.py`

#### keycloak_client_secret
- **Type**: String
- **Default**: Not set
- **Usage**: Keycloak client secret for MAIA services
- **Location**: `MAIA/maia_fn.py`, `MAIA/maia_core.py`

#### keycloak_issuer_url
- **Type**: String (URL)
- **Default**: Not set
- **Usage**: Keycloak issuer URL for OIDC configuration
- **Location**: `MAIA/maia_fn.py`

#### maia_orthanc_image
- **Type**: String (image URL)
- **Default**: Not set
- **Usage**: Orthanc DICOM server image repository
- **Location**: `MAIA/maia_fn.py`

#### maia_orthanc_version
- **Type**: String (version tag)
- **Default**: Not set
- **Usage**: Orthanc image version tag
- **Location**: `MAIA/maia_fn.py`

### Git Integration Variables (for Docker image building)

#### MAIA_HELM_REPO_URL
- **Type**: String (URL)
- **Default**: Required (checked in code)
- **Usage**: Helm repository URL for MAIA charts
- **Location**: `MAIA/maia_docker_images.py`

#### MAIA_GIT_REPO_URL
- **Type**: String (URL)
- **Default**: Required (checked in code)
- **Usage**: Git repository URL for MAIA source code
- **Location**: `MAIA/maia_docker_images.py`

#### GIT_USERNAME
- **Type**: String
- **Default**: Required (checked in code)
- **Usage**: Git username for repository access
- **Location**: `MAIA/maia_docker_images.py`

#### GIT_TOKEN
- **Type**: String
- **Default**: Required (checked in code)
- **Usage**: Git access token for repository authentication
- **Location**: `MAIA/maia_docker_images.py`

#### MAIA_DASHBOARD_DOMAIN
- **Type**: String (domain)
- **Default**: Required (in maia_core)
- **Usage**: Dashboard domain for MAIA deployments
- **Location**: `MAIA/maia_core.py`

---

## Docker Registry & Images

### imagePullSecrets
- **Type**: String
- **Default**: Not set
- **Usage**: Kubernetes secret name for pulling private images
- **Details**: 
  - Used when deploying namespaces and services
  - Referenced in cluster configuration
- **Location**: `MAIA/maia_fn.py`, `MAIA/maia_admin.py`

### docker_email
- **Type**: String (email address)
- **Default**: Not set (shown in environment.md as example)
- **Usage**: Email for Docker registry authentication
- **Details**: Used in cluster configuration for creating registry secrets
- **Location**: Referenced in cluster config, used by `MAIA/maia_admin.py`

### docker_password
- **Type**: String
- **Default**: Not set
- **Usage**: Password for Docker registry authentication
- **Location**: `MAIA_scripts/MAIA_build_images.py`, cluster configs

### docker_server
- **Type**: String (URL)
- **Default**: Not set
- **Usage**: Docker registry server URL
- **Details**: Example: `registry.example.com`
- **Location**: Referenced in cluster config, used by `MAIA/maia_fn.py`

### docker_username
- **Type**: String
- **Default**: Not set
- **Usage**: Username for Docker registry authentication
- **Location**: Referenced in cluster config, used by `MAIA/maia_fn.py`

---

## Advanced Configuration

### BACKEND
- **Type**: String
- **Default**: `default`
- **Usage**: Backend deployment mode
- **Details**: 
  - Set to `compose` to enable compose-specific deployment mode
  - Affects namespace discovery and deployment behavior
  - Disables certain components in compose mode
- **Location**: Multiple files across dashboard apps and `MAIA/kubernetes_utils.py`

### PROJECT_NAME
- **Type**: String
- **Default**: Not set
- **Required**: Yes (when BACKEND=compose)
- **Usage**: Project name for compose deployment
- **Details**: Used as namespace when running in compose mode
- **Location**: `MAIA/kubernetes_utils.py`

### CIFS_SERVER
- **Type**: String (URL/path)
- **Default**: Not set
- **Usage**: CIFS server URL for shared storage access
- **Details**: 
  - Used for network file sharing in MAIA filebrowser
  - Example: `//fileserver.example.com/share`
- **Location**: `MAIA/maia_admin.py`

### JSON_KEY_PATH
- **Type**: String (file path)
- **Default**: Not set
- **Usage**: Path to JSON credentials file for registry authentication
- **Details**: 
  - Used for Harbor or GCR registry authentication
  - Auto-set by user management views
- **Location**: `dashboard/apps/user_management/views.py`, `MAIA/maia_admin.py`

---

## Configuration File Loading

The dashboard loads environment variables from `.env` files located in:
- **Debug mode (`DEBUG=True`)**: `<BASE_DIR>/config/env.env`
- **Production mode (`DEBUG=False`)**: `/mnt/dashboard-config/env.env`

The configuration directory also contains:
- Cluster configuration YAML files (loaded dynamically in `settings.py`)
- GPU specifications
- Service endpoint definitions
- MAIA-specific configuration files

## Cluster Configuration Files

In addition to environment variables, the dashboard loads cluster configurations from YAML files in `CLUSTER_CONFIG_PATH` (or `MOUNT_DIR`). These files define:

- **cluster_name**: Unique cluster identifier
- **maia_dashboard.enabled**: Whether this cluster is available in the dashboard
- **maia_dashboard.token**: Access token for private clusters
- **api**: API endpoint URL for the cluster
- **services**: Links to cluster services (Traefik, ArgoCD, Grafana, etc.)
- **gpu_specs**: GPU specifications available on the cluster

These configurations are loaded dynamically in `dashboard/core/settings.py` and populate:
- `CLUSTER_LINKS`: Service URLs per cluster
- `CLUSTER_NAMES`: Mapping of API URLs to cluster names
- `PRIVATE_CLUSTERS`: Authentication tokens for private clusters
- `API_URL`: List of cluster API endpoints
- `GPU_SPECS`: Available GPU types across all clusters

---

## Required vs Optional Variables

### Minimal Required Configuration (SQLite, no external services)
- `DEBUG`
- `SECRET_KEY` (change from default!)
- `SERVER`
- `OIDC_RP_CLIENT_ID`
- `OIDC_RP_CLIENT_SECRET`
- `OIDC_ISSUER_URL`
- `OIDC_OP_AUTHORIZATION_ENDPOINT`
- `OIDC_OP_TOKEN_ENDPOINT`
- `OIDC_OP_USER_ENDPOINT`

### Full Production Configuration
All minimal variables plus:
- MySQL database settings (`DB_ENGINE`, `DB_NAME`, `DB_USERNAME`, `DB_PASS`, `DB_HOST`, `DB_PORT`)
- ArgoCD settings (`ARGOCD_SERVER`, `ARGOCD_CLUSTER`)
- Cluster configuration (`CLUSTER_CONFIG_PATH`)
- MAIA registry (`MAIA_PRIVATE_REGISTRY`)
- MinIO for custom environments (`MINIO_URL`, `BUCKET_NAME`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`) - optional
- Email settings (if notifications enabled)
- Discord webhooks (if notifications enabled)

### Optional Enhancements
- GitHub OAuth (`GITHUB_ID`, `GITHUB_SECRET`)
- OpenAI chatbot (`OPENWEBAI_API_KEY`, `OPENWEBAI_URL`)
- Pod terminator (`POD_TERMINATOR_ADDRESS`)
- CIFS storage (`CIFS_SERVER`)
- Custom JupyterHub image (`JHUB_IMAGE`)

---

## Example Configuration

See `dashboard/README.md` for a complete example `.env` file structure.

For cluster configuration examples, refer to the YAML files in the `configs/` directory of the repository.

---

## Troubleshooting

1. **Database connection errors**: Verify MySQL settings if `DB_ENGINE=mysql`, or check `LOCAL_DB_PATH` permissions for SQLite
2. **OIDC authentication failures**: Ensure all `OIDC_*` endpoints are correct and accessible
3. **MinIO upload failures**: Verify `MINIO_URL`, credentials, and that `BUCKET_NAME` exists
4. **Namespace deployment failures**: Check `CLUSTER_CONFIG_PATH` contains valid YAML files and `KUBECONFIG` is accessible
5. **Image pull errors**: Verify `MAIA_PRIVATE_REGISTRY` and `imagePullSecrets` are correctly configured

---

## See Also

- `dashboard/README.md` - Dashboard setup and usage guide
- `dashboard/core/settings.py` - Django settings implementation
- `MAIA/maia_admin.py` - MAIA namespace deployment functions
- Helm charts in `charts/` - Deployment configurations
