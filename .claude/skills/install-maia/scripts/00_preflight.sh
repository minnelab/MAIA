#!/usr/bin/env bash
# 00_preflight.sh: read-only checks on the hypervisor and the control node. Changes nothing.
# Usage: 00_preflight.sh [--hypervisor <ssh-alias>] [--branch B] [--name maia-vm] [port flags]
#   Exits 0 if everything passes, 1 if a hard check fails (no usable /dev/kvm, too little RAM/CPU/disk, branch missing).
#   Ports already in use and sudo needing a password are printed as WARN; the agent must ask the user about them.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"

[[ -n "$HYPERVISOR" ]] && run ctl ssh-config <<EOF
ssh -G "$HYPERVISOR" | grep -E '^(hostname|user|port|proxyjump) '
EOF

run hv preflight-host <<EOF
need_mem=\$(( $VM_MEM_GB + 4 )); need_disk=\$(( $VM_DISK_GB + 50 )); fail=0
. /etc/os-release; echo "os: \$PRETTY_NAME  kernel: \$(uname -r)  virt: \$(systemd-detect-virt 2>/dev/null; true)"
echo "nested: \$(cat /sys/module/kvm_*/parameters/nested 2>/dev/null | tr '\n' ' ')"
lscpu | grep -iE '^(Model name|Virtualization)'
cpus=\$(nproc); load=\$(cut -d' ' -f1 /proc/loadavg)
echo "cpus: \$cpus  load1: \$load"
awk -v c=\$cpus -v l=\$load -v n=$VM_CPUS 'BEGIN{ if (c - l < n) { print "FAIL: fewer than " n " idle CPUs"; exit 1 } }' || fail=1
avail=\$(awk '/MemAvailable/{print int(\$2/1048576)}' /proc/meminfo); echo "mem available: \${avail} GiB (need \$need_mem)"
[[ \$avail -ge \$need_mem ]] || { echo "FAIL: not enough free RAM"; fail=1; }
disk=\$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9); echo "disk free under \$HOME: \${disk} GiB (need \$need_disk)"
[[ \$disk -ge \$need_disk ]] || { echo "FAIL: not enough disk"; fail=1; }
dev=\$(findmnt -no SOURCE --target ~ | sed 's/[0-9]*\$//; s/p\$//'); rota=\$(lsblk -dno ROTA "\$dev" 2>/dev/null | head -1 | tr -d " ")
echo "VM disk: \$dev rotational=\${rota:-?} (model: \$(lsblk -dno MODEL "\$dev" 2>/dev/null | head -1))"
[[ "\$rota" == 1 && "$VM_DISK_CACHE" != unsafe ]] && echo "WARN: rotational disk, so DB init in MAIA will outlast liveness probes. Ask the user about --disk-cache unsafe"
ls -l /dev/kvm || { echo "FAIL: no /dev/kvm (do not fall back to TCG)"; fail=1; }
id -nG | tr ' ' '\n' | grep -qx kvm && echo "kvm group: yes" || echo "kvm group: no"
python3 -c 'import os; os.close(os.open("/dev/kvm", os.O_RDWR))' 2>/dev/null && echo "kvm open: OK" \
  || { echo "FAIL: cannot open /dev/kvm. Ask the user to run: sudo usermod -aG kvm \$USER (then reconnect)"; fail=1; }
P=\$(pgrep -u \$USER -x systemd | head -1); kg=\$(getent group kvm | cut -d: -f3)
if [[ -n "\$P" ]] && ! grep -E '^Groups:' /proc/\$P/status | grep -qw "\$kg"; then
  echo "FAIL: systemd --user manager (pid \$P) predates kvm group membership, so the unit can't open /dev/kvm. Ask the user: sudo systemctl restart user@\$(id -u).service"; fail=1
else echo "user manager has kvm group: yes"; fi
sudo -n true 2>/dev/null && echo "sudo: passwordless" || echo "WARN: sudo needs a password, so any host change has to be run by the user"
echo "linger: \$(loginctl show-user \$USER -p Linger --value 2>/dev/null)"
echo "tools: smolvm=\$(command -v smolvm || ls ~/.local/bin/smolvm 2>/dev/null || echo -) qemu=\$(command -v qemu-system-x86_64 || echo -) cloud-localds=\$(command -v cloud-localds || echo -)"
echo "--- workloads"; ps -eo user,%cpu,rss,comm --sort=-rss | head -6
docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | head || true
pgrep -a qemu-system || echo "no qemu processes"
for p in $SSH_PORT $HTTPS_PORT $HTTP_PORT $API_PORT; do
  ss -ltnH "sport = :\$p" | grep -q . && echo "WARN: port \$p in use on hypervisor, so pick another (--*-port)" || echo "port \$p free"
done
exit \$fail
EOF

run ctl preflight-branch <<EOF
cd "$SKILL_DIR/../../.."
sha=\$(git ls-remote origin "refs/heads/$MAIA_BRANCH" | cut -f1)
[[ -n "\$sha" ]] || { echo "FAIL: branch $MAIA_BRANCH not on origin"; exit 1; }
echo "branch $MAIA_BRANCH = \$sha (local HEAD \$(git rev-parse HEAD))"
n=\$(git status --porcelain | wc -l); [[ \$n -eq 0 ]] || echo "WARN: \$n local uncommitted changes are NOT part of the install (it pulls from GitHub)"
command -v ansible-playbook >/dev/null && ansible --version | head -1 || { echo "FAIL: ansible not on control node"; exit 1; }
test -r "$SSH_PUBKEY" && echo "pubkey: $SSH_PUBKEY" || { echo "FAIL: no $SSH_PUBKEY"; exit 1; }
ssh -G "$GUEST" | grep -E '^(hostname|port|user|proxyjump) ' || true
EOF
echo "PREFLIGHT OK"
