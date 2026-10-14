#!/bin/bash
# OpenShift: unprivileged Jupyter Lab + Remote Desktop proxy (no RDP, no SSH, no sudo).
set -euo pipefail

umask 0002

HOME="${HOME:-/home/ubuntu}"
export HOME
export SHELL="${SHELL:-/bin/bash}"
export NB_PREFIX="${NB_PREFIX:-/}"
export DISABLE_RDP=1
export JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP="${JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP:-/usr/bin/start-xfce.sh}"
export JUPYTER_RUNTIME_DIR="${JUPYTER_RUNTIME_DIR:-/tmp/jupyter/runtime}"
export JUPYTER_DATA_DIR="${JUPYTER_DATA_DIR:-${HOME}/.local/share/jupyter}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-$(id -u)}"
export XAUTHORITY="${XDG_RUNTIME_DIR}/.Xauthority"

# Arbitrary UID: ensure a passwd entry exists (needs chmod g=u /etc/passwd at build)
if ! getent passwd "$(id -u)" >/dev/null 2>&1; then
  if [ -w /etc/passwd ]; then
    echo "ubuntu:x:$(id -u):0:OpenShift user:${HOME}:${SHELL}" >> /etc/passwd
  fi
fi

export USER="$(id -un 2>/dev/null || echo ubuntu)"
export LOGNAME="${USER}"
export NB_USER="${USER}"

mkdir -p \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/Tutorials" \
  "${HOME}/.config" \
  "${HOME}/.local/share/jupyter/runtime" \
  "${HOME}/.jupyter" \
  "${HOME}/.vnc" \
  "${JUPYTER_RUNTIME_DIR}" \
  "${JUPYTER_DATA_DIR}" \
  "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
chmod -R g+rwX \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/Tutorials" \
  "${HOME}/.config" \
  "${HOME}/.local" \
  "${HOME}/.jupyter" \
  "${HOME}/.vnc" \
  2>/dev/null || true

rm -f "${HOME}/.Xauthority.lock" "${XAUTHORITY}.lock" 2>/dev/null || true
touch "${XAUTHORITY}" 2>/dev/null || true

# Seed XFCE / session files on empty PVC
if [ ! -e "${HOME}/.Xsession" ] && [ -e /etc/skel/.Xsession ]; then
  cp -a /etc/skel/.Xsession "${HOME}/.Xsession" 2>/dev/null || true
fi
if [ ! -e "${HOME}/.xsession" ] && [ -e /etc/skel/.xsession ]; then
  cp -a /etc/skel/.xsession "${HOME}/.xsession" 2>/dev/null || true
fi
if [ ! -e "${HOME}/.Xclients" ] && [ -e /etc/skel/.Xclients ]; then
  cp -a /etc/skel/.Xclients "${HOME}/.Xclients" 2>/dev/null || true
fi
if [ -d /etc/skel/.config ] && [ ! -e "${HOME}/.config/pulse/client.conf" ]; then
  cp -a /etc/skel/.config/. "${HOME}/.config/" 2>/dev/null || true
fi

# Stale VNC only — never wipe /tmp/jupyter-server-proxy-* while connecting
pkill -u "$(id -u)" -f '[X]tigervnc' 2>/dev/null || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "${HOME}/.vnc/"*":1.pid" 2>/dev/null || true

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY || true

if [ "$#" -gt 0 ] && [ "$1" != "jupyter" ] && [ "$1" != "jupyter-lab" ] && [ "$1" != "/usr/bin/start-jupyter.sh" ]; then
  exec "$@"
fi

cd "${HOME}"
exec /usr/bin/start-jupyter.sh
