#!/bin/bash
# RDP stage: Jupyter + SSH 2022 + xrdp/XFCE on 3389 (aligned with docker/SRD).
# Home may be a PVC mount.
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

PASSWORD="${XRDP_PASSWORD:-${UBUNTU_PASSWORD:-ubuntu}}"
echo "ubuntu:${PASSWORD}" | run_priv chpasswd
run_priv /etc/install_ssh_server.sh

# generate xrdp key (same as docker/SRD)
if [ ! -f /etc/xrdp/rsakeys.ini ]; then
  run_priv xrdp-keygen xrdp auto
fi

# TLS cert for Guacamole (docker/SRD sets security_layer=tls)
if [ ! -f /etc/xrdp/cert.pem ]; then
  run_priv rm -f /etc/xrdp/key.pem || true
  if [ -z "${CERTIFICATE_SUBJECT:-}" ]; then
    CERTIFICATE_SUBJECT="/C=US/ST=Some State/L=Some City/O=Some Org/OU=Some Unit/CN=Terminalserver"
  fi
  run_priv openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout /etc/xrdp/key.pem \
    -out /etc/xrdp/cert.pem \
    -days 365 \
    -subj "${CERTIFICATE_SUBJECT}"
  run_priv crudini --set /etc/xrdp/xrdp.ini Globals security_layer tls
  run_priv crudini --set /etc/xrdp/xrdp.ini Globals certificate /etc/xrdp/cert.pem
  run_priv crudini --set /etc/xrdp/xrdp.ini Globals key_file /etc/xrdp/key.pem
fi

run_priv bash -c 'uuidgen > /etc/machine-id'
if ! grep -q 'QT_XKB_CONFIG_ROOT' /etc/profile 2>/dev/null; then
  run_priv bash -c 'echo "export QT_XKB_CONFIG_ROOT=/usr/share/X11/locale" >> /etc/profile'
fi

# shellcheck disable=SC1091
. /usr/bin/prepare-home.sh

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
exec sudo --preserve-env=NB_PREFIX,JUPYTER_TOKEN,JUPYTER_PASSWORD,JUPYTER_PORT,XRDP_PASSWORD,UBUNTU_PASSWORD "$@"
