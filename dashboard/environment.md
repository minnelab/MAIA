ENV

# If set to True, configuration is loaded from config/*, else from /mnt/dashboard-config. Can be overridden by the DEBUG environment variable.
DEBUG (False) 

# Token used to validate API requests for GPU booking and project deployments
SECRET_KEY (S#perS3crEt_007)

# Maximum memory and GPU allocation for a user
MAX_MEMORY (7) 2^7 = 128GB
MAX_CPU    (5) 2^5 = 32 CPUs


# MinIO Configuration used for storing PIP/Conda environments when registering a project.
MINIO_URL 
MINIO_ACCESS_KEY = ('N/A')
MINIO_SECRET_KEY = ('N/A')
MINIO_SECURE  = (True)
BUCKET_NAME

# Used to generate the public shareable link for the PIP/Conda environments.
MINIO_PUBLIC_URL (MINIO_URL)
MINIO_PUBLIC_SECURE (MINIO_SECURE)


# Discord Configuration used for sending notifications to the Discord channel.
DISCORD_URL (None) Webhook URL for the Discord channel. Used for sending notifications to the Discord channel when a project/user is registered.
DISCORD_SUPPORT_URL (None) Support Link for the Discord channel.

# Default Ingress Host, used for generating full URLs for the Kubernetes Ingress
DEFAULT_INGRESS_HOST (localhost) used if spec.rules.host is not set in the ingress.yaml file (i.e. Kaapana).

# OpenWebAI Configuration used for the MAIA Chatbot.
OPENWEBAI_API_KEY (None) OpenAI API key.
OPENWEBAI_URL (None) OpenAI API URL.

# ArgoCD Configuration used for deploying the projects.
ARGOCD_SERVER (None) ArgoCD Server URL.
ARGOCD_CLUSTER (None) ArgoCD Cluster Name.


# PUBLIC FQDN used for generating full URLs
SERVER

# SQLite Configuration used for storing user data. Only if MySQL is not used.
LOCAL_DB_PATH= (BASE_DIR)  <BASE_DIR>/db.sqlite3



# OpenID Connect Configuration used for authentication and user management
OIDC_RP_CLIENT_ID (None)
OIDC_RP_CLIENT_SECRET (None)
OIDC_SERVER_URL (None)
OIDC_REALM_NAME (None)
OIDC_USERNAME (None)

OIDC_ISSUER_URL (None)
OIDC_OP_AUTHORIZATION_ENDPOINT (None)
OIDC_OP_TOKEN_ENDPOINT (None)
OIDC_OP_USER_ENDPOINT (None)
OIDC_OP_JWKS_ENDPOINT (None)

OIDC_RP_SIGN_ALGO (None)
OIDC_RP_SCOPES (None)


# MySQL Configuration used for storing user data. Only if MySQL is used.
DB_ENGINE (mysql)
DB_NAME
DB_HOST
DB_PORT
DB_USERNAME
DB_PASS

BACKEND (default) or compose to enable/disable components for compose deployment
MAIA_SEGMENTATION_PORTAL_NAMESPACE_ID (maia-segmentation) namespace id for the segmentation portal, from where to retrieve the segmentation models
CLUSTER_CONFIG_PATH path to the cluster configuration files
MAIA_PRIVATE_REGISTRY private registry for the MAIA images
ARGOCD_DISABLED to disable ArgoCD deployment and directly deploy the projects using the HELM charts
GLOBAL_NAMESPACES namespaces to be searched for Kubeflow and XNAT Ingresses
JHUB_IMAGE custom image for the JupyterHub
MINIO_CONSOLE_URL MinIO Console URL to access the custom PIP/Conda environments
PROJECT_NAME Name of the project to be deployed in 'compose' deployment
CIFS_SERVER CIFS server URL to access the shared storage
POD_TERMINATOR_ADDRESS address of the pod-terminator service to delete expired pods
email_account email account for the email notifications
email_password email password for the email notifications
email_smtp_server email SMTP server for the email notifications



MAIA CONFIG

admin_group_ID
base_registry_server
base_registry_path
docker_build_project_chart
docker_build_project_repo
docker_build_project_version
argocd_namespace

core_project_chart
core_project_repo
core_project_version

admin_project_chart
admin_project_repo
admin_project_version

argocd_host
argocd_token

maia_project_chart
maia_project_repo
maia_project_version

maia_pro_project_chart
maia_pro_project_repo
maia_pro_project_version

dashboard_api_secret

maia_workspace_image
maia_workspace_pro_image

maia_workspace_version
maia_workspace_pro_version

maia_orthanc_image
maia_orthanc_version

maia_monai_toolkit_image

imagePullSecrets: docker-registry-secret-name # Default Docker registry secret name for pulling images in the cluster
docker_email: admin@maia.se  # Email for Docker registry authentication
docker_password: docker-password # Password for Docker registry authentication
docker_server: docker-registry-url # URL for the Docker registry, e.g., "registry.maia-cloud.com"
docker_username: docker-username # Username for Docker registry authentication

keycloak_client_id: keycloak-client-id
keycloak_client_secret: keycloak-client-secret
keycloak_issuer_url: https://<keycloak_url>/realms/<realm_name>
keycloak_authorize_url: https://<keycloak_url>/realms/<realm_name>/protocol/openid-connect/auth
keycloak_token_url: https://<keycloak_url>/realms/<realm_name>/protocol/openid-connect/token
keycloak_userdata_url: https://<keycloak_url>/realms/<realm_name>/protocol/openid-connect/userinfo

mysql_dashboard_password