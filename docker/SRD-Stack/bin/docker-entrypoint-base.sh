#!/bin/bash
# Base stage: Jupyter Lab + SSH on 2022. Home may be a PVC mount.
set -euo pipefail

HOME="${HOME:-/home/ubuntu}"
export HOME USER="${USER:-ubuntu}" LOGNAME="${USER}" SHELL="${SHELL:-/bin/bash}"
export NB_PREFIX="${NB_PREFIX:-/}"

run_priv() {
  if [ "$(id -u)" = "0" ]; then
    "$@"
  else
    sudo "$@"
  fi
}

PASSWORD="${UBUNTU_PASSWORD:-ubuntu}"
echo "ubuntu:${PASSWORD}" | run_priv chpasswd
run_priv /etc/install_ssh_server.sh

# shellcheck disable=SC1091
. /usr/bin/prepare-home.sh

cd "${HOME}"

if [ "$#" -eq 0 ]; then
  set -- supervisord
fi

if [ "$(id -u)" = "0" ]; then
  exec "$@"
fi
exec sudo --preserve-env=NB_PREFIX,JUPYTER_TOKEN,JUPYTER_PASSWORD,JUPYTER_PORT,UBUNTU_PASSWORD "$@"
