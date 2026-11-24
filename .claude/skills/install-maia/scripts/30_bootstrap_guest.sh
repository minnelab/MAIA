#!/usr/bin/env bash
# 30_bootstrap_guest.sh: minimal guest prep over SSH (no hypervisor changes). Reboots if the upgrade needs it.
# Usage: 30_bootstrap_guest.sh [--guest maia-vm]
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
run guest guest-bootstrap <<'EOF'
sudo -n true || { echo "guest user needs NOPASSWD sudo"; exit 1; }
export DEBIAN_FRONTEND=noninteractive
sudo -E apt-get update -qq
sudo -E apt-get -y -qq -o Dpkg::Options::=--force-confold upgrade
sudo -E apt-get install -y -qq jq unzip curl git python3-pip >/dev/null
sudo timedatectl set-timezone Europe/Stockholm
ip -4 route show default; hostname -I
nproc; free -m | sed -n 2p; df -h / | tail -1
test -f /var/run/reboot-required && echo REBOOT_REQUIRED || echo no-reboot-needed
EOF
if grep -q REBOOT_REQUIRED "$(ls -t "$LOG_DIR"/*-guest-bootstrap.log | head -1)"; then
  run guest guest-reboot <<'EOF' || true
sudo systemctl reboot
EOF
  run ctl guest-wait-after-reboot <<EOF
sleep 20; for i in \$(seq 1 60); do ssh -n ${GUEST_SSH_OPTS[*]} $GUEST 'uptime' 2>/dev/null && exit 0; sleep 5; done; exit 1
EOF
fi
