#!/bin/bash

VERSION=0.0.0
MAIA_INSTALLATION_VERSION=0.0.0
sudo apt update
sudo apt install -y python3-pip ufw curl
sudo apt install -y jq yq apache2-utils
if [ "$1" == "--dev" ]; then
    pip install git+https://github.com/minnelab/MAIA.git@master --break-system-packages
else
    pip install maia-toolkit==${VERSION} --break-system-packages
fi

pip install ansible jmespath --break-system-packages



curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh

ARGOCD_VS=$(curl -s https://api.github.com/repos/argoproj/argo-cd/releases/latest | grep tag_name | cut -d '"' -f 4)
sudo curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/download/$ARGOCD_VS/argocd-linux-amd64
sudo chmod +x /usr/local/bin/argocd

export CONFIG_FOLDER="maia-config"
mkdir -p $CONFIG_FOLDER

echo "Do you want to run Step 1: prepare hosts (install NVIDIA drivers, NFS & CIFS storage drivers, and configure UFW firewall for SSH and node-to-node communication)?"
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            # Ask about each sub-step for configurability
            read -p "Install NVIDIA drivers? (y/N): " install_nvidia_drivers
            read -p "Install NFS drivers for storage? (y/N): " install_nfs
            read -p "Install CIFS drivers for storage? (y/N): " install_cifs
            read -p "Configure UFW firewall (to allow SSH and node-to-node communication)? (y/N): " configure_ufw

            # Build config.yaml with selected options
            export PREPARE_HOSTS="yes"
            break
            ;;
        No )
            # Write config.yaml with only cluster_config_extra_env (no prepare_hosts section)
            export PREPARE_HOSTS="no"
            break
            ;;
    esac
done

echo "Do you want to run Step 2: configure hosts (needed for self-signed certificates to map the local host to the cluster domain)?"
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export CONFIGURE_HOSTS="yes"
            break
            ;;
        No )
            export CONFIGURE_HOSTS="no"
            break
            ;;
    esac
done
echo "Do you want to run Step 3: install MicroK8s (install MicroK8s, enable OIDC authentication, create CA certificate in cert-manager, and install ArgoCD for GitOps-based application management)? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export INSTALL_MICROK8S="yes"
            read -p "Do you want to enable OIDC authentication for MicroK8s? (y/N): " enable_oidc_microk8s
            read -p "Do you want to create CA certificate in cert-manager? (y/N): " create_ca_cert_manager
            read -p "Do you want to install ArgoCD for GitOps-based application management? (y/N): " install_argocd
            break
            ;;
        No )
            export INSTALL_MICROK8S="no"
            break
            ;;
    esac
done

echo "Do you want to run Step 4: Install MAIA Core? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export INSTALL_MAIA_CORE="yes"
            break
            ;;
        No )
            export INSTALL_MAIA_CORE="no"
            break
            ;;
    esac
done

echo "Do you want to run Step 5: Install MAIA Admin? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export INSTALL_MAIA_ADMIN="yes"
            break
            ;;
        No )
            export INSTALL_MAIA_ADMIN="no"
            break
            ;;
    esac
done

echo "Do you want to run Step 6: Configure OIDC Authentication (configure Rancher and Harbor for OIDC authentication)? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export CONFIGURE_OIDC_AUTHENTICATION="yes"
            break
            ;;
        No )
            export CONFIGURE_OIDC_AUTHENTICATION="no"
            break
            ;;
    esac
done

echo "Do you want to run Step 7: Get Kubeconfig from Rancher local cluster? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export GET_KUBECONFIG_FROM_RANCHER_LOCAL="yes"
            break
            ;;
        No )
            export GET_KUBECONFIG_FROM_RANCHER_LOCAL="no"
            break
            ;;
    esac
done

echo "Do you want to run Step 8: Configure MAIA Dashboard? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export CONFIGURE_MAIA_DASHBOARD="yes"
            break
            ;;
        No )
            export CONFIGURE_MAIA_DASHBOARD="no"
            break
            ;;
    esac
done

echo "Do you want to generate self-signed certificates for the cluster? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export SELF_SIGNED_CERTIFICATES="yes"
            export INGRESS_RESOLVER_EMAIL=""
            break
            ;;
        No )
            export SELF_SIGNED_CERTIFICATES="no"
            read -p "Please provide a valid email for Let's Encrypt certificate generation: " INGRESS_RESOLVER_EMAIL
            # Verify it's a valid email
            while ! [[ "$INGRESS_RESOLVER_EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; do
                echo "Invalid email address. Please enter a valid email:"
                read INGRESS_RESOLVER_EMAIL
            done
            export INGRESS_RESOLVER_EMAIL
            break
            ;;
    esac
done

echo "Do you want to generate staging certificates with Let's Encrypt? (y/N): "
select yn in "Yes" "No"; do
    case $yn in
        Yes )
            export GENERATE_STAGING_CERTIFICATES="yes"
            break
            ;;
        No )
            export GENERATE_STAGING_CERTIFICATES="no"
            break
            ;;
    esac
done

if [ "$GENERATE_STAGING_CERTIFICATES" = "yes" ]; then
    # Download CA for Staging and save it in <CONFIG_FOLDER>/staging-ca.pem
    mkdir -p "$CONFIG_FOLDER"
    curl -fsSL "https://letsencrypt.org/certs/staging/letsencrypt-stg-root-x1.pem" -o "$CONFIG_FOLDER/staging-ca.pem"

fi

export PUBLIC_REGISTRY=1

export K8S_DISTRIBUTION="microk8s"

read -p "Enter cluster name: " CLUSTER_NAME
export CLUSTER_NAME

read -p "Enter cluster domain: " CLUSTER_DOMAIN
export CLUSTER_DOMAIN

cat <<EOF > $CONFIG_FOLDER/config.yaml
prepare_hosts:
  nvidia_drivers: $([ "${install_nvidia_drivers,,}" = "y" ] && echo "true" || echo "false")
  nfs: $([ "${install_nfs,,}" = "y" ] && echo "true" || echo "false")
  cifs: $([ "${install_cifs,,}" = "y" ] && echo "true" || echo "false")
  ufw: $([ "${configure_ufw,,}" = "y" ] && echo "true" || echo "false")
install_microk8s:
  install_microk8s: $([ "${INSTALL_MICROK8S,,}" = "yes" ] && echo "true" || echo "false")
  enable_oidc_microk8s: $([ "${enable_oidc_microk8s,,}" = "y" ] && echo "true" || echo "false")
  enable_ca_microk8s: $([ "${create_ca_cert_manager,,}" = "y" ] && echo "true" || echo "false")
  install_argocd: $([ "${install_argocd,,}" = "y" ] && echo "true" || echo "false")
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
  kubeconfig_file: "local.yaml"
configure_maia_dashboard:
  auto_sync: true
env:
  CLUSTER_DOMAIN: $CLUSTER_DOMAIN
  CLUSTER_NAME: $CLUSTER_NAME
  INGRESS_RESOLVER_EMAIL: $INGRESS_RESOLVER_EMAIL
  K8S_DISTRIBUTION: $K8S_DISTRIBUTION
steps:
  - empty
  $(if [ "$PREPARE_HOSTS" = "yes" ]; then echo "- prepare_hosts"; fi)
  $(if [ "$CONFIGURE_HOSTS" = "yes" ]; then echo "- configure_hosts"; fi)
  $(if [ "$INSTALL_MICROK8S" = "yes" ]; then echo "- install_microk8s"; fi)
  $(if [ "$INSTALL_MAIA_CORE" = "yes" ]; then echo "- install_maia_core"; fi)
  $(if [ "$INSTALL_MAIA_ADMIN" = "yes" ]; then echo "- install_maia_admin"; fi)
  $(if [ "$CONFIGURE_OIDC_AUTHENTICATION" = "yes" ]; then echo "- configure_oidc_authentication"; fi)
  $(if [ "$GET_KUBECONFIG_FROM_RANCHER_LOCAL" = "yes" ]; then echo "- get_kubeconfig_from_rancher_local"; fi)
  $(if [ "$CONFIGURE_MAIA_DASHBOARD" = "yes" ]; then echo "- configure_maia_dashboard"; fi)
cluster_config_extra_env:
  empty: empty
  $(if [ "$SELF_SIGNED_CERTIFICATES" = "yes" ]; then echo "selfsigned: true"; fi)
  $(if [ "$GENERATE_STAGING_CERTIFICATES" = "yes" ]; then echo "staging_certificates: true"; fi)
  $(if [ "$GENERATE_STAGING_CERTIFICATES" = "yes" ]; then 
    echo "externalCA:"; 
    echo "  name: \"iam-ca-secret\"";
    echo "  cert: \"$CONFIG_FOLDER/staging-ca.pem\"";
  fi)
EOF



export hostname=$(hostname)
read -s -p "Enter password for sudo/ansible: " PW
echo
export PW
# Verify password by attempting a simple sudo command
echo "$PW" | sudo -S -v >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Incorrect password for sudo. Exiting."
    exit 1
fi

cat <<EOF > $CONFIG_FOLDER/inventory
[control-plane]
$hostname ansible_host=127.0.0.1 ansible_connection=local ansible_user=$USER ansible_become_password=$PW ansible_become=true ansible_become_method=sudo
EOF

if [[ " $@ " =~ " --dry-run " ]]; then
    :
else
    export PATH=$HOME/.local/bin:$PATH
    MAIA_Install --config-folder $CONFIG_FOLDER --ansible-collection-path maia.installation==${MAIA_INSTALLATION_VERSION}
fi

