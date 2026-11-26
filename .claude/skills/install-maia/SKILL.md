---
name: install-maia
description: Install the full MAIA platform (k3s + ArgoCD + MAIA core/admin/dashboard, the verdi component set) on a fresh VM or server, driven by an agent from a control node. Use when asked to install, reinstall, rebuild or test MAIA on a VM, a remote hypervisor (VM on an SSH host, e.g. flem), a local QEMU/KVM VM, or an existing Ubuntu 24.04 SSH host; also to resume a failed MAIA install step or tear down such a VM.
---

# install-maia

Reproducible, logged MAIA install. All scripts run on the **control node** (where this repo is checked out).
They reach the VM host as `ssh <hypervisor>` and the MAIA node as `ssh <guest>`, both ssh_config aliases.
Never hardcode IPs, users or ports: read them with `ssh -G <alias>`.
The reference run (target `remote-hypervisor`, hypervisor `flem`) is in [RUNBOOK.md](RUNBOOK.md). Every command here ran there.

## Inputs (ask for any you don't have)
| Input | Values / default |
|---|---|
| **target** | `remote-hypervisor` (VM on an SSH host; tested on flem) · `local-qemu` (VM on the control node) · `existing-ssh-host` (skip VM creation) · `local-smolvm` (**NO-GO**, see references/smolvm.md) |
| **hypervisor** | ssh alias, e.g. `flem` (`--hypervisor`). Empty means local |
| **branch** | `157-add-tool-for-mcp-server-to-execute-helm-commands-from-dashboard` or any pushed branch, e.g. `master` (`--branch`) |
| **domain** | `maia.local` (`--domain`) |
| guest alias / name | `maia-vm` / `maia-vm`. Size **8 vCPU** / 16 GB / 150 GB (`VM_CPUS VM_MEM_GB VM_DISK_GB`). 4 vCPU does not fit MAIA's CPU requests |
| cluster API | `--cluster-api off` (default) or `on`: enables the dashboard's kubectl/helm/argocd API with `MAIA_CLUSTER_API_TOKEN` from secrets.env. Pass the same value to 50_install and 60_verify |
| disk cache | `--disk-cache writeback` (default) or `unsafe`. **Ask the user** when preflight reports a rotational hypervisor disk: on flem's HDD, DB first-init outlasted liveness probes until `unsafe` |
| images / charts | optional `--overrides <file>` (start from `profiles/example.yaml`): image tags, registry, chart refs/versions. Stored as `~/.maia-vm/<name>/overrides.yaml`, validated against the branch's `MAIA/versions.py` |
The flags above (and ports) are **remembered** per deployment in `~/.maia-vm/<name>/install-flags.env`: pass them once; later calls reuse them, and a flag given again replaces the saved value. More flags: [references/config-reference.md](references/config-reference.md). Prompt template for a fresh install on a new server: [references/new-server-prompt.md](references/new-server-prompt.md).

## Rules
- **Approval gates.** Anything that changes the *hypervisor* (packages, smolvm install, user units, firewall, teardown)
  needs the user's go-ahead. The scripts print the plan and exit 3 until you pass `--approve-host-changes`.
  Show the printed plan to the user first. Changes inside the guest need no approval.
- **sudo on the hypervisor is the user's job.** If `sudo -n true` fails, give the user the exact commands to run.
  Never take, pass, or store a sudo/become password.
- **Secrets** live only in `~/.maia-vm/<name>/secrets.env` (0600) on the control node. Never on the hypervisor, never in the repo.
  Don't print them. Ansible tasks that touch them use `no_log`.
- Port forwards bind to **127.0.0.1** on the hypervisor. Reach services with an SSH tunnel.
- Every script logs to `logs/<ts>-<step>.log` and adds a row to `logs/journal.md` (where, step, duration, rc, output tail).
  Copy the relevant rows into RUNBOOK.md when you change the procedure.
- Local uncommitted changes are **not** installed. The guest pulls the branch from GitHub.
- **Never `argocd app sync maia-admin-keycloak`** to clear its OutOfSync: the Bitnami chart renders a new random Postgres password
  on every render, and a sync breaks Keycloak's DB login. Other apps' benign drift is listed in references/troubleshooting.md.
- Don't trust a "fatal:" line on its own: the collection has many `ignore_errors` tasks. Check `failed=0` in PLAY RECAP and the job rc.
  50_install.sh ends with `INSTALL DONE` on success; otherwise a `FAILED: [where] <step>` line names the step to fix and resume from.
- **Manual guest commands:** `ssh -o UserKnownHostsFile=~/.maia-vm/<name>/known_hosts <guest> …`. The scripts keep the guest's
  host key there, and it changes on every rebuild, so plain `ssh <guest>` fails on a stale `~/.ssh/known_hosts` entry.

## Procedure (run from the repo root: `cd $(git rev-parse --show-toplevel)`; `S=.claude/skills/install-maia/scripts`, `H="--hypervisor flem"`, or `H=""` for local)

### 0. Preflight (read-only, ~5 s): gate
`$S/00_preflight.sh $H --branch <b>`. It must print `PREFLIGHT OK`. Report every FAIL/WARN to the user and **stop** on:
no openable `/dev/kvm` (never use TCG); RAM < VM+4 GB; fewer idle CPUs than VM_CPUS; disk < VM+50 GB; a rotational VM disk (ask about `--disk-cache unsafe`); sudo needing a password where host
packages are missing; the `systemd --user` manager lacking the kvm group (user runs `sudo systemctl restart user@$(id -u).service`);
ports in use (pick others with `--ssh-port/--https-port/--http-port/--api-port` and tell the user).
User-run host setup for QEMU, if missing:
`sudo apt install -y qemu-system-x86 qemu-utils cloud-image-utils; sudo usermod -aG kvm $USER; sudo loginctl enable-linger $USER`.

### 1. Backend choice
QEMU is the default. smolvm is **NO-GO** (TSI networking has no default route, so k3s dies; the guest kernel has no nfs/nfsd;
systemd isn't PID 1). Only re-check after upgrading smolvm: `$S/05_install_smolvm.sh $H` (approval), then `$S/10_feasibility_smolvm.sh $H`.

### 2. Create the VM (QEMU, ~1 min + boot): skip for existing-ssh-host
1. `$S/21_create_vm_qemu.sh $H`: stage A writes VM files to `~/.maia-vm/<name>/` on the hypervisor (Ubuntu cloud image, GPG + SHA256
   verified; standalone 150 GB qcow2; cloud-init seed with user `maia`, NOPASSWD sudo, `~/.ssh/id_ed25519.pub`).
   Then it prints the systemd --user unit and exits 3.
2. Show the unit to the user. On go-ahead: `$S/21_create_vm_qemu.sh $H [--disk-cache unsafe] --approve-host-changes` →
   `enable --now`, waits for SSH and `cloud-init status --wait` (~1 min). Re-running with changed flags (CPUs, cache) rewrites the
   unit and **restarts the VM**, which needs the user's approval again. After a restart, pods sit in `Unknown` for 5–10 min. That's normal.
3. The guest alias must exist in `~/.ssh/config`. **Show it to the user before adding it:**
   ```
   Host maia-vm
     HostName 127.0.0.1
     Port 2222          # = --ssh-port
     User maia
     ProxyJump flem     # omit for local-qemu
   ```
For existing-ssh-host, the alias points at the server instead. Its user needs NOPASSWD sudo (the user sets this up).
Ubuntu 24.04, ≥ 4 CPU / 16 GB.

### 3. Guest bootstrap (~5 min, includes a reboot)
`$S/30_bootstrap_guest.sh --guest maia-vm`: apt upgrade, base packages, timezone, reboot if required. It prints the default route.

### 4. Render config (~1 s)
`$S/40_render_config.sh --guest maia-vm [--overrides <file>]`: creates secrets once, validates the overrides file, and renders `~/.maia-vm/<name>/inventory.ini` (user from `ssh -G`).

### 5. Install (~30–40 min: bootstrap 6–10, core 6–13, admin 4, oidc+dashboard 2)
`$S/50_install.sh --guest maia-vm --branch <b> --domain <d>` runs these steps in order:
| step | what | ref. time |
|---|---|---|
| render | ansible-playbook install-maia.yml: /etc/maia-config/{config.yaml,env.json,main.sh,maia-step.sh,…}, k3s config (first render only) + `disable+: [local-storage]`, traefik OIDC plugin, `manage_etc_hosts: false` | 1.3 min (30 s again) |
| bootstrap | main.sh → install_MAIA.sh (pip MAIA@branch, ansible, kubectl, helm, argocd) → prepare_hosts, configure_hosts, install_k3s | ~10 min |
| prepare_hosts / configure_hosts / install_k3s | re-run one of them on its own (skipped when bootstrap ran in the same invocation) | 35 s / 35 s / 3–5 min |
| k3s-traefik-cleanup | k3s starts before upstream's config disables traefik, so its traefik HelmCharts are applied, then stuck deleting (missing `chart-content-traefik`). With traefik disabled: drop their finalizers and the `helm-*-traefik*` jobs | 10–60 s |
| kyverno-proxy-fix | with no proxy set: delete upstream's Kyverno ClusterPolicy `inject-proxy-env-vars` and recreate pods that got `HTTPS_PROXY=:3130` (upstream applies it unconditionally) | 5 s |
| external-ca | k3s server CA (cert-manager/kubernetes-ca) → /etc/maia-config/maia-ca.crt, node trust store, re-render → `externalCA` in config.yaml | 30 s |
| install_maia_core | 8 ArgoCD apps (Kubeflow dominates) | 6–13 min (3 min re-run) |
| local-path-sync | one ArgoCD sync of `maia-core-local-path` (always OutOfSync after core: its objects were created by kubectl apply) | 10 s |
| install_maia_admin | admin toolkit, Keycloak, Harbor, OpenWebUI, Guacamole, dashboard apps. A watchdog in maia-step.sh kills an `argocd app sync <app>` CLI hung >10 min once ArgoCD reports that app Succeeded/Synced/Healthy (upstream task has no timeout) | ~2–4 min |
| keycloak-admin | re-runs MAIA_configure_keycloak (its 409 `already exists` = already configured, accepted), then checks via the Keycloak admin API that `admin@<domain>` exists (temporary password `admin`) | 7 s |
| configure_oidc_authentication | Harbor OIDC | 30 s |
| configure_maia_dashboard | dashboard (the pod pip-installs MAIA at start, so `maia.` gives 502 for **2–10 min**) | 45 s |
Long steps run **detached in the guest** (`/etc/maia-config/logs/job-<step>.{log,pid,rc}`), so an SSH drop doesn't kill them
(rc 255 is retried 5×). Re-running the same step re-attaches if the job is still running.
**Resume after a failure:** fix the cause, record it in references/troubleshooting.md, then `$S/50_install.sh --from-step <step>`
(or `--only-step <step>`). After a config change, run `--only-step render` first. Most known failures and their fixes are in
troubleshooting.md. Check there first: half-initialized DBs, `Insufficient cpu`, LoadBalancer `<pending>`, unresolvable `registry.<d>`.
Each job ends with `free -m`, `kubectl top nodes` and the list of pods that aren't running. If pods are OOMKilled or Pending
for memory/CPU, lower replicas/requests through config first, and **ask the user** before dropping a component or resizing the VM.

### 6. Verify (~1 min)
`$S/60_verify.sh $H --guest maia-vm --domain <d>`: (1) node Ready and every pod Running/Completed; (2) every ArgoCD app of the
install set Healthy and Synced, or only documented benign drift; then it waits (up to 10 min) for the dashboard to stop answering 502;
(3) through `ssh -L <local>:127.0.0.1:<https-port> <hypervisor>`, `curl -k --resolve` for `maia iam registry kubeflow chat login`
gives 200/30x (kubeflow: oauth2-proxy's 403 "Sign In" page); (4) Keycloak OIDC discovery, dashboard → Keycloak login form, and a
login as `admin@<d>`/`admin` reaching Keycloak's UPDATE_PASSWORD action (or a dashboard callback once it's changed); (5) is the
fresh-agent rebuild (below); (5b) the dashboard Cluster API matches `--cluster-api` (on: the token gets 200 `enabled`, no token is refused; off: 404 disabled); (6) no generated secret value anywhere in the skill dir or logs. (7) records what is deployed (MAIA commit on the node and in the dashboard pod, k3s, every ArgoCD app's
repo/chart/target/synced revision, Helm releases, every running image with its digest) in `/etc/maia-config/deployed-versions.md`
and `~/.maia-vm/<name>/deployed/` (`latest.md`, plus one file per distinct state), and prints the diff against the previous
record. It never fails VERIFY. `60_verify.sh --versions-only` runs only (7), e.g. after a sync or an image change. It must print `VERIFY OK` (~10 s
plus the dashboard wait).
Browser access for the user: Keycloak's hostname is `iam.<d>` **without a port**, so the browser must reach port 443.
Tunnel from their machine with local port 443 (needs admin rights): `sudo ssh -L 443:127.0.0.1:8443 flem`, add
`127.0.0.1 maia.<d> iam.<d> registry.<d> kubeflow.<d> chat.<d> login.<d>` to the hosts file, trust or accept the self-signed CA
(`/etc/maia-config/maia-ca.crt` on the guest), and open `https://maia.<d>/maia/`. First-access login: `admin@<d>` / `admin`
(temporary, Keycloak forces a change). Keycloak admin console user `user`; it and the other generated platform passwords are in
`/etc/maia-config/env.json` on the guest (0600).

### 9. Teardown (approval)
`$S/90_teardown.sh $H --name maia-vm` prints exactly what it removes: **only** `<name>.service` and `~/.maia-vm/<name>/` on the
hypervisor, plus control-node state. Nothing else on the host. Re-run with `--approve-host-changes` after the user agrees.
`--purge-secrets` also deletes secrets.env.

## Layout
`scripts/` (lib.sh = run/log helpers), `ansible/` (install-maia.yml, roles/maia adapted from verdi-ansible without Vault, proxy,
LLM endpoints or site users), `references/` (smolvm.md, qemu-fallback.md, troubleshooting.md, config-reference.md, new-server-prompt.md), `logs/` (gitignored).
