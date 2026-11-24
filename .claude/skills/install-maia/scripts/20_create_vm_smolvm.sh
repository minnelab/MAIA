#!/usr/bin/env bash
# 20_create_vm_smolvm.sh: smolvm backend. It only proceeds when 10_feasibility_smolvm.sh recorded GO.
# Reference run: NO-GO (TSI networking has no default route, so k3s dies; the libkrunfw kernel has no nfs/nfsd;
# systemd is not PID 1). This path has NOT been exercised end to end. Use 21_create_vm_qemu.sh instead.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
if [[ "$(state_get smolvm_feasibility)" != GO ]]; then
  echo "smolvm feasibility is '$(state_get smolvm_feasibility)' (not GO). Use 21_create_vm_qemu.sh. See references/smolvm.md."
  exit 2
fi
echo "smolvm reported GO, but this path is unverified. Follow references/smolvm.md and record every command in RUNBOOK.md."
exit 2
