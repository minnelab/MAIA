#!/bin/bash
# OpenShift: unprivileged Jupyter Lab + Desktop proxy + SSH on 2022.
# No root/sudo. Adapts to arbitrary UID/GID (default image 1000670000).
set -euo pipefail

umask 0002

HOME="${HOME:-/home/ubuntu}"
export HOME
if [ -z "${SHELL:-}" ] || [ "${SHELL}" = "/bin/bash" ]; then
  if [ -r /etc/default-shell ]; then
    SHELL="$(cat /etc/default-shell)"
  elif [ -x /bin/zsh ]; then
    SHELL=/bin/zsh
  else
    SHELL=/bin/bash
  fi
fi
export SHELL
export NB_PREFIX="${NB_PREFIX:-/}"
export DISABLE_RDP=1
export JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP="${JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP:-/usr/bin/start-xfce.sh}"
export JUPYTER_RUNTIME_DIR="${JUPYTER_RUNTIME_DIR:-/tmp/jupyter/runtime}"
export JUPYTER_DATA_DIR="${JUPYTER_DATA_DIR:-${HOME}/.local/share/jupyter}"
export PATH="/usr/local/bin:${PATH}"
export TMPDIR="${TMPDIR:-/tmp}"
export DESKTOP_GEOMETRY="${DESKTOP_GEOMETRY:-1280x800}"

# Always per-UID — never reuse image ENV /tmp/runtime-ubuntu (wrong owner)
export XDG_RUNTIME_DIR="/tmp/runtime-$(id -u)"
export XAUTHORITY="${XDG_RUNTIME_DIR}/.Xauthority"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"

_uid="$(id -u)"
_gid="$(id -g)"

# Ensure getpwuid(uid) resolves — otherwise shells show "I have no name!".
# Needs world-writable /etc/passwd (see Dockerfile). Maps name "ubuntu" to this UID:GID.
_need_passwd=0
if ! getent passwd "${_uid}" >/dev/null 2>&1; then
  _need_passwd=1
else
  _cur="$(getent passwd ubuntu 2>/dev/null | head -1 || true)"
  _cur_uid="$(echo "${_cur}" | cut -d: -f3)"
  _cur_gid="$(echo "${_cur}" | cut -d: -f4)"
  if [ "${_cur_uid}" != "${_uid}" ] || [ "${_cur_gid}" != "${_gid}" ]; then
    _need_passwd=1
  fi
fi
if [ "${_need_passwd}" = "1" ]; then
  if [ -w /etc/passwd ]; then
    grep -v '^ubuntu:' /etc/passwd > /tmp/passwd.openshift
    echo "ubuntu:x:${_uid}:${_gid}:OpenShift user:${HOME}:${SHELL}" >> /tmp/passwd.openshift
    cat /tmp/passwd.openshift > /etc/passwd
    rm -f /tmp/passwd.openshift
  else
    echo "entrypoint-openshift: WARNING /etc/passwd not writable — expect 'I have no name!'" >&2
  fi
fi
if [ -w /etc/group ]; then
  if ! getent group "${_gid}" >/dev/null 2>&1; then
    # Prefer name ubuntu for primary GID when free
    if ! getent group ubuntu >/dev/null 2>&1; then
      echo "ubuntu:x:${_gid}:" >> /etc/group
    else
      echo "openshift-${_gid}:x:${_gid}:" >> /etc/group
    fi
  fi
  for g in $(id -G 2>/dev/null); do
    if ! getent group "${g}" >/dev/null 2>&1; then
      echo "openshift-${g}:x:${g}:" >> /etc/group
    fi
  done
else
  echo "entrypoint-openshift: WARNING /etc/group not writable" >&2
fi
unset _cur _cur_uid _cur_gid _need_passwd

export USER="$(id -un 2>/dev/null || echo ubuntu)"
export LOGNAME="${USER}"
export NB_USER="${USER}"

echo "entrypoint-openshift: uid=${_uid} gid=${_gid} user=${USER} passwd_writable=$(test -w /etc/passwd && echo yes || echo no) XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR}"

# Create dirs only — no recursive chmod on PVC (slow on Ceph/NFS)
mkdir -p \
  "${HOME}/Desktop" \
  "${HOME}/Documents" \
  "${HOME}/Tutorials" \
  "${HOME}/.config" \
  "${HOME}/.local/share/jupyter/runtime" \
  "${HOME}/.local/share/sshd" \
  "${HOME}/.jupyter" \
  "${HOME}/.vnc" \
  "${HOME}/.ssh" \
  "${JUPYTER_RUNTIME_DIR}" \
  "${JUPYTER_DATA_DIR}" \
  "${XDG_RUNTIME_DIR}" \
  "${XDG_CACHE_HOME}" \
  /tmp/.X11-unix \
  /tmp/jupyter

chmod 1777 /tmp/.X11-unix 2>/dev/null || true
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true
chmod g+rwX \
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

# Seed XFCE session files on empty PVC
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

# Stale VNC only — never wipe /tmp/jupyter-server-proxy-*
pkill -u "${_uid}" -f '[X]tigervnc' 2>/dev/null || true
pkill -u "${_uid}" -f '[X]vnc' 2>/dev/null || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "${HOME}/.vnc/"*":1.pid" 2>/dev/null || true

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY || true
unset _uid _gid

# SSH in background so Jupyter is not delayed
if [ -f /usr/bin/start-sshd-unprivileged.sh ]; then
  ( /usr/bin/start-sshd-unprivileged.sh || echo "entrypoint: sshd start failed (continuing)" >&2 ) &
fi

if [ "$#" -gt 0 ] && [ "$1" != "jupyter" ] && [ "$1" != "jupyter-lab" ] && [ "$1" != "/usr/bin/start-jupyter.sh" ]; then
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

cd "${HOME}"
exec /usr/bin/start-jupyter.sh
