#!/bin/sh
# XFCE session for jupyter-remote-desktop-proxy (TigerVNC) in unprivileged pods.
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

export HOME="${HOME:-/home/ubuntu}"
export USER="${USER:-ubuntu}"
export XDG_SESSION_TYPE=x11
export DESKTOP_SESSION=xfce
export XDG_CURRENT_DESKTOP=XFCE
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
export NO_AT_BRIDGE=1
export GTK_A11Y=none

# Software OpenGL for Qt/VTK apps (Slicer, napari, …) over VNC.
# On GPU nodes, NVIDIA EGL must not be used for the desktop X session.
if [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ]; then
  export __EGL_VENDOR_LIBRARY_FILENAMES="${__EGL_VENDOR_LIBRARY_FILENAMES:-/usr/share/glvnd/egl_vendor.d/50_mesa.json}"
fi
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
export MESA_GL_VERSION_OVERRIDE="${MESA_GL_VERSION_OVERRIDE:-3.3}"

# Per-UID runtime (image ENV /tmp/runtime-ubuntu is owned by the build UID)
_uid="$(id -u)"
_runtime_owner="$(stat -c '%u' "${XDG_RUNTIME_DIR}" 2>/dev/null || echo "")"
if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ "${_runtime_owner}" != "${_uid}" ]; then
  export XDG_RUNTIME_DIR="/tmp/runtime-${_uid}"
fi
unset _uid _runtime_owner

mkdir -p \
  "${XDG_CONFIG_HOME}" \
  "${XDG_DATA_HOME}" \
  "${XDG_CACHE_HOME}" \
  "${XDG_RUNTIME_DIR}" \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/.vnc" \
  /tmp/.X11-unix 2>/dev/null || true
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
chmod 1777 /tmp/.X11-unix 2>/dev/null || true

if command -v dbus-launch >/dev/null 2>&1; then
  exec dbus-launch --exit-with-session xfce4-session
fi
if command -v startxfce4 >/dev/null 2>&1; then
  exec startxfce4
fi
exec xfce4-session
