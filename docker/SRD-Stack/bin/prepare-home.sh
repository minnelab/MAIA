#!/bin/bash
# Prepare /home/ubuntu when it is backed by a PVC (empty volume hides image home).
set -euo pipefail

HOME="${HOME:-/home/ubuntu}"
export HOME
umask 0002

run_priv() {
  if [ "$(id -u)" = "0" ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo "$@"
  else
    # OpenShift unprivileged: best-effort as current UID (dirs are g+rwX / fsGroup 0)
    "$@"
  fi
}

export JUPYTER_RUNTIME_DIR="${JUPYTER_RUNTIME_DIR:-/tmp/jupyter/runtime}"
export JUPYTER_DATA_DIR="${JUPYTER_DATA_DIR:-${HOME}/.local/share/jupyter}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"
# xrdp/Xorg expect the MIT-MAGIC-COOKIE in $HOME/.Xauthority (same as working SRD).
# Do NOT relocate XAUTHORITY to tmpfs — that causes Guacamole black screens.
export XAUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"

run_priv mkdir -p "${JUPYTER_RUNTIME_DIR}" "${XDG_RUNTIME_DIR}" /tmp/jupyter
run_priv chown -R ubuntu:0 "${JUPYTER_RUNTIME_DIR}" "${XDG_RUNTIME_DIR}" /tmp/jupyter 2>/dev/null || true
run_priv chmod 0700 "${JUPYTER_RUNTIME_DIR}" "${XDG_RUNTIME_DIR}" 2>/dev/null || true

run_priv mkdir -p \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/Tutorials" \
  "${HOME}/.config" \
  "${HOME}/.local/share/jupyter/runtime" \
  "${HOME}/.jupyter" \
  "${HOME}/.vnc" \
  "${JUPYTER_DATA_DIR}"

run_priv chown -R ubuntu:0 \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/Tutorials" \
  "${HOME}/.config" \
  "${HOME}/.local" \
  "${HOME}/.jupyter" \
  "${HOME}/.vnc" \
  2>/dev/null || true
run_priv chmod -R g+rwX \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/Tutorials" \
  "${HOME}/.config" \
  "${HOME}/.local" \
  "${HOME}/.jupyter" \
  "${HOME}/.vnc" \
  2>/dev/null || true
run_priv chown ubuntu:0 "${HOME}" 2>/dev/null || true
run_priv chmod 2775 "${HOME}" 2>/dev/null || true

# Stale lock only — keep/create cookie file where xrdp expects it
rm -f "${HOME}/.Xauthority.lock" 2>/dev/null || true
touch "${HOME}/.Xauthority" 2>/dev/null || true
chown ubuntu:0 "${HOME}/.Xauthority" 2>/dev/null || true

# Seed session files like docker/SRD (PVC often empty; refresh broken Stack starters)
seed_session() {
  local name="$1"
  local dest="${HOME}/${name}"
  local src="/etc/skel/${name}"
  [ -e "${src}" ] || return 0
  if [ ! -e "${dest}" ] \
     || grep -qE 'startwm\.sh|/usr/bin/startxfce4' "${dest}" 2>/dev/null \
     || ! grep -q 'xfce4-session' "${dest}" 2>/dev/null; then
    cp -a "${src}" "${dest}" || true
  fi
}
seed_session .Xsession
seed_session .xsession
seed_session .Xclients
if [ -d /etc/skel/.config ] && [ ! -e "${HOME}/.config/pulse/client.conf" ]; then
  mkdir -p "${HOME}/.config"
  cp -a /etc/skel/.config/. "${HOME}/.config/" 2>/dev/null || true
fi
chmod 0755 "${HOME}/.xsession" 2>/dev/null || true
chown -R ubuntu:0 \
  "${HOME}/.Xsession" "${HOME}/.xsession" "${HOME}/.Xclients" "${HOME}/.config" \
  2>/dev/null || true

# Seed zsh/tmux/nvim from the image template (PVC-safe; no package installs)
if [ -x /etc/install_zsh.sh ]; then
  /etc/install_zsh.sh configure || true
fi
# Use build-time gitstatusd cache (powerlevel10k); works even with an old ~/.zshrc on PVC.
# Clear GITSTATUS_DAEMON — it forces build.info's version and mismatches install.info.
if [ -d /opt/gitstatus ]; then
  unset GITSTATUS_DAEMON
  export GITSTATUS_CACHE_DIR=/opt/gitstatus
fi
