#!/bin/bash
# Start Jupyter Lab using NB_PREFIX as ServerApp.base_url (default /).
set -euo pipefail

export HOME="${HOME:-/home/ubuntu}"
export NB_PREFIX="${NB_PREFIX:-/}"
export JUPYTER_RUNTIME_DIR="${JUPYTER_RUNTIME_DIR:-/tmp/jupyter/runtime}"
export JUPYTER_DATA_DIR="${JUPYTER_DATA_DIR:-${HOME}/.local/share/jupyter}"
# Per-UID runtime (image ENV /tmp/runtime-ubuntu is owned by the build UID)
export XDG_RUNTIME_DIR="/tmp/runtime-$(id -u)"
export JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP="${JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP:-/usr/bin/start-xfce.sh}"
export PATH="/usr/local/bin:${PATH}"
export TMPDIR="${TMPDIR:-/tmp}"

# Cookie on tmpfs for VNC (PVC flock issues)
export XAUTHORITY="${XDG_RUNTIME_DIR}/.Xauthority"

mkdir -p "${XDG_RUNTIME_DIR}" "${HOME}/.vnc" "${JUPYTER_RUNTIME_DIR}" /tmp/.X11-unix
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
chmod 1777 /tmp/.X11-unix 2>/dev/null || true
touch "${XAUTHORITY}" 2>/dev/null || true
export XAUTHORITY XDG_RUNTIME_DIR JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP PATH

# Scrub stale TigerVNC :1 only — never delete /tmp/jupyter-server-proxy-*
pkill -u "$(id -u)" -f '[X]tigervnc' 2>/dev/null || true
pkill -u "$(id -u)" -f '[X]vnc' 2>/dev/null || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "${HOME}/.vnc/"*":1.pid" 2>/dev/null || true
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix 2>/dev/null || true

cd "${HOME}"
exec jupyter lab \
  --ip=0.0.0.0 \
  --port="${JUPYTER_PORT:-8888}" \
  --no-browser \
  --ServerApp.root_dir="${HOME}" \
  --ServerApp.base_url="${NB_PREFIX}" \
  --IdentityProvider.token="${JUPYTER_TOKEN:-}" \
  --ServerApp.password="${JUPYTER_PASSWORD:-}" \
  --ServerApp.allow_origin='*' \
  --ServerApp.allow_remote_access=true
