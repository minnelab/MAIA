#!/bin/bash

sudo apt update
sudo apt install -y python3-pip ufw curl
sudo apt install -y jq yq apache2-utils
pip install maia-toolkit ansible jmespath --break-system-packages



curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh

VERSION=$(curl -s https://api.github.com/repos/argoproj/argo-cd/releases/latest | grep tag_name | cut -d '"' -f 4)
sudo curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/download/$VERSION/argocd-linux-amd64
sudo chmod +x /usr/local/bin/argocd




export MAIA_PRIVATE_REGISTRY=""
export INGRESS_RESOLVER_EMAIL=""

export K8S_DISTRIBUTION="microk8s"
export CONFIG_FOLDER="maia-config"

read -p "Enter cluster name: " CLUSTER_NAME
export CLUSTER_NAME
mkdir -p $CONFIG_FOLDER


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

cat <<EOF > $CONFIG_FOLDER/config.yaml
cluster_config_extra_env:
  selfsigned: true
EOF

export PATH=$HOME/.local/bin:$PATH
MAIA_Install --config-folder $CONFIG_FOLDER