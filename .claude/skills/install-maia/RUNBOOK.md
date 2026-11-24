# install-maia — reference run RUNBOOK

Target: `remote-hypervisor` (hypervisor = `flem`, guest = `maia-vm`, 4 vCPU / 16 GB / 150 GB)
Control node: WSL. Branch: `157-add-tool-for-mcp-server-to-execute-helm-commands-from-dashboard` @ `36e4416`.
Legend: **[WSL]** control node · **[flem]** hypervisor · **[maia-vm]** guest

## Phase 0 — Preflight (2026-11-24, ~2 min, read-only)

| Where | Command | Result |
|---|---|---|
| WSL | `ssh -G flem` | user/host/port/key are resolved from ssh config (not hardcoded) |
| flem | `cat /etc/os-release; uname -r` | Ubuntu 24.04.4 LTS, kernel 6.8.0-124-generic |
| flem | `systemd-detect-virt` | `none` (bare metal); `kvm_intel nested=Y` |
| flem | `nproc` / `lscpu` | 16 CPUs, Xeon E5-2630 v3, VT-x |
| flem | `free -g` | 23 GB total, ~21 GB available (16 + 4 headroom fits, but only by ~1 GB) |
| flem | `df -h ~ /` | /home 466 GB free, / 1.2 TB free → OK (≥200 GB) |
| flem | `ls -l /dev/kvm; id` | `crw-rw---- root:kvm`; user **not** in `kvm` group → **open() EACCES** ❌ |
| flem | `sudo -n true` | **password required** ❌ |
| flem | `loginctl show-user -p Linger` | `Linger=no` |
| flem | `which smolvm qemu-system-x86_64` | neither installed; `~/.local/bin` absent |
| flem | `ps`, `docker ps`, `systemctl … running`, `ss -ltn` | idle (load 0.0); no containers; multipassd running, no VMs up (bridges DOWN); `socat-forward.service` holds `*:443` → 22 |
| flem | `ss -ltn \| grep 2222\|8443\|8080\|16443` | all free on flem |
| WSL | `git ls-remote origin <branch>` | exists, `36e4416` = local HEAD; **160 uncommitted local changes are NOT included** |

**Gate: NO-GO, waiting on the user** (no KVM access, and sudo needs a password).

User actions after Phase 0 (run by the user on flem): `sudo usermod -aG kvm $USER`, `sudo loginctl enable-linger $USER`,
`sudo apt install -y qemu-system-x86 qemu-utils cloud-image-utils`. Then **[WSL]** appended the `Host maia-vm` entry
(User maia, 127.0.0.1:2222, ProxyJump flem) to `~/.ssh/config`, backing it up first to `~/.ssh/config.bak-maia-vm`.

## smolvm install (flem, ~5 s, approved)
| Where | Command | Result |
|---|---|---|
| flem | download `smolvm-1.14.1-linux-x86_64.tar.gz` + `checksums.sha256` from github.com/smol-machines/smolvm v1.14.1 | `sha256sum -c` OK; matches GitHub asset digest `e91786c1…af2f` |
| flem | `tar -xzf … -C ~/.smolvm --strip-components=1; ln -s ~/.smolvm/smolvm ~/.local/bin/smolvm` | `smolvm 1.14.1` |
Encoded as `scripts/05_install_smolvm.sh`.

## Phase 1: smolvm feasibility (flem, ~4 min) → **NO-GO**
| Where | Command | Result |
|---|---|---|
| flem | `smolvm machine create --name maia-probe --image ubuntu:24.04 --cpus 4 --mem 16384 --storage 150 --overlay 40 --net` + `start` | created + running in 22 s |
| flem→probe | `cat /proc/1/comm; uname -r; /proc/filesystems` | pid1=`init` (smolvm agent), kernel 6.12.95 (libkrunfw), overlay ✅, **no nfs, no nfsd** ❌, no /lib/modules, no config.gz |
| flem→probe | iptables-legacy/nft nat, conntrack, comment; bridge; veth; vxlan; bridge-nf sysctls | all ✅ |
| flem→probe | `ip -br link; ip route` | **TSI net: only `dummy0` 203.0.113.1/24, no default route** |
| flem→probe | (a) `apt install systemd; systemctl is-system-running` | `offline` ❌ (the image runs as a container under the agent; systemd is not PID 1) |
| flem→probe | (b) `curl get.k3s.io \| INSTALL_K3S_SKIP_ENABLE=true sh -; k3s server &` | **fatal: `no default routes found in /proc/net/route`** ❌ |
| flem | `smolvm machine stop/delete --name maia-probe` | deleted |
Verdict: NO-GO → QEMU. Details in references/smolvm.md. Encoded as `scripts/10_feasibility_smolvm.sh`.

## Phase 2: QEMU VM (flem). Stage A: files (~20 s)
| Where | Command | Result |
|---|---|---|
| WSL | `scripts/00_preflight.sh --hypervisor flem` | PREFLIGHT OK (kvm open OK, 21 GiB avail, 466 GiB disk, ports free, linger yes) |
| flem | `scripts/21_create_vm_qemu.sh --hypervisor flem` (stage A) | `gpgv: Good signature` on SHA256SUMS; `noble-server-cloudimg-amd64.img: OK`; `qemu-img convert` + `resize 150G`; `cloud-localds seed.iso` |

## Phase 2: QEMU VM. Stage B: unit (approved "enable --now")
| Where | Command | Result |
|---|---|---|
| flem | `21_create_vm_qemu.sh --hypervisor flem --approve-host-changes` | unit enabled, but **qemu: `Could not access KVM kernel module: Permission denied`** |
| flem | `grep Groups /proc/$(pgrep -u $USER -x systemd)/status` | the user manager (started 13 Nov) lacked kvm gid 994 |
| flem (user) | `sudo systemctl restart user@1000.service` | unit restarted, qemu running; ports 2222/8443/8080/16443 on **127.0.0.1 only** |
| WSL→maia-vm | `ssh maia-vm` (ProxyJump flem), `cloud-init status --wait` | `status: done`, 4 vCPU / 15 GiB / 145 GiB |
Script fixes from this phase: `ssh -n` in run blocks; `qemu-img info -U`; seed kept on re-run; restart-on-unit-change.

## Phase 3: guest bootstrap (4 min 14 s + reboot 22 s)
`30_bootstrap_guest.sh` → apt upgrade, base pkgs, TZ; `REBOOT_REQUIRED` → reboot; default route `via 10.0.2.2 dev enp0s2`, IP 10.0.2.15.

## Phase 4: render config (< 1 s)
`40_render_config.sh` → `~/.maia-vm/maia-vm/secrets.env` + `secrets.yml` (0600, WSL), `inventory.ini` (guest user `maia` from `ssh -G maia-vm`).

## Phase 5: install (timings from logs/journal.md)
| Step | Time | Result / what was fixed |
|---|---|---|
| render (ansible-playbook, 24 tasks) | 1 min 19 s first, ~30 s later | OK |
| bootstrap: install_MAIA.sh tooling + prepare_hosts + configure_hosts + install_k3s | 10 min 13 s | ❌ Kyverno ImagePullBackOff: `proxyconnect tcp: dial tcp :3130` → **UPSTREAM proxy_ip null bug**, fixed with `proxy_ip: ""` |
| install_k3s (re-run) | 3 min 10 s | ❌ `k3s kubectl`: `extracting data: permission denied` → k3s data dir owned by maia (verdi parity) |
| install_k3s (re-run) | 4 min 35 s | ✅ (argocd 7/7, kyverno 4/4) |
| external-ca (was ca-configmap) | 2 s + re-render 29 s | first version looked for a ClusterIssuer that doesn't exist yet; now reads cert-manager/kubernetes-ca |
| install_maia_core | 13 min 12 s | ✅ 8 apps (Kubeflow is most of the time) |
| install_maia_admin | — | ❌ ssh banner timeout (rc 255) → retry in guest_job; ❌ **UPSTREAM rootCA["cert"] TypeError** → externalCA = k3s CA; ❌ Keycloak `Insufficient cpu` (requests 3.59/4) → **user: 8 vCPU** (VM restart 34 s) |
| (VM restart side effects) | — | k3s re-applied bundled traefik/local-storage (**install-maia clobbered k3s config** + **UPSTREAM local-path name clash**), fixed (force: false + `disable+: [local-storage]`); /etc/hosts wiped by cloud-init (fixed later) |
| install_maia_admin | — | ❌ Keycloak `password authentication failed for user "bn_keycloak"`: Postgres killed by liveness probe during initdb. **flem HDD: 67 ms/fsync** → **user: `cache=unsafe`** → 1.2 ms/fsync; DB re-init 25 s, 0 restarts |
| install_maia_admin | 3 min 36 s | ❌ guacamole: no pods → **UPSTREAM ADMIN_PROJECT_CHART_VERSION 1.3.0 has no guacamole app** → pin 1.3.1 |
| install_maia_admin | 3 min 35 s | ❌ `charts/guacamole: app path does not exist` on master → **UPSTREAM git charts default to master** → pin to branch |
| install_maia_core + install_maia_admin | 3 min 17 s + — | ❌ argocd sync hangs: traefik LB `<pending>` → **UPSTREAM metallb pool `10.0.2.15-fec0::…`** → `metallb_ip_pool` |
| install_maia_core + install_maia_admin | 3 min 14 s + 1 min 35 s | ✅ |
| configure_oidc_authentication | 29 s | ❌ `Could not resolve host: registry.maia.local` (cloud-init rewrote /etc/hosts) → `manage_etc_hosts: false` + configure_hosts re-run 35 s |
| configure_oidc_authentication | 27 s | ✅ |
| configure_maia_dashboard | 45 s | ✅ (dashboard pod pip-installs MAIA at start, ~80 s until 302) |
| keycloak-admin | 7 s | first-access admin `admin@maia.local` created (upstream had skipped it on resumed runs) |
Memory and CPU at the end: node 8 vCPU / 16 GB, CPU requests 5.9/8, ~8 GB available; no OOMKills.
flem after the VM got 16 GB: ~6 GB available on the host.

## Verification (2026-11-24 20:35, through `ssh -L 8443:127.0.0.1:8443 flem`): **VERIFY OK**
| # | Check | Result |
|---|---|---|
| 1 | `kubectl get nodes`, pods not Running/Completed | maia-vm Ready v1.35.4+k3s1; all pods Running/Completed |
| 2 | ArgoCD apps of the install set | all Healthy; Synced or only benign drift (CRD/ClusterRole/webhook caBundle, k3s coredns CM, Bitnami keycloak-postgresql Secret) |
| 3 | `curl -k --resolve <h>.maia.local:8443:127.0.0.1` | maia 301, iam 302, registry 200, kubeflow 403 = oauth2-proxy "Sign In" page, chat 200, login 303 |
| 4 | OIDC | discovery issuer OK; `/maia/` → `/maia/login/`; `/maia/oidc/authenticate/` → Keycloak authorize (client_id=maia) → login form; `admin@maia.local`/`admin` → `required-action UPDATE_PASSWORD` |
| 6 | secret values in skill dir + logs | none (logs are redacted by `run()`; 18 earlier log files were scrubbed after the MAIA_Install leak was found) |
| 5 | teardown + fresh-agent rebuild | not run (needs user approval) |

## Step 5: teardown + fresh-agent rebuild (2026-11-24, 21:03–22:10 CET), approved by the user, secrets.env kept
**[WSL]** `90_teardown.sh --hypervisor flem --approve-host-changes` (7 s): only `maia-vm.service` and `~/.maia-vm/maia-vm` removed on
flem; after: no qemu, ports free, 21 GB available, smolvm untouched.
A fresh agent (no prior context) then followed SKILL.md only, with the unit pre-approved (8 vCPU, `--disk-cache unsafe`):
| Step | Time | Result |
|---|---|---|
| 00_preflight | 3 s | OK (WARN rotational disk → unsafe chosen) |
| 21_create_vm_qemu stage A + B | 27 s + 26 s | OK; ssh after ~10 s |
| 30_bootstrap_guest | 2 min 1 s | OK (with reboot) |
| 40_render_config | <1 s | OK (existing secrets.env reused) |
| render + bootstrap + external-ca | 1 min + 6.5 min + 35 s | OK |
| install_maia_core | 6 min | ❌ **UPSTREAM 12** Kyverno `inject-proxy-env-vars` → `HTTPS_PROXY=:3130` in all new pods; agent deleted the policy + 7 argocd pods |
| install_maia_core (re-run) | 6 min 19 s | OK |
| install_maia_admin | 23 min 52 s | OK, but ~19 min of it was **UPSTREAM 13** (hung `argocd app sync maia-admin-guacamole`), killed |
| keycloak-admin | 5 s | ❌ 409 `Client maia-public already exists` (**UPSTREAM 14**; the skill wrongly called the script idempotent) |
| configure_oidc_authentication + dashboard | 37 s + 50 s | OK |
| 60_verify (1st) | 9 s | ❌ local-path OutOfSync (happens on every install) + dashboard 502 (pip install took ~7 min) |
| 60_verify (2nd, after a local-path sync + waiting) | 12 s | **VERIFY OK** |
End to end ~66 min, with 4 manual interventions, all inside the guest. Fresh-agent SKILL.md gaps it reported: working directory not
stated, manual ssh needs the skill's known_hosts, the 3 upstream issues above, local-path drift misattributed to reboots, dashboard
timing understated, noisy "FAILED open or read" in stage A, mis-numbered verify checks.

### Skill fixes from the rebuild (tested on the rebuilt VM, 22:13–22:15)
| Fix | Test |
|---|---|
| `kyverno-proxy-fix` step after install_k3s | no-op when clean; re-applied the policy + test pod (`HTTPS_PROXY=:3130`) → policy deleted, pod recreated with empty env, argocd Ready |
| watchdog in maia-step.sh for hung `argocd app sync` (>10 min, only if the app is Succeeded/Synced/Healthy) | fake hung CLI with `SYNC_HANG_SECS=5` → killed after the ArgoCD check |
| `local-path-sync` step after install_maia_core | already Synced → no-op (the sync path was exercised by hand in both runs) |
| keycloak-admin accepts 409 + checks the user through the admin API | on the rebuilt VM: 409 accepted, `admin@maia.local exists` |
| 60_verify waits ≤10 min for the dashboard | see final verify below |
| stage A image pre-check quiet (`sha256sum --status`) | syntax only (the image is already present on flem) |
| SKILL.md: run from repo root; known_hosts for manual ssh; INSTALL DONE / FAILED; step table; verify numbering | — |
