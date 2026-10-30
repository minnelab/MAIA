#!/bin/bash
# Base stage: Jupyter Lab + SSH on 2022. Home may be a PVC mount.
set -euo pipefail

HOME="${HOME:-/home/ubuntu}"
if [ -z "${SHELL:-}" ] || [ "${SHELL}" = "/bin/bash" ]; then
  if [ -r /etc/default-shell ]; then
    SHELL="$(cat /etc/default-shell)"
  elif [ -x /bin/zsh ]; then
    SHELL=/bin/zsh
  else
    SHELL=/bin/bash
  fi
fi
export HOME USER="${USER:-ubuntu}" LOGNAME="${USER}" SHELL
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

if [ ! -f /home/ubuntu/.bash_profile ]; then
  cp /etc/.bash_profile /home/ubuntu/
fi

if [ ! -f /home/ubuntu/.zshrc ]; then
  cp /etc/.zshrc /home/ubuntu/
fi

if [ ! -f /home/ubuntu/.tmux.conf ]; then
  cp /etc/.tmux.conf /home/ubuntu/
fi


/etc/install_libreoffice.sh
/etc/install_itksnap.sh
/etc/install_mitk.sh
/etc/install_napari.sh
/etc/install_qupath.sh
/etc/install_slicer.sh
/etc/install_matlab.sh
#source /etc/freesurfer/freesurfer/SetUpFreeSurfer.sh


exec sudo --preserve-env=NB_PREFIX,JUPYTER_TOKEN,JUPYTER_PASSWORD,JUPYTER_PORT,UBUNTU_PASSWORD "$@"
