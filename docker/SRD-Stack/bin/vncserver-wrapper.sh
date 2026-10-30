#!/bin/bash
# Wrapper around TigerVNC /usr/bin/vncserver for OpenShift.
# jupyter-remote-desktop-proxy detects TigerVNC by scanning this file for
# the string "tigervnc". Ensures -rfbunixpath parent dir exists (Xvnc ENOENT
# otherwise) and uses a per-UID XDG_RUNTIME_DIR.
#
# GPU nodes: NVIDIA device-plugin injects 10_nvidia.json + host EGL libs.
# Xtigervnc then segfaults in GlxExtensionInit (libnvidia-egl-gbm + swrast).
# Keep GLX (needed by Slicer/Qt) but force Mesa software EGL for this process.
#
# tigervnc
set -euo pipefail

REAL_VNCSERVER="${REAL_VNCSERVER:-/usr/bin/vncserver}"
DESKTOP_GEOMETRY="${DESKTOP_GEOMETRY:-1280x800}"

export XDG_RUNTIME_DIR="/tmp/runtime-$(id -u)"
mkdir -p "${XDG_RUNTIME_DIR}" /tmp/.X11-unix
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
chmod 1777 /tmp/.X11-unix 2>/dev/null || true
export XAUTHORITY="${XAUTHORITY:-${XDG_RUNTIME_DIR}/.Xauthority}"
touch "${XAUTHORITY}" 2>/dev/null || true

# Do not load NVIDIA EGL into Xtigervnc (CUDA apps are unaffected)
if [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ]; then
  export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
fi
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"

# Prefer a writable Mesa-aware XFCE starter when present (live-patched pods)
USER_XSTARTUP="${HOME:-/home/ubuntu}/.local/bin/start-xfce.sh"

out=()
skip_next=0
for a in "$@"; do
  if [ "${skip_next}" = "1" ]; then
    skip_next=0
    continue
  fi
  if [ "${a}" = "-geometry" ]; then
    skip_next=1
    continue
  fi
  if [ "${a}" = "-xstartup" ]; then
    skip_next=1
    if [ -x "${USER_XSTARTUP}" ]; then
      out+=("-xstartup" "${USER_XSTARTUP}")
    else
      out+=("-xstartup")
      skip_next=0
    fi
    continue
  fi
  out+=("${a}")
done

i=0
while [ "$i" -lt "${#out[@]}" ]; do
  if [ "${out[$i]}" = "-rfbunixpath" ] && [ $((i + 1)) -lt "${#out[@]}" ]; then
    sock="${out[$((i + 1))]}"
    sock="${sock#\'}"; sock="${sock%\'}"
    sock="${sock#\"}"; sock="${sock%\"}"
    parent="$(dirname "${sock}")"
    if [ -n "${parent}" ] && [ "${parent}" != "." ]; then
      mkdir -p "${parent}"
      chmod 700 "${parent}" 2>/dev/null || true
    fi
  fi
  i=$((i + 1))
done

exec "${REAL_VNCSERVER}" "${out[@]}" -geometry "${DESKTOP_GEOMETRY}"
