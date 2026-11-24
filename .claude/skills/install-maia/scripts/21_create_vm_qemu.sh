#!/usr/bin/env bash
# 21_create_vm_qemu.sh: QEMU/KVM Ubuntu 24.04 guest, run as a systemd --user unit on the hypervisor.
# Usage: 21_create_vm_qemu.sh [--hypervisor <ssh-alias>] [--name maia-vm] [port flags] [--approve-host-changes]
#   Stage A (no approval needed): VM files in ~/.maia-vm/<name>/ on the hypervisor, i.e. the verified cloud image,
#           a qcow2 overlay and the cloud-init seed. The guest user is 'maia' with NOPASSWD sudo and $SSH_PUBKEY.
#   Stage B (--approve-host-changes): ~/.config/systemd/user/<name>.service, then enable --now.
#           Needs qemu-system-x86, qemu-utils, cloud-image-utils (apt, done by the user) and linger
#           (`sudo loginctl enable-linger $USER`) so the VM survives SSH logout.
# Every port forward binds to 127.0.0.1 on the hypervisor only.
# --disk-cache unsafe for HDD hypervisors (see lib.sh and references/qemu-fallback.md). Changing it restarts the VM.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
IMG_URL=https://cloud-images.ubuntu.com/noble/current
UNIT="$VM_NAME.service"

run hv qemu-prereqs <<EOF
for b in qemu-system-x86_64 qemu-img cloud-localds; do command -v \$b >/dev/null || { echo "missing \$b. Ask the user: sudo apt install -y qemu-system-x86 qemu-utils cloud-image-utils"; exit 1; }; done
python3 -c 'import os; os.close(os.open("/dev/kvm", os.O_RDWR))' || { echo "no /dev/kvm access"; exit 1; }
qemu-system-x86_64 --version | head -1
fail=0
P=\$(pgrep -u \$USER -x systemd | head -1); kg=\$(getent group kvm | cut -d: -f3)
if [[ -n "\$P" ]] && ! grep -E '^Groups:' /proc/\$P/status | grep -qw "\$kg"; then
  echo "FAIL: systemd --user manager (pid \$P) predates kvm group membership, so the unit can't open /dev/kvm. Ask the user: sudo systemctl restart user@\$(id -u).service"; fail=1
else echo "user manager has kvm group: yes"; fi
[[ \$fail -eq 0 ]] || exit 1
[[ "\$(loginctl show-user \$USER -p Linger --value)" == yes ]] || echo "WARN: linger is off, so the VM stops when the last SSH session ends"
EOF

run hv qemu-image <<EOF
D=~/.maia-vm/$VM_NAME; mkdir -p \$D/dl; chmod 700 ~/.maia-vm \$D; cd \$D/dl
curl -fsSLo SHA256SUMS $IMG_URL/SHA256SUMS; curl -fsSLo SHA256SUMS.gpg $IMG_URL/SHA256SUMS.gpg
if [[ -r /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg ]]; then
  gpgv --keyring /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg SHA256SUMS.gpg SHA256SUMS 2>&1 | grep -E 'Good signature' || { echo "SHA256SUMS signature check failed"; exit 1; }
else echo "WARN: ubuntu-cloudimage-keyring missing, so only the checksum is verified"; fi
# quiet pre-check: is a verified image already there? (no 'FAILED open or read' noise on a first run)
if ! grep ' \*\?noble-server-cloudimg-amd64.img\$' SHA256SUMS | sha256sum -c --status - 2>/dev/null; then
  curl -fsSLo noble-server-cloudimg-amd64.img $IMG_URL/noble-server-cloudimg-amd64.img
  grep ' \*\?noble-server-cloudimg-amd64.img\$' SHA256SUMS | sha256sum -c -   # REQUIRED
else echo "noble-server-cloudimg-amd64.img: OK (already downloaded)"; fi
cd \$D
if [[ ! -f $VM_NAME.qcow2 ]]; then
  # A full copy rather than a backing-file overlay: "current" gets replaced upstream, and the disk must not depend on it.
  qemu-img convert -O qcow2 dl/noble-server-cloudimg-amd64.img $VM_NAME.qcow2
  qemu-img resize $VM_NAME.qcow2 ${VM_DISK_GB}G
fi
qemu-img info -U $VM_NAME.qcow2 | grep -E 'virtual size|disk size'   # -U: works while the VM holds the lock
EOF

PUBKEY="$(cat "$SSH_PUBKEY")"
run hv qemu-seed <<EOF
D=~/.maia-vm/$VM_NAME; cd \$D
# Keep an existing seed: a new instance-id would make cloud-init run again (and regenerate host keys) on the next boot.
if [[ -f seed.iso ]]; then echo "seed.iso exists, keeping it"; ls -l seed.iso; exit 0; fi
cat > user-data <<'UD'
#cloud-config
hostname: $VM_NAME
manage_etc_hosts: true
users:
  - name: maia
    groups: [sudo]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: true
    ssh_authorized_keys:
      - $PUBKEY
ssh_pwauth: false
growpart: {mode: auto, devices: ["/"]}
UD
printf 'instance-id: %s-%s\nlocal-hostname: %s\n' $VM_NAME \$(date +%s) $VM_NAME > meta-data
cloud-localds seed.iso user-data meta-data
cat > qmp-powerdown.py <<'PY'
# ACPI powerdown through QMP. systemd waits TimeoutStopSec for the guest to halt before it sends SIGTERM.
import json, socket, sys, time
s = socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.recv(4096)
for cmd in ("qmp_capabilities", "system_powerdown"):
    s.sendall(json.dumps({"execute": cmd}).encode()); s.recv(4096)
time.sleep(1)
PY
ls -l seed.iso qmp-powerdown.py
EOF

UNIT_TEXT="[Unit]
Description=MAIA VM $VM_NAME (QEMU/KVM, managed by install-maia)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/.maia-vm/$VM_NAME
ExecStart=/usr/bin/qemu-system-x86_64 -name $VM_NAME -machine q35,accel=kvm -cpu host -smp $VM_CPUS -m ${VM_MEM_GB}G \\
  -drive file=%h/.maia-vm/$VM_NAME/$VM_NAME.qcow2,if=virtio,format=qcow2,discard=unmap,cache=$VM_DISK_CACHE \\
  -drive file=%h/.maia-vm/$VM_NAME/seed.iso,if=virtio,format=raw,readonly=on \\
  -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:$SSH_PORT-:22,hostfwd=tcp:127.0.0.1:$HTTPS_PORT-:443,hostfwd=tcp:127.0.0.1:$HTTP_PORT-:80,hostfwd=tcp:127.0.0.1:$API_PORT-:6443 \\
  -display none -serial file:%h/.maia-vm/$VM_NAME/console.log \\
  -qmp unix:%h/.maia-vm/$VM_NAME/qmp.sock,server=on,wait=off
ExecStop=/usr/bin/python3 %h/.maia-vm/$VM_NAME/qmp-powerdown.py %h/.maia-vm/$VM_NAME/qmp.sock
TimeoutStopSec=180
Restart=no

[Install]
WantedBy=default.target"

echo "=== Stage B plan on $(hv_label): write ~/.config/systemd/user/$UNIT, then systemctl --user daemon-reload && enable --now $UNIT"
echo "$UNIT_TEXT"
require_approval

UNIT_B64="$(printf '%s\n' "$UNIT_TEXT" | base64 -w0)"
run hv qemu-unit <<EOF
mkdir -p ~/.config/systemd/user
F=~/.config/systemd/user/$UNIT; was=\$(systemctl --user is-active $UNIT 2>/dev/null || true)
echo $UNIT_B64 | base64 -d > \$F.new
if [[ -f \$F ]] && cmp -s \$F \$F.new; then rm \$F.new; changed=0; else mv \$F.new \$F; changed=1; fi
systemctl --user daemon-reload
systemctl --user enable --now $UNIT
# The unit changed (e.g. more vCPUs) while the VM was running: restart (ExecStop = ACPI powerdown, then a fresh qemu)
if [[ \$changed == 1 && \$was == active ]]; then echo "unit changed, so restarting $UNIT"; systemctl --user restart $UNIT; fi
sleep 3; systemctl --user --no-pager status $UNIT | head -5
ss -ltnH | grep -E ':($SSH_PORT|$HTTPS_PORT|$HTTP_PORT|$API_PORT)\\b'
EOF

run ctl guest-wait-ssh <<EOF
for i in \$(seq 1 60); do ssh -n ${GUEST_SSH_OPTS[*]} $GUEST true 2>/dev/null && { echo "ssh up after ~\$((i*5))s"; break; }; sleep 5; done
ssh -n ${GUEST_SSH_OPTS[*]} $GUEST 'cloud-init status --wait; hostname; nproc; free -g | sed -n 2p; df -h / | tail -1'
EOF
state_set backend qemu
