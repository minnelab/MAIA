# smolvm backend: feasibility result

**Result: NO-GO** (smolvm 1.14.1, libkrunfw guest kernel 6.12.95, hypervisor flem / Ubuntu 24.04, 2026-11-24).
`scripts/10_feasibility_smolvm.sh` repeats the probe. Re-run it when smolvm is upgraded. If it ever reports GO,
the smolvm path still has to be built and recorded before `20_create_vm_smolvm.sh` is trusted.

## What the probe ran
```
smolvm machine create --name maia-probe --image ubuntu:24.04 --cpus 4 --mem 16384 --storage 150 --overlay 40 --net
smolvm machine start --name maia-probe
smolvm machine exec --name maia-probe -- sh -c '…checks…'
```

| Check | Result | Why it matters to MAIA |
|---|---|---|
| PID 1 | `init` (smolvm agent); the image runs as a container under it | `systemctl is-system-running` → `offline`. The k3s role uses `service: k3s`, and prepare_hosts uses ufw and nfs-server units |
| overlay fs | ✅ | containerd snapshotter |
| `nfs` / `nfsd` in /proc/filesystems | ❌ both missing, no /lib/modules, no /proc/config.gz | the prepare_hosts NFS server and `maia-core-nfs-provisioner` (NFS client mounts in kubelet) can't work |
| iptables nat (legacy + nft), conntrack, comment match | ✅ | kube-proxy, flannel |
| bridge, veth, vxlan, bridge-nf sysctls | ✅ | flannel vxlan |
| network | TSI (`--net`): only `dummy0 203.0.113.1/24`, **no default route** | k3s: `level=fatal msg="… no default routes found in /proc/net/route"` |
| IPVS | not present | not required (k3s uses iptables) |

Not tried: `--net-backend virtio-net`. It might give a default route, but it fixes neither the missing NFS
support nor PID-1 systemd, so the verdict stands.

## Install (if smolvm is wanted anyway, e.g. for the probe)
`scripts/05_install_smolvm.sh --hypervisor <alias> --approve-host-changes`: pinned 1.14.1, checked against
`checksums.sha256` from the release and the GitHub asset digest
`e91786c12808ce87655aa190eb5f6692672cd659a89367b5ec18dace5756af2f`. Installs to `~/.smolvm`, linked from `~/.local/bin`, no sudo.
