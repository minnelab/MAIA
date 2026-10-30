#!/bin/bash
# User-mode OpenSSH (no root/sudo). Keys+config under $HOME; listens on SSH_PORT (2022).
# Also starts an IPv6 loopback bridge so `oc port-forward` (dials [::1]) works.
set -euo pipefail

if [ "${DISABLE_SSH:-0}" = "1" ] || [ "${DISABLE_SSH:-}" = "true" ]; then
  echo "start-sshd-unprivileged: DISABLE_SSH set, skipping"
  exit 0
fi

if [ -x /usr/sbin/sshd ]; then
  SSHD_BIN=/usr/sbin/sshd
elif command -v sshd >/dev/null 2>&1; then
  SSHD_BIN="$(command -v sshd)"
else
  echo "start-sshd-unprivileged: sshd not installed, skipping" >&2
  exit 0
fi

HOME="${HOME:-/home/ubuntu}"
SSH_PORT="${SSH_PORT:-2022}"
SSH_DIR="${SSH_DIR:-${HOME}/.local/share/sshd}"
mkdir -p "${SSH_DIR}" "${HOME}/.ssh"
chmod 700 "${SSH_DIR}" "${HOME}/.ssh" 2>/dev/null || true

for t in rsa ecdsa ed25519; do
  key="${SSH_DIR}/ssh_host_${t}_key"
  if [ ! -f "${key}" ]; then
    ssh-keygen -f "${key}" -N '' -t "${t}" >/dev/null
  fi
  chmod 600 "${key}" 2>/dev/null || true
done

if [ -n "${SSH_PUBLIC_KEY:-}" ]; then
  auth="${HOME}/.ssh/authorized_keys"
  touch "${auth}"
  chmod 600 "${auth}" 2>/dev/null || true
  grep -qxF "${SSH_PUBLIC_KEY}" "${auth}" 2>/dev/null || echo "${SSH_PUBLIC_KEY}" >> "${auth}"
fi

if [ ! -f /etc/ssh/moduli ] && [ -f /ssh_orig/moduli ] && [ -w /etc/ssh ]; then
  cp /ssh_orig/moduli /etc/ssh/moduli 2>/dev/null || true
fi

CONFIG="${SSH_DIR}/sshd_config"
cat > "${CONFIG}" <<EOF
Port ${SSH_PORT}
AddressFamily inet
ListenAddress 0.0.0.0
HostKey ${SSH_DIR}/ssh_host_rsa_key
HostKey ${SSH_DIR}/ssh_host_ecdsa_key
HostKey ${SSH_DIR}/ssh_host_ed25519_key
PidFile ${SSH_DIR}/sshd.pid
AuthorizedKeysFile .ssh/authorized_keys
PasswordAuthentication yes
PubkeyAuthentication yes
PermitRootLogin no
PermitEmptyPasswords no
KbdInteractiveAuthentication no
UsePAM no
StrictModes no
X11Forwarding no
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp internal-sftp
EOF

if [ -f "${SSH_DIR}/sshd.pid" ]; then
  old="$(cat "${SSH_DIR}/sshd.pid" 2>/dev/null || true)"
  if [ -n "${old}" ] && kill -0 "${old}" 2>/dev/null \
     && tr '\0' ' ' < "/proc/${old}/cmdline" 2>/dev/null | grep -q sshd; then
    echo "start-sshd-unprivileged: sshd already running (pid ${old})"
  else
    rm -f "${SSH_DIR}/sshd.pid"
    old=""
  fi
else
  old=""
fi

if [ -z "${old:-}" ]; then
  "${SSHD_BIN}" -t -f "${CONFIG}"
  "${SSHD_BIN}" -f "${CONFIG}" -E "${SSH_DIR}/sshd.log"
  sleep 0.3
  if [ -f "${SSH_DIR}/sshd.pid" ] && kill -0 "$(cat "${SSH_DIR}/sshd.pid")" 2>/dev/null; then
    echo "start-sshd-unprivileged: sshd on 0.0.0.0:${SSH_PORT}"
  else
    echo "start-sshd-unprivileged: sshd failed — ${SSH_DIR}/sshd.log:" >&2
    cat "${SSH_DIR}/sshd.log" >&2 || true
    exit 1
  fi
fi

# oc port-forward dials [::1]:PORT inside the pod
BRIDGE_PID="${SSH_DIR}/ssh-ipv6-bridge.pid"
if [ -f "${BRIDGE_PID}" ]; then
  bpid="$(cat "${BRIDGE_PID}" 2>/dev/null || true)"
  if [ -n "${bpid}" ] && kill -0 "${bpid}" 2>/dev/null; then
    echo "start-sshd-unprivileged: ipv6 bridge already running"
    exit 0
  fi
  rm -f "${BRIDGE_PID}"
fi

if [ -f /usr/bin/ssh-ipv6-bridge.py ]; then
  SSH_PORT="${SSH_PORT}" python3 /usr/bin/ssh-ipv6-bridge.py \
    >>"${SSH_DIR}/ssh-ipv6-bridge.log" 2>&1 &
  echo $! > "${BRIDGE_PID}"
  sleep 0.2
  if kill -0 "$(cat "${BRIDGE_PID}")" 2>/dev/null; then
    echo "start-sshd-unprivileged: ipv6 bridge [::1]:${SSH_PORT} -> 127.0.0.1:${SSH_PORT}"
  else
    echo "start-sshd-unprivileged: ipv6 bridge failed (sshd still on IPv4)" >&2
    cat "${SSH_DIR}/ssh-ipv6-bridge.log" >&2 || true
  fi
fi
