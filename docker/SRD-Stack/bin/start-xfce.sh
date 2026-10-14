#!/bin/sh
# XFCE session for jupyter-remote-desktop-proxy (TigerVNC).
# Matches upstream default: dbus-launch + xfce4-session.
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
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"

mkdir -p \
  "${XDG_CONFIG_HOME}" \
  "${XDG_DATA_HOME}" \
  "${XDG_CACHE_HOME}" \
  "${XDG_RUNTIME_DIR}" \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/.vnc" 2>/dev/null || true
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true

# Upstream jupyter-remote-desktop-proxy uses: dbus-launch xfce4-session
if command -v dbus-launch >/dev/null 2>&1; then
  exec dbus-launch --exit-with-session xfce4-session
fi
if command -v startxfce4 >/dev/null 2>&1; then
  exec startxfce4
fi
exec xfce4-session
