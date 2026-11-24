#!/usr/bin/env bash
# 90_teardown.sh: delete ONLY this VM and its files: the <name>.service user unit and ~/.maia-vm/<name>/ on the hypervisor.
# Control node: removes known_hosts/inventory/tunnel state; keeps secrets.env unless --purge-secrets.
# Usage: 90_teardown.sh [--hypervisor <ssh-alias>] [--name maia-vm] [--purge-secrets] --approve-host-changes
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
PURGE=0; for a in "${REST[@]+"${REST[@]}"}"; do [[ $a == --purge-secrets ]] && PURGE=1; done
[[ "$VM_NAME" =~ ^[a-z0-9][a-z0-9-]+$ ]] || { echo "bad VM name"; exit 2; }
echo "Will run on $(hv_label): systemctl --user disable --now $VM_NAME.service; rm ~/.config/systemd/user/$VM_NAME.service; rm -rf ~/.maia-vm/$VM_NAME"
echo "Will remove on ctl: $STATE_DIR/{known_hosts,inventory.ini,secrets.yml,tunnel.sock}$([[ $PURGE == 1 ]] && echo ', secrets.env')"
require_approval
run hv teardown-vm <<EOF
systemctl --user disable --now $VM_NAME.service 2>&1 || true
rm -f ~/.config/systemd/user/$VM_NAME.service; systemctl --user daemon-reload
pgrep -af "qemu-system-x86_64 -name $VM_NAME " && { echo "qemu still running"; exit 1; } || true
test -d ~/.maia-vm/$VM_NAME && rm -rf -- ~/.maia-vm/$VM_NAME
rmdir ~/.maia-vm 2>/dev/null || true
ls -la ~/.maia-vm 2>/dev/null || echo "~/.maia-vm removed"
EOF
rm -f "$STATE_DIR/known_hosts" "$STATE_DIR/inventory.ini" "$STATE_DIR/secrets.yml" "$STATE_DIR/tunnel.sock" "$STATE_DIR/backend" "$STATE_DIR/smolvm_feasibility"
[[ $PURGE == 1 ]] && rm -f "$STATE_DIR/secrets.env"
echo "teardown done"
