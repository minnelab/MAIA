#!/bin/bash
# Desktop stage: Jupyter Lab + Remote Desktop proxy + SSH. RDP disabled.
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
export DISABLE_RDP=1
export JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP="${JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP:-/usr/bin/start-xfce.sh}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"
export XAUTHORITY="${XDG_RUNTIME_DIR}/.Xauthority"

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

export XAUTHORITY="${XDG_RUNTIME_DIR}/.Xauthority"
mkdir -p "${XDG_RUNTIME_DIR}" "${HOME}/.vnc"
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
rm -f "${HOME}/.Xauthority.lock" "${XAUTHORITY}.lock" 2>/dev/null || true
touch "${XAUTHORITY}" 2>/dev/null || true
chown -R ubuntu:0 "${HOME}/.vnc" 2>/dev/null || true

# Ensure xrdp is not running
run_priv pkill -f '[x]rdp' 2>/dev/null || true

# Stale VNC display only — do NOT remove /tmp/jupyter-server-proxy-*
# (jupyter-remote-desktop-proxy places its unix socket there)
pkill -u "$(id -u)" -f '[X]tigervnc' 2>/dev/null || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "${HOME}/.vnc/"*":1.pid" 2>/dev/null || true

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY || true
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

exec sudo --preserve-env=NB_PREFIX,JUPYTER_TOKEN,JUPYTER_PASSWORD,JUPYTER_PORT,JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP,UBUNTU_PASSWORD,XAUTHORITY,XDG_RUNTIME_DIR,DISABLE_RDP,SHELL "$@"
