# QEMU/KVM backend (the backend used by the reference run)

Files on the hypervisor (all under `~/.maia-vm/<name>/`, nothing outside except the user unit):
| File | What |
|---|---|
| `dl/noble-server-cloudimg-amd64.img`, `dl/SHA256SUMS{,.gpg}` | Ubuntu 24.04 cloud image. `gpgv` against `/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg` + `sha256sum -c` (**required**) |
| `<name>.qcow2` | `qemu-img convert` of the image (standalone, no backing file) + `resize 150G`; cloud-init growpart expands / |
| `user-data`, `meta-data`, `seed.iso` | cloud-init NoCloud seed: user `maia`, NOPASSWD sudo, control-node pubkey, no password auth. **Kept on re-runs** (a new instance-id would re-run cloud-init) |
| `qmp-powerdown.py`, `qmp.sock` | ACPI shutdown for `ExecStop` |
| `console.log` | guest serial console: look here first when SSH doesn't come up |
| `~/.config/systemd/user/<name>.service` | the VM process; `enable --now`, `WantedBy=default.target` |

## Persistence: systemd --user unit plus linger
Chosen over `-daemonize`+pidfile so the VM survives SSH logout and hypervisor reboots, and has
`systemctl --user status|stop|start <name>` and `journalctl --user -u <name>`.
Requirements on the hypervisor (done by the user, sudo):
```
sudo apt install -y qemu-system-x86 qemu-utils cloud-image-utils
sudo usermod -aG kvm $USER
sudo loginctl enable-linger $USER
sudo systemctl restart user@$(id -u).service   # ONLY if the user manager was running before the usermod (see troubleshooting)
```

## Size and disk cache
- **8 vCPU** default (`VM_CPUS`). 4 vCPU leaves Keycloak (requests 2 CPU, hardcoded) unschedulable.
- `--disk-cache writeback` (QEMU default, durable) or `unsafe`. On flem (7200 rpm ST2000DM001) guest fsync took 67 ms with writeback,
  and DB first-init (Postgres/MySQL) was killed by liveness probes. With `unsafe`: 1.2 ms. Trade-off: a *hypervisor* crash or power
  loss can corrupt the VM disk. It's fine for a rebuildable VM, but the user decides. Preflight flags rotational disks.
- Changing either rewrites the unit and restarts the VM (ACPI powerdown via QMP, then a fresh qemu).

## Networking
`-nic user` (slirp): guest 10.0.2.15/24, gateway 10.0.2.2. Port forwards bind to **127.0.0.1 on the hypervisor only**:
`2222→22, 8443→443, 8080→80, 16443→6443`. MetalLB's pool is the node IP (10.0.2.15), so traefik's LoadBalancer
IP is the node, and hostfwd :443 reaches traefik. slirp also gives the guest an IPv6 SLAAC address (`fec0::…`), so the node is
dual-stack, which is why config.yaml pins `metallb_ip_pool: <ipv4>-<ipv4>` (see troubleshooting). No bridge, no root, no firewall changes on the hypervisor.
From the control node: `ssh -L 8443:127.0.0.1:8443 <hypervisor>`, then `curl -k --resolve maia.<domain>:8443:127.0.0.1 …`.
