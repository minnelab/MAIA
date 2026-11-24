#!/usr/bin/env bash
# 10_feasibility_smolvm.sh: throwaway smolvm probe (maia-probe). Writes GO or NO-GO to $STATE_DIR/smolvm_feasibility.
# Usage: 10_feasibility_smolvm.sh [--hypervisor <ssh-alias>]
# Reference result (smolvm 1.14.1, flem, 2026-11-24): NO-GO. See references/smolvm.md.
# Needs smolvm on the hypervisor (~/.local/bin/smolvm). Use 05_install_smolvm.sh, which asks for approval.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
SV='PATH=$HOME/.local/bin:$PATH smolvm'

run hv smolvm-probe-create <<EOF
$SV machine create --name maia-probe --image ubuntu:24.04 --cpus $VM_CPUS --mem $(( VM_MEM_GB * 1024 )) --storage $VM_DISK_GB --overlay 40 --net | tail -2
$SV machine start --name maia-probe | tail -1
EOF

set +e
run hv smolvm-probe-checks <<EOF
X() { $SV machine exec --name maia-probe -- sh -c "\$1"; }
X 'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null; apt-get install -y -qq iptables iproute2 systemd curl ca-certificates >/dev/null 2>&1; true'
res=\$(X '
  echo "pid1=\$(cat /proc/1/comm) kernel=\$(uname -r)"
  grep -qw overlay /proc/filesystems && echo overlay=ok || echo overlay=MISSING
  grep -qw nfs /proc/filesystems && echo nfs_client=ok || echo nfs_client=MISSING
  grep -qw nfsd /proc/filesystems && echo nfsd=ok || echo nfsd=MISSING
  test -e /proc/sys/net/bridge/bridge-nf-call-iptables && echo br_netfilter=ok || echo br_netfilter=MISSING
  iptables-nft -t nat -N PROBE >/dev/null 2>&1 && echo iptables_nat=ok || echo iptables_nat=MISSING
  ip link add vxp type vxlan id 42 dstport 4789 dev \$(ls /sys/class/net | grep -v "^lo\$" | head -1) 2>/dev/null && echo vxlan=ok || echo vxlan=MISSING
  ip route | grep -q "^default" && echo default_route=ok || echo default_route=MISSING
  s=\$(systemctl is-system-running 2>&1); [ "\$s" = running ] || [ "\$s" = degraded ] && echo systemd=ok || echo systemd=\$s
')
echo "\$res"
echo "\$res" | grep -qE 'MISSING|systemd=(offline|unknown)' && echo VERDICT=NO-GO || echo VERDICT=GO
EOF
set -e
verdict=$(grep -ho 'VERDICT=[A-Z-]*' "$(ls -t "$LOG_DIR"/*-smolvm-probe-checks.log | head -1)" | tail -1 | cut -d= -f2)

run hv smolvm-probe-delete <<EOF
$SV machine stop --name maia-probe >/dev/null 2>&1 || true
$SV machine delete --name maia-probe -f 2>/dev/null </dev/null || $SV machine delete --name maia-probe </dev/null
$SV machine ls
EOF
state_set smolvm_feasibility "${verdict:-NO-GO}"
echo "smolvm feasibility: ${verdict:-NO-GO}  ($STATE_DIR/smolvm_feasibility)"
