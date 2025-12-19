#!/bin/bash

CORE_PROJECT_VERSION="0.1.8"
CORE_PROJECT_CHART="maia-core-project"
CORE_PROJECT_REPO="https://minnelab.github.io/MAIA/"
ADMIN_PROJECT_CHART="maia-admin-project"
ADMIN_PROJECT_REPO="https://minnelab.github.io/MAIA/"
ADMIN_PROJECT_VERSION="0.1.4"
ARGOCD_NAMESPACE="argocd"
ADMIN_GROUP_ID="MAIA:admin"

if [ $# -ge 1 ]; then
  ENV_JSON="$1"
  if [ ! -f "$ENV_JSON" ]; then
    echo "Error: '$ENV_JSON' is not a file."
    exit 1
  fi
  # Parse JSON and export as envvars
  # Requires 'jq' to be installed
  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: 'jq' is required but not installed."
    exit 1
  fi
  while IFS="=" read -r key value; do
    export ${key}=${value}
    echo "Read $key from $ENV_JSON"
  done < <(jq -r 'to_entries|map("\(.key)=\(.value|tostring)")|.[]' "$ENV_JSON")
  export CONFIG_FOLDER=$(dirname "$(realpath "$ENV_JSON")")
  if [ -n "$CONFIG_FOLDER" ]; then
    echo "Exported CONFIG_FOLDER from $ENV_JSON"
  fi
  # Extract CLUSTER_NAME from DEPLOY_KUBECONFIG if possible
  if [ -n "$DEPLOY_KUBECONFIG" ]; then
    CLUSTER_NAME=$(basename "$DEPLOY_KUBECONFIG" | sed -E 's/-kubeconfig\.yaml$//')
    export CLUSTER_NAME=${CLUSTER_NAME}
    echo "Extracted CLUSTER_NAME='$CLUSTER_NAME' from DEPLOY_KUBECONFIG"
  fi
fi

# If JSON_KEY_PATH is set, load harbor credentials from it
if [ -n "$JSON_KEY_PATH" ] && [ -f "$JSON_KEY_PATH" ]; then
  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: 'jq' is required but not installed."
    exit 1
  fi
  export HARBOR_USERNAME=$(jq -r '.harbor_username // empty' "$JSON_KEY_PATH")
  export HARBOR_PASSWORD=$(jq -r '.harbor_password // empty' "$JSON_KEY_PATH")
  if [ -n "$HARBOR_USERNAME" ]; then
    echo "Exported HARBOR_USERNAME from $JSON_KEY_PATH"
  fi
  if [ -n "$HARBOR_PASSWORD" ]; then
    echo "Exported HARBOR_PASSWORD from $JSON_KEY_PATH"
  fi
fi

if [ -n "$CLUSTER_NAME" ]; then
  if [ -z "$CONFIG_FOLDER" ]; then
    echo "Error: CONFIG_FOLDER must be set to read cluster configuration."
    exit 1
  fi
  CLUSTER_CONFIG_FILE="$CONFIG_FOLDER/$CLUSTER_NAME.yaml"
  if [ ! -f "$CLUSTER_CONFIG_FILE" ]; then
    echo "Warning: Cluster config file '$CLUSTER_CONFIG_FILE' does not exist. Skipping CLUSTER_DOMAIN extraction."
  else
    if ! command -v yq >/dev/null 2>&1; then
      echo "Error: 'yq' is required but not installed to extract cluster_domain from YAML."
      exit 1
    fi
    CLUSTER_DOMAIN_VAL=$(yq '.cluster_domain // .domain // empty' "$CLUSTER_CONFIG_FILE")
    if [ -n "$CLUSTER_DOMAIN_VAL" ]; then
      # Remove quotes only if present
      export CLUSTER_DOMAIN=$(echo "${CLUSTER_DOMAIN_VAL}" | sed 's/^"\(.*\)"$/\1/')
      echo "Loaded CLUSTER_DOMAIN from $CLUSTER_CONFIG_FILE"
    fi
    export K8S_DISTRIBUTION=$(yq '.k8s_distribution // empty' "$CLUSTER_CONFIG_FILE")
    if [ -n "$K8S_DISTRIBUTION" ]; then
      export K8S_DISTRIBUTION=$(echo "${K8S_DISTRIBUTION}" | sed 's/^"\(.*\)"$/\1/')
      echo "Loaded K8S_DISTRIBUTION from $CLUSTER_CONFIG_FILE"
    fi
    export INGRESS_RESOLVER_EMAIL=$(yq '.ingress_resolver_email // empty' "$CLUSTER_CONFIG_FILE" | sed 's/^"\(.*\)"$/\1/')
    echo "Loaded INGRESS_RESOLVER_EMAIL from $CLUSTER_CONFIG_FILE"
    export RANCHER_TOKEN=$(yq '.rancher_token // empty' "$CLUSTER_CONFIG_FILE")
    if [ -n "$RANCHER_TOKEN" ]; then
      export RANCHER_TOKEN=$(echo "${RANCHER_TOKEN}" | sed 's/^"\(.*\)"$/\1/')
      echo "Loaded RANCHER_TOKEN from $CLUSTER_CONFIG_FILE"
    fi
  fi
fi


# Required environment variables:
# Verify required environment variables are set
# List of required environment variables with short descriptions:
# MAIA_PRIVATE_REGISTRY   - The URL of the private MAIA Docker/Helm registry.
# HARBOR_USERNAME        - Username for authenticating with the MAIA Harbor registry.
# HARBOR_PASSWORD        - Password for authenticating with the MAIA Harbor registry.
# KUBECONFIG             - Path to the kubeconfig file for the Kubernetes cluster.
# CLUSTER_DOMAIN         - The public domain or base domain for the MAIA cluster.
# CONFIG_FOLDER          - Directory path to store MAIA/cluster configuration files.
# CLUSTER_NAME           - Name to assign to the MAIA Kubernetes cluster.
# INGRESS_RESOLVER_EMAIL - Email for Let's Encrypt certificate for ingress.
# K8S_DISTRIBUTION       - Chosen Kubernetes distribution (e.g., "microk8s", "rke2").
required_vars=(
  "MAIA_PRIVATE_REGISTRY"
  "HARBOR_USERNAME"
  "HARBOR_PASSWORD"
  "CLUSTER_DOMAIN"
  "CLUSTER_NAME"
  "CONFIG_FOLDER"
  "INGRESS_RESOLVER_EMAIL"
  "K8S_DISTRIBUTION"
)

for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    if [ "$var" = "MAIA_PRIVATE_REGISTRY" ] && [ -v MAIA_PRIVATE_REGISTRY ] && [ -z "${MAIA_PRIVATE_REGISTRY}" ]; then
      export PUBLIC_REGISTRY=1
      continue
    fi
    if [ "$var" = "INGRESS_RESOLVER_EMAIL" ] && [ -v INGRESS_RESOLVER_EMAIL ] && [ -z "${INGRESS_RESOLVER_EMAIL}" ]; then
      continue
    fi
    # If PUBLIC_REGISTRY=1, skip prompting for HARBOR_USERNAME and HARBOR_PASSWORD
    if [ "$PUBLIC_REGISTRY" = "1" ]; then
      if [ "$var" = "HARBOR_USERNAME" ] || [ "$var" = "HARBOR_PASSWORD" ]; then
        continue
      fi
    fi
    echo "Error: Required environment variable $var is not set."
    # Instead of exiting, prompt the user to input the missing variable
    # Dictionary containing short descriptions of each required variable
    declare -A var_descriptions=(
      ["MAIA_PRIVATE_REGISTRY"]="The URL of the private MAIA Docker/Helm registry."
      ["HARBOR_USERNAME"]="Username for authenticating with the MAIA Harbor registry."
      ["HARBOR_PASSWORD"]="Password for authenticating with the MAIA Harbor registry."
      ["CLUSTER_DOMAIN"]="The public domain or base domain for the MAIA cluster."
      ["CONFIG_FOLDER"]="Directory path to store MAIA/cluster configuration files."
      ["CLUSTER_NAME"]="Name to assign to the MAIA Kubernetes cluster."
      ["INGRESS_RESOLVER_EMAIL"]="Email for Let's Encrypt certificate for ingress."
      ["K8S_DISTRIBUTION"]="Chosen Kubernetes distribution (e.g., 'microk8s', 'rke2', 'k3s', 'k0s')."
    )
    description="${var_descriptions[$var]}"
    if [ -z "$description" ]; then
      description="(No description available for $var)"
    fi
    read -p "Please enter a value for $var ($description): " input_var
    if [ -z "$input_var" ]; then
      # Check if the variable is already present in the file; if not, exit
        if [ "$var" == "MAIA_PRIVATE_REGISTRY" ]; then
          # Allow empty for MAIA_PRIVATE_REGISTRY
          export PUBLIC_REGISTRY=1
          export $var=""
          echo "MAIA_PRIVATE_REGISTRY left empty -- using PUBLIC_REGISTRY=1"
        elif [ "$var" == "CONFIG_FOLDER" ]; then
          input_var="$(pwd)/${CLUSTER_NAME}-config"
          echo "CONFIG_FOLDER set to $input_var"
        elif [ "$var" == "INGRESS_RESOLVER_EMAIL" ]; then
          export $var=""
          echo "INGRESS_RESOLVER_EMAIL left empty"
        else
          echo "Error: $var is not set. Exiting."
          exit 1
        fi

    fi
    if [ "$var" == "CONFIG_FOLDER" ]; then
      # If CONFIG_FOLDER is not absolute, make it absolute based on current directory
      if [[ "$input_var" != /* ]]; then
        input_var="$(pwd)/$input_var"
      fi
    fi
    if [ "$var" == "INGRESS_RESOLVER_EMAIL" ]; then
      # Basic email validation using regex or ignore if empty
      if [ -n "$input_var" ] && ! [[ "$input_var" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        echo "Error: INGRESS_RESOLVER_EMAIL must be a valid email address."
        exit 1
      fi
    fi
    if [ "$var" == "K8S_DISTRIBUTION" ]; then
      valid_distributions=("microk8s" "rke2" "k3s" "k0s")
      is_valid=false
      for dist in "${valid_distributions[@]}"; do
        if [ "$input_var" == "$dist" ]; then
          is_valid=true
          break
        fi
      done
      if [ "$is_valid" = false ]; then
        echo "Error: K8S_DISTRIBUTION must be one of: ${valid_distributions[*]}"
        exit 1
      fi
    fi
    export $var="$input_var"
  fi
done

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  if [ -f "$CONFIG_FOLDER/$CLUSTER_NAME.yaml" ]; then
    existing_traefik_dashboard_password=$(yq -r '.traefik_dashboard_password // empty' "$CONFIG_FOLDER/$CLUSTER_NAME.yaml")
  else
    existing_traefik_dashboard_password=""
  fi
else
  existing_traefik_dashboard_password=""
fi

if [ -n "$existing_traefik_dashboard_password" ] && [ "$existing_traefik_dashboard_password" != "null" ]; then
  traefik_dashboard_password="$existing_traefik_dashboard_password"
else
  traefik_dashboard_password=$(openssl rand -hex 12)
fi

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  if [ -f "$CONFIG_FOLDER/$CLUSTER_NAME.yaml" ]; then
    existing_rancher_password=$(yq -r '.rancher_password // empty' "$CONFIG_FOLDER/$CLUSTER_NAME.yaml")
  else
    existing_rancher_password=""
  fi
else
  existing_rancher_password=""
fi

if [ -n "$existing_rancher_password" ] && [ "$existing_rancher_password" != "null" ]; then
  rancher_password="$existing_rancher_password"
else
  rancher_password=$(openssl rand -hex 12)
fi

export SSH_PORT_TYPE=${SSH_PORT_TYPE:-NodePort}
export PORT_RANGE_LOWER_BOUND=${PORT_RANGE_LOWER_BOUND:-30000}
export PORT_RANGE_UPPER_BOUND=${PORT_RANGE_UPPER_BOUND:-31000}

if [ "$K8S_DISTRIBUTION" = "microk8s" ]; then
  export STORAGE_CLASS=${STORAGE_CLASS:-microk8s-hostpath}
  export SHARED_STORAGE_CLASS=${SHARED_STORAGE_CLASS:-nfs-client}
fi
export URL_TYPE=${URL_TYPE:-subdomain}
export BUCKET_NAME=${BUCKET_NAME:-maia-envs}

mkdir -p $CONFIG_FOLDER
cat <<EOF > $CONFIG_FOLDER/$CLUSTER_NAME.yaml
domain: "$CLUSTER_DOMAIN"
ingress_resolver_email: "$INGRESS_RESOLVER_EMAIL"
cluster_name: "$CLUSTER_NAME"
k8s_distribution: "$K8S_DISTRIBUTION"
traefik_resolver: "maiaresolver"
traefik_dashboard_password: "$traefik_dashboard_password"
rancher_password: "$rancher_password"
rancher_token: "$RANCHER_TOKEN"
rootCA: $CONFIG_FOLDER/ca.crt
bucket_name: $BUCKET_NAME
ssh_port_type: $SSH_PORT_TYPE
port_range:
- $PORT_RANGE_LOWER_BOUND
- $PORT_RANGE_UPPER_BOUND
shared_storage_class: $SHARED_STORAGE_CLASS
storage_class: $STORAGE_CLASS
url_type: $URL_TYPE
EOF

cat <<EOF > $CONFIG_FOLDER/microk8s-config.yaml
version: 0.2.0
#extraCNIEnv:
#  IPv4_CLUSTER_CIDR: "10.2.0.0/16"
#  IPv4_SERVICE_CIDR: "10.94.0.0/34"
extraSANs:
  #- "10.94.0.1"
  - "$CLUSTER_DOMAIN"
addons:
  - name: dns
EOF





JSON_KEY_PATH=$CONFIG_FOLDER/maia-registry-credentials.json
cat <<EOF > $JSON_KEY_PATH
{
  "harbor_username": "$HARBOR_USERNAME",
  "harbor_password": "$HARBOR_PASSWORD"
}
EOF

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  existing_dashboard_api_secret=$(jq -r '.dashboard_api_secret' "$CONFIG_FOLDER/env.json")
else
  existing_dashboard_api_secret=""
fi

if [ -n "$existing_dashboard_api_secret" ] && [ "$existing_dashboard_api_secret" != "null" ]; then
  dashboard_api_secret="$existing_dashboard_api_secret"
else
  dashboard_api_secret=$(openssl rand -hex 12)
fi


if [ -f "$CONFIG_FOLDER/env.json" ]; then
  existing_keycloak_client_secret=$(jq -r '.keycloak_client_secret' "$CONFIG_FOLDER/env.json")
else
  existing_keycloak_client_secret=""
fi

if [ -n "$existing_keycloak_client_secret" ] && [ "$existing_keycloak_client_secret" != "null" ]; then
  keycloak_client_secret="$existing_keycloak_client_secret"
else
  keycloak_client_secret=$(openssl rand -hex 12)
fi

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  existing_argocd_password=$(jq -r '.ARGOCD_PASSWORD' "$CONFIG_FOLDER/env.json")
else
  existing_argocd_password=""
fi

if [ -n "$existing_argocd_password" ] && [ "$existing_argocd_password" != "null" ]; then
  ARGOCD_PASSWORD="$existing_argocd_password"
else
  ARGOCD_PASSWORD=$(openssl rand -hex 12)
fi
BCRYPT=$(htpasswd -nbBC 10 "" "$ARGOCD_PASSWORD" | tr -d ':\n' | sed 's/\$2y/\$2a/')
ARGOCD_BCRYPT_PASSWORD="$BCRYPT"
export ARGOCD_PASSWORD="$ARGOCD_PASSWORD"
export ARGOCD_BCRYPT_PASSWORD="$ARGOCD_BCRYPT_PASSWORD"

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  existing_minio_admin_password=$(jq -r '.minio_admin_password' "$CONFIG_FOLDER/env.json")
else
  existing_minio_admin_password=""
fi

if [ -n "$existing_minio_admin_password" ] && [ "$existing_minio_admin_password" != "null" ]; then
  minio_admin_password="$existing_minio_admin_password"
else
  minio_admin_password=$(openssl rand -hex 12)
fi

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  existing_minio_root_password=$(jq -r '.minio_root_password' "$CONFIG_FOLDER/env.json")
else
  existing_minio_root_password=""
fi

if [ -n "$existing_minio_root_password" ] && [ "$existing_minio_root_password" != "null" ]; then
  minio_root_password="$existing_minio_root_password"
else
  minio_root_password=$(openssl rand -hex 12)
fi

if [ -f "$CONFIG_FOLDER/env.json" ]; then
  existing_mysql_dashboard_password=$(jq -r '.mysql_dashboard_password' "$CONFIG_FOLDER/env.json")
else
  existing_mysql_dashboard_password=""
fi

if [ -n "$existing_mysql_dashboard_password" ] && [ "$existing_mysql_dashboard_password" != "null" ]; then
  mysql_dashboard_password="$existing_mysql_dashboard_password"
else
  mysql_dashboard_password=$(openssl rand -hex 12)
fi

cat <<EOF > $CONFIG_FOLDER/env.json
{
  "MAIA_PRIVATE_REGISTRY": "$MAIA_PRIVATE_REGISTRY",
  "cluster_name": "$CLUSTER_NAME",
  "JSON_KEY_PATH": "$JSON_KEY_PATH",
  "keycloak_client_secret": "$keycloak_client_secret",
  "DEPLOY_KUBECONFIG": "$CONFIG_FOLDER/$CLUSTER_NAME-kubeconfig.yaml",
  "MAIA_DASHBOARD_DOMAIN": "maia.$CLUSTER_DOMAIN",
  "dashboard_api_secret": "$dashboard_api_secret",
  "argocd_namespace": "$ARGOCD_NAMESPACE",
  "admin_group_ID": "$ADMIN_GROUP_ID",
  "core_project_chart": "$CORE_PROJECT_CHART",
  "core_project_repo": "$CORE_PROJECT_REPO",
  "core_project_version": "$CORE_PROJECT_VERSION",
  "ARGOCD_PASSWORD": "$ARGOCD_PASSWORD",
  "argocd_bcrypt_password": "$ARGOCD_BCRYPT_PASSWORD",
  "admin_project_chart": "$ADMIN_PROJECT_CHART",
  "admin_project_repo": "$ADMIN_PROJECT_REPO",
  "admin_project_version": "$ADMIN_PROJECT_VERSION",
  "minio_admin_password": "$minio_admin_password",
  "minio_root_password": "$minio_root_password",
  "mysql_dashboard_password": "$mysql_dashboard_password"
}
EOF

wget https://raw.githubusercontent.com/minnelab/MAIA/refs/heads/master/MAIA/configs/MAIA_realm_template.json -O $CONFIG_FOLDER/MAIA_realm.json

CIFS_KEY_PATH="$CONFIG_FOLDER/cifs_key"
CIFS_KEY_PATH_PUB="$CONFIG_FOLDER/cifs_key.pub"
if [ -z "$CIFS_KEY_PATH" ] || [ ! -f "$CIFS_KEY_PATH" ] || [ ! -f "$CIFS_KEY_PATH_PUB" ]; then
echo "Do you want to generate a CIFS public-private key pair for CIFS shared storage support? (y/n)"
read -r generate_cifs_key

if [[ "$generate_cifs_key" =~ ^[Yy]$ ]]; then
  
  if [ -f "$CIFS_KEY_PATH" ] || [ -f "$CIFS_KEY_PATH_PUB" ]; then
    echo "A CIFS key already exists at $CIFS_KEY_PATH. Do you want to overwrite it? (y/n)"
    read -r overwrite_cifs_key
    if [[ ! "$overwrite_cifs_key" =~ ^[Yy]$ ]]; then
      echo "Skipping CIFS key generation."
    else
      ssh-keygen -t rsa -b 4096 -N "" -f "$CIFS_KEY_PATH"
      echo "CIFS public-private key pair generated."
    fi
  else
    ssh-keygen -t rsa -b 4096 -N "" -f "$CIFS_KEY_PATH"
    echo "CIFS public-private key pair generated."
  fi
  echo "CIFS private key: $CIFS_KEY_PATH"
  echo "CIFS public key: $CIFS_KEY_PATH_PUB"
else
  echo "Skipping CIFS key generation."
  touch $CIFS_KEY_PATH
  touch $CIFS_KEY_PATH_PUB
fi

fi