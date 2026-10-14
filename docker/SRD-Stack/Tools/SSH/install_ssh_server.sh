#!/bin/bash
# Enable OpenSSH on port 2022 and register it with supervisord.
set -euo pipefail

if ! command -v sshd >/dev/null 2>&1; then
  echo "SSH server is not installed."
  exit 0
fi

if [ ! -f /etc/ssh/sshd_config ]; then
  cp /ssh_orig/sshd_config /etc/ssh/
fi
sed -i 's/^Port 22/#Port 22/' /etc/ssh/sshd_config

[ -f /etc/ssh/ssh_config ] || cp /ssh_orig/ssh_config /etc/ssh/
[ -f /etc/ssh/moduli ] || cp /ssh_orig/moduli /etc/ssh/

[ -f /etc/ssh/ssh_host_rsa_key ] || ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -t rsa
[ -f /etc/ssh/ssh_host_ecdsa_key ] || ssh-keygen -f /etc/ssh/ssh_host_ecdsa_key -N '' -t ecdsa
[ -f /etc/ssh/ssh_host_ed25519_key ] || ssh-keygen -f /etc/ssh/ssh_host_ed25519_key -N '' -t ed25519

mkdir -p /var/run/sshd /etc/ssh/sshd_config.d
cp /etc/ssh-server/sftp.conf /etc/ssh/sshd_config.d/99-sftp.conf

if [ ! -f /etc/supervisor/conf.d/sshd.conf ]; then
  cp /etc/ssh-server/sshd.supervisor.conf /etc/supervisor/conf.d/sshd.conf
fi
