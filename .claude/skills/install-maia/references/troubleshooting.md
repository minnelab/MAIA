# Troubleshooting (found in the reference run)

> **Upstream fixes, 2026-11-24:** fixes for all 11 UPSTREAM items below are in this repo's working tree (uncommitted):
> argocd proxy `when:`, `rootCA` path, `ADMIN_PROJECT_CHART_VERSION` 1.3.1, `MAIA_CHART_GIT_REF`, IPv4-only MetalLB pool,
> k3s `disable: [traefik, local-storage]` merge, Keycloak admin/theme ungated, pinned Keycloak DB passwords, CoreDNS wildcard
> (chart 0.2.4), `keycloak_resources` + 500m request, masked env logging / become vars file / `no_log` toggles (`maia_show_secrets`).
> Items 12–14 found by the fresh-agent rebuild are applied too (uncommitted): Kyverno proxy policy gated on `proxy_ip`,
> `argocd app sync --timeout` (600 s admin/dashboard, 1800 s core), and `create_client(..., skip_exists=True)`.
> Item 15 (pushed in cf3b159): Harbor admin password from `HARBOR_ADMIN_PASSWORD` instead of the chart default `Harbor12345`.
> Item 16 (uncommitted): `admin_email` passed to `MAIA_install_core_toolkit` in `roles/maia_core_layer`.
> Items 17–18 (uncommitted): `failed_when: false` on `Generate OpenWebUI API Key`; `rollout status` wait after the argocd-server restart.
> Items 19a–d (uncommitted): the API-key task calls `MAIA_fetch_openwebui_api_key.sh`, retries 20×30 s, passes the password
> via `OPENWEBUI_PASSWORD`; `configure_host.yaml` maps `chat.<domain>`. The skill stub (no `.sh`) is only for branches without 19a.
> The guest installs from the GitHub branch, so the skill's workarounds stay until those fixes are pushed there. After that,
> they're harmless no-ops (except `--disk-cache` and the 8 vCPU default, which are about the hardware).

Each entry gives the symptom, the cause, the fix in this skill, and whether it's **UPSTREAM** (proposed separately, not changed here).

## Hypervisor
### `/dev/kvm` permission denied for the user
`crw-rw---- root kvm` and the user isn't in `kvm`. The user fixes it with `sudo usermod -aG kvm $USER`, then reconnects. Don't fall back to TCG.

### QEMU unit fails: `Could not access KVM kernel module: Permission denied`, even though `id` shows kvm
The `systemd --user` manager (`user@UID.service`) started **before** the usermod, and lingering keeps it running, so its
children keep the old groups. Check: `grep Groups /proc/$(pgrep -u $USER -x systemd)/status` must contain kvm's gid.
Fix (user, sudo): `sudo systemctl restart user@$(id -u).service`. 00_preflight and 21_create_vm_qemu check for this now.

### `qemu-img: Failed to get shared "write" lock`
`qemu-img info` on a running VM's disk. Use `qemu-img info -U`.

### Re-running 21_create_vm_qemu.sh while the VM runs
Safe now: the disk and the seed are kept (a new seed means a new instance-id, which re-runs cloud-init and regenerates host keys).

## Scripts
### `ssh` inside a `run … <<EOF` block eats the rest of the script
`run` feeds the script to `bash -s` on stdin, and a nested `ssh` reads that stdin. Always use `ssh -n` inside run blocks.

## MAIA install
### UPSTREAM: every image pull fails with `proxyconnect tcp: dial tcp :3130: connect: connection refused`
`ansible/MAIA/Installation/roles/argocd/tasks/main.yml` → "Set proxy environment variables for k3s":
`when: proxy_ip is defined and proxy_ip != "" …`. The role default is `proxy_ip: null`, and null is *defined* and `!= ""`,
so `/etc/systemd/system/k3s.service.env` gets `https_proxy='https://:3130/'`, and k3s/containerd use it after the restart.
Same bug class as verdi's `volume_path is defined`.
- Fix in this skill: config.yaml `install_k3s: {proxy_ip: "", no_proxy_ips: ""}` (MAIA_Install passes that block as vars).
- If it already happened: `sudo truncate -s0 /etc/systemd/system/k3s.service.env && sudo systemctl daemon-reload && sudo systemctl restart k3s`,
  then `50_install.sh --from-step install_k3s`.
- Upstream proposal: `when: (proxy_ip | default('', true) | length > 0) and (no_proxy_ips | default('', true) | length > 0)`.
  The proxy port 3130 and the `10.36.0.0/16` in NO_PROXY are also site-specific hardcodes.

### `k3s kubectl …`: `Error: extracting data: permission denied` (Kyverno wait times out instantly)
The collection runs `k3s kubectl` **without become**. With `data-dir:` in /etc/rancher/k3s/config.yaml, a non-root k3s must
traverse `<data-dir>/data/<hash>`, and the data dir was root 0700. verdi got away with it only because "Ensure Volume ownership"
recursively chowns `maia_data_dir` to the ansible user before k3s installs. Fix in this skill: the role creates
`maia_k3s_data_dir` owned by `maia_user` (0700). Already broken: `sudo chown maia:maia /mnt/maia-data/k3s`.
UPSTREAM hardening: the collection could set `kubernetes_kubectl_cmd: "sudo k3s kubectl"` or use the KUBECONFIG + plain kubectl.

### UPSTREAM: MAIA_Install puts the become password on the command line
`MAIA_scripts/MAIA_Install.py` requires `PW` and runs `ansible-playbook -e ansible_become_password=$PW` for every step
(visible in `ps`). In this skill the guest user has NOPASSWD sudo and `PW=nopasswd-sudo` (a placeholder that isn't a secret).
Proposal: let ansible use `become` without a password when PW is unset, or pass it with `--become-password-file`.

### OpenWebUI stuck in ContainerCreating (`configmap "custom-ca-cert" not found`) with selfsigned
`roles/maia_admin_layer` creates `openwebui/custom-ca-cert` only `when: external_ca_set`. Selfsigned mode has no externalCA,
but the verdi OpenWebUI values mount it. Fix in this skill: the `external-ca` step sets externalCA to the k3s server CA
(see the rootCA entry below), so upstream creates the ConfigMap. The mount is also `optional: true`.
UPSTREAM proposal: create the ConfigMap from the selfsigned CA too.

### Re-running install_k3s prints `fatal:` lines for traefik helmchart / kubernetes-ca / internal-ca
These are "already exists" errors and are `ignore_errors` in the collection. Harmless; check `failed=0` in PLAY RECAP.

### UPSTREAM: install_maia_admin crashes with selfsigned: `TypeError: string indices must be integers, not 'str'`
`MAIA/maia_admin.py:1449` (`create_guacamole_values`): `open(Path(cluster_config_dict["rootCA"]["cert"]))`, but
`rootCA` is a **path string** everywhere else (`rootCA: $CONFIG_FOLDER/ca.crt` from MAIA_Configure_Installation.sh:262;
used as `Path(cluster_config_dict["rootCA"])` at maia_admin.py:375 and :917 and maia_core.py:1200). So any selfsigned install
with Guacamole fails. verdi never hits it because it sets `externalCA` (that branch comes first).
- Fix in this skill: the `external-ca` step (after install_k3s) writes the k3s server CA (= rootCA = the CA behind
  `kubernetes-ca-issuer`) to `/etc/maia-config/maia-ca.crt` and re-renders. config.yaml then gets
  `externalCA: {name: maia-ca, cert: /etc/maia-config/maia-ca.crt}`. That also makes upstream create
  `openwebui/custom-ca-cert` and the maia-dashboard CA secret, so the earlier OpenWebUI ConfigMap entry is handled upstream.
- Upstream proposal: `open(Path(cluster_config_dict["rootCA"]))` at line 1449.

### SSH to the guest: `Connection timed out during banner exchange` (rc 255) while Kubeflow images pull
The node is busy and sshd is slow to answer through ProxyJump. `guest_job` retries rc 255 up to 5× (the jobs re-attach,
so a retry is safe), and ConnectTimeout is 60 s.

### ArgoCD shows `OutOfSync/Missing` for gpu-booking, gpu-operator, loki, prometheus, tempo, …
The MAIA app-of-apps defines them, and install_maia_core syncs only `maia_core_argocd_applications`. Expected.
60_verify checks the install set (core + admin lists, `*dashboard*`, Kubeflow's `ml-*`) and lists the rest as `skip`.

## Capacity / storage (found on flem)
### Keycloak Pending: `Insufficient cpu` with 4 vCPU
`create_keycloak_values` hardcodes Keycloak `requests.cpu: 2` (no config knob). With Kubeflow, istio, knative, kyverno and
minio, a 4-vCPU node already has ~3.6 CPUs requested, so Keycloak never schedules. **The default is now 8 vCPU** (user decision 2026-11-24).
After the change, the node had 5.9/8 CPUs requested. UPSTREAM proposal: make Keycloak resources configurable and lower the default request.

### DB pods killed in the middle of first init on HDD hypervisors (Keycloak Postgres: `password authentication failed for user "bn_keycloak"`;
### katib-mysql: `Cannot create redo log files because data files are corrupt or the database was not shut down cleanly after creating the data files`)
flem's VM disk is a 7200 rpm desktop HDD (ST2000DM001). With the default QEMU cache, a guest fsync took ~67 ms
(`dd bs=8k count=300 oflag=dsync` → 121 kB/s). initdb/InnoDB init took > 90 s, the liveness probe (30 s + 6×10 s) killed it
(exit 137), and the restart found a half-initialized data dir ("Deploying PostgreSQL with persisted data"), so the DB user's
password was never set. Not a credentials mismatch: Keycloak and Postgres read the same Secret key.
- Fix (user approved): `--disk-cache unsafe` → `-drive …,cache=unsafe` (QEMU ignores guest flushes). fsync 67 ms → 1.2 ms
  (7.0 MB/s), and Postgres was ready in 25 s with 0 restarts. Risk: a *hypervisor* crash or power loss can corrupt the VM disk;
  a VM or k3s crash can't. 00_preflight warns when the hypervisor disk is rotational.
- Re-init a half-initialized DB (no data yet, so it's safe before configure_oidc_authentication):
  ```
  K="sudo k3s kubectl"
  $K -n keycloak scale sts maia-admin-keycloak-postgresql --replicas=0; $K -n keycloak delete pvc data-maia-admin-keycloak-postgresql-0
  $K -n keycloak scale sts maia-admin-keycloak-postgresql --replicas=1; $K -n keycloak delete pod maia-admin-keycloak-0
  $K -n kubeflow scale deploy katib-mysql --replicas=0; $K -n kubeflow delete pvc katib-mysql
  $K -n kubeflow scale deploy katib-mysql --replicas=1    # the PVC comes back from the ArgoCD sync of the kubeflow apps
  ```
- The nfs-client StorageClass has `archiveOnDelete: true`: deleted PVCs stay as `/nfs/archived-*` on the guest.

## Reboot robustness
### After a VM/k3s restart: k3s traefik reappears, MAIA's local-path provisioner crash-loops (`configmaps "local-path-config" is forbidden`)
Two causes:
1. (install-maia bug, fixed) Re-rendering overwrote `/etc/rancher/k3s/config.yaml`, which removed the `disable: [traefik]` that
   the upstream k3s role adds. The template is now written with `force: false` (first render only).
2. UPSTREAM: MAIA's `maia-core-local-path` and k3s's bundled `local-storage` addon both deploy `rancher.io/local-path` with the same
   `local-path-provisioner-bind` ClusterRoleBinding and `local-path` StorageClass. k3s re-applies its manifest on every start, so the
   binding points back at `kube-system`'s service account. Fix in this skill: drop-in `/etc/rancher/k3s/config.yaml.d/50-install-maia.yaml`
   with `disable+: [local-storage]` (append, so the k3s role's `combine` that replaces `disable` doesn't drop it).
   UPSTREAM proposal: have the k3s role disable `local-storage` together with traefik.
Cleanup if traefik HelmCharts are stuck deleting (finalizer `wrangler.cattle.io/on-helm-chart-remove`, helm-delete pods in
ContainerCreating for want of `chart-content-traefik`): `kubectl -n kube-system patch helmchart traefik{,-crd} --type=merge -p '{"metadata":{"finalizers":null}}'`
and delete the `helm-install-*`/`helm-delete-*` jobs.

### Pods in `Unknown` for ~5–10 min after a VM restart
Normal: containerd re-creates every sandbox, and NFSD has a 90 s grace period. Wait before diagnosing.

### UPSTREAM: install_maia_admin: `Wait until guacamole pods are ready` → `error: no matching resources found`
`MAIA/versions.py` defaults `admin_project_chart_version = "1.3.0"`, but `charts/maia-admin-project/templates/guacamole_app.yaml`
exists only from **1.3.1** (commit 5e3c2b2; published 2026-11-04). MAIA renders guacamole_values, but chart 1.3.0 never creates the
`maia-admin-guacamole` Application, so the guacamole namespace stays empty. Fix in this skill: `maia_env_overrides:
{ADMIN_PROJECT_CHART_VERSION: "1.3.1"}` (the same pin as verdi's commented env). Upstream proposal: bump the default in versions.py.

### UPSTREAM (security): MAIA_Install logs secrets
`MAIA_scripts/MAIA_Install.py:134` logs `Setting environment variable <KEY> to <VALUE>` for every config.yaml `env:` key, including
`GUACAMOLE_PASSWORD` and `AGENT_API_TOKEN`, into `/etc/maia-config/logs/*.log` on the node. In this skill, `run()` pipes all output
through `redact` (every secrets.env value becomes `<redacted:NAME>`) before anything reaches the control node's `logs/`.
The guest-side logs still hold them (the dir is 0750 maia, alongside env.json). Upstream proposal: mask values of keys matching
`PASSWORD|SECRET|TOKEN|KEY`.

### UPSTREAM: git-sourced charts default to `master`, so a dev-branch install mixes branch code with master charts
In `MAIA/versions.py`, every `*_CHART_TYPE: git_repo` chart (CORE_TOOLKIT, LOCAL_PATH, KUBEFLOW, ADMIN_TOOLKIT, MAIA_DASHBOARD, GUACAMOLE,
MAIA_NAMESPACE, …) has a `*_CHART_VERSION` (the git ref) that defaults to `master`. `charts/guacamole` doesn't exist on master, so the
`maia-admin-guacamole` app fails with `ComparisonError: charts/guacamole: app path does not exist`.
Fix in this skill: for `maia_branch != master`, every key in `maia_branch_chart_keys` is set to the branch in config.yaml `env:`.
Upstream proposal: default the git refs to `MAIA_TAG`/the installed branch.

### UPSTREAM: traefik LoadBalancer `<pending>`, Ingresses never Healthy (`argocd app sync` hangs on `waiting for healthy state of … Ingress`)
metallb-controller: `Failed to allocate IP for "traefik/maia-core-traefik": no available IPs`. The pool was
`["10.0.2.15-fec0::5054:ff:fe12:3456"]`: `maia_core.py` (around lines 337–369) joins the node's InternalIPs with `-`, and with a
dual-stack node (QEMU slirp adds a `fec0::` SLAAC address) that yields an IPv4-to-IPv6 "range". Some Ingresses still got 10.0.2.15
from k3s's servicelb, which hid the problem until a re-sync. Fix in this skill: `cluster_config_extra_env.metallb_ip_pool:
"<ipv4>-<ipv4>"` (an override maia_core already supports). Upstream proposal: use only the InternalIPs of one address family.

### configure_oidc_authentication: Harbor `curl … https://registry.<domain>/api/v2.0/configurations` fails (rc≠0, no output)
`Could not resolve host: registry.<domain>`. With selfsigned, MAIA's `configure_hosts` step writes `<node-ip> <sub>.<domain>` lines
to /etc/hosts, but cloud-init's `manage_etc_hosts: true` (from the QEMU seed) regenerates /etc/hosts on every boot, so they were
gone after the VM restarts (install-maia bug, fixed). The role writes `/etc/cloud/cloud.cfg.d/99-install-maia.cfg`
(`manage_etc_hosts: false`). If it already happened: `50_install.sh --only-step configure_hosts`.
UPSTREAM (security): the Harbor OIDC task has no `no_log`, so its `cmd`, which contains the Keycloak client secret, is printed in the
guest-side job log.

### UPSTREAM: first-access admin never created after a resumed install_maia_admin (`Invalid username or password`; realm has no users)
`roles/maia_admin_layer` runs `MAIA_configure_keycloak` (creates `<ADMIN_EMAIL>` with temporary password `admin` + `MAIA:users`)
only `when: keycloak_synced == false`, i.e. only on the run that first syncs the Keycloak app. If that run fails later, every resume
skips it. Fix in this skill: the `keycloak-admin` step runs it after every install_maia_admin. The script is **not** fully idempotent: user and
group creation catch "already exists", but `create_client(maia-public)` doesn't, so a re-run ends with
`KeycloakPostError: 409 Client maia-public already exists` (rc 1). The step accepts that 409, then checks through the admin API
that the user exists.
Note: ADMIN_EMAIL here is `admin@<domain>`, not the README's `admin@maia.io`. The Keycloak *admin console* user is Bitnami's `user`.
Upstream proposal: gate on "user absent", not on "app not yet synced".

### UPSTREAM: Bitnami Keycloak Postgres password isn't pinned
`create_keycloak_values` sets no `postgresql.auth.*`, so every ArgoCD render generates a new random password (ArgoCD can't use Helm
`lookup`), and `maia-admin-keycloak` always shows the `maia-admin-keycloak-postgresql` Secret OutOfSync. **Don't sync that app**:
the Secret would change and Keycloak would lose its DB. Upstream proposal: pass a password generated into env.json.

### UPSTREAM: in-cluster DNS doesn't know `maia.`, `chat.`, `login.`, `minio*.` `<domain>` (selfsigned)
`charts/maia-core-toolkit/templates/{selfsigned,k3s_coredns}.yaml` hardcode `iam registry mgmt argocd kubeflow` + the apex in
`coredns-custom`. Other names in that zone return **SERVFAIL** inside pods (`nslookup maia.maia.local`). Browser flows work
(they resolve outside the cluster), but any pod that calls the dashboard/OpenWebUI by its public name fails. No values override exists,
so it's not worked around here. Upstream proposal: add the missing subdomains, or make the list a value.

### ArgoCD drift that is expected (60_verify accepts it; nothing to fix)
OutOfSync but Healthy because a controller writes into the object after apply: CRDs and Mutating/ValidatingWebhookConfigurations
(`caBundle` injected by cert-manager/knative/istio), aggregated ClusterRoles (rules filled in by the aggregator), `kube-system/coredns`
(owned and re-applied by k3s), and the Keycloak Postgres Secret above. Anything else OutOfSync is reported as UNEXPECTED.
`maia-core-local-path` has all resources OutOfSync (health unknown) after **every** install_maia_core, not only after a reboot: the
core layer first creates the objects with kubectl apply (they carry a last-applied annotation), so ArgoCD doesn't treat them as its own.
One sync adopts them, and 50_install's `local-path-sync` step does it automatically. By hand:
`kubectl -n argocd patch application maia-core-local-path --type=merge -p '{"operation":{"sync":{}}}'`.

### Browser login through the tunnel fails after the Keycloak form
Keycloak's hostname is `iam.<domain>` without a port, so its form action and redirects go to :443. A `-L 8443:…` tunnel is enough
for curl with `--resolve` and URL rewriting (60_verify does this), but a browser needs the local tunnel on 443:
`sudo ssh -L 443:127.0.0.1:8443 <hypervisor>` plus hosts-file entries. The dashboard builds `redirect_uri=http://…` (Django doesn't see
X-Forwarded-Proto); Keycloak accepts it, so it isn't blocking.

## Found by the fresh-agent rebuild (2026-11-24, second run)
### UPSTREAM (12): install_maia_core fails at `Login to ArgoCD using CLI`; argocd-server restarting; pods have `HTTPS_PROXY=:3130`
`roles/argocd/tasks/main.yml:135-205` writes and applies the Kyverno ClusterPolicy `inject-proxy-env-vars` whenever Kyverno is
freshly installed. Its only conditions are `install_kyverno` and "Kyverno not yet installed", with no `proxy_ip` check. With no proxy,
every new pod gets `HTTP(S)_PROXY=":3130"`. argocd-server can't reach the API (`proxyconnect tcp: dial tcp :3130`) and the ArgoCD
CLI login fails. The first reference run escaped it only because its first Kyverno install failed, so the re-run skipped these tasks.
- Fix in this skill: the `kyverno-proxy-fix` step (after install_k3s, only when `proxy_ip` is empty) deletes the policy (it keeps a
  copy in `/etc/maia-config/inject-proxy-env-vars.removed.yaml`) and recreates the controller-owned pods that carry the bogus env.
- By hand: `kubectl delete clusterpolicy inject-proxy-env-vars`, delete the pods whose env has `HTTPS_PROXY=:3130`, then
  `50_install.sh --from-step install_maia_core`.
- Upstream proposal: gate both Kyverno proxy tasks on `proxy_ip | default('', true) | length > 0` (same as the k3s.service.env fix).

### UPSTREAM (13): install_maia_admin hangs at `Sync maia-admin-guacamole ArgoCD application`
That task runs `argocd app sync maia-admin-guacamole` with `ignore_errors: true` but **no timeout**. ArgoCD finished the sync on the
server (operation Succeeded, Synced/Healthy, pods Running), but the CLI watch never returned (19 min). The first reference run hung
at the same task for a different reason: the MetalLB pool, so the Ingress was never healthy.
- Fix in this skill: maia-step.sh runs a watchdog during every step. It kills an `argocd app sync <app>` CLI older than 10 min
  (`SYNC_HANG_SECS`) only if ArgoCD reports that app `Succeeded/Synced/Healthy`. The ignored error lets the playbook continue.
- By hand: check the app is Synced/Healthy, then in the guest `pkill -f 'argocd app sync maia-admin-guacamole'`.
- Upstream proposal: give every `argocd app sync` task a `--timeout` (the CLI flag) and/or a task `timeout:`, as the admin-toolkit syncs already have.

### UPSTREAM (14): `MAIA_configure_keycloak` fails on re-run: `409 Client maia-public already exists`
`MAIA_scripts/MAIA_configure_keycloak.py` wraps `create_user` and `create_group` in try/except but not `create_client`, so it is not
idempotent. The upstream task is `ignore_errors`, which hides that; the skill's `keycloak-admin` step accepts the 409 explicitly.
Upstream proposal: catch `KeycloakPostError` with 409 around `create_client` (or look the client up first).

### UPSTREAM (15, security): Harbor runs with the public default admin password `Harbor12345`
`maia_admin.create_harbor_values` never set `harborAdminPassword`, so the chart default was used, and `configure_oidc_authentication`
logged in with the same hardcoded `harbor_admin_pass`. Anyone who reaches `registry.<domain>` could log in as admin.
- Fix upstream: `create_harbor_values` sets `harborAdminPassword` from env `HARBOR_ADMIN_PASSWORD` when present.
- Fix in this skill: `MAIA_HARBOR_ADMIN_PASSWORD` is generated in secrets.env and rendered into both `env.HARBOR_ADMIN_PASSWORD`
  and `configure_oidc_authentication.harbor_admin_pass`. 40_render_config adds missing keys to an existing secrets.env.
- Harbor reads the password only on its first start. If Harbor's database already exists, change it in the portal instead.
- Until the fix is on the branch the guest installs from, Harbor still starts with `Harbor12345`, and the OIDC task fails
  with 401 (it's `ignore_errors`) because the skill now sends the generated password.

### UPSTREAM (16): install_maia_core fails in 40 s: `KeyError: 'admin_email'` in `create_kubeflow_values`
Commit ad95809 added `"clusterAdminUser": os.environ["admin_email"]` to `MAIA/maia_core.py`, but the `Run MAIA Core Toolkit
installer` task in `roles/maia_core_layer` doesn't pass `admin_email` in its `environment:`, even though env.json has it.
- Fix in this skill: config.yaml.j2 adds `admin_email: admin@<domain>` under `env:`. MAIA_Install exports it, and the local
  ansible-playbook inherits it. Then `--only-step render` and `--from-step install_maia_core`.
- Upstream proposal: add `admin_email: "{{ admin_email | default('admin@maia.io') }}"` to that task's `environment:`.

### UPSTREAM (17): install_maia_admin fails at `Generate OpenWebUI API Key` (output censored by no_log)
Commit ad95809 added a task that runs `MAIA_fetch_openwebui_api_key`, but no such command exists: it isn't in setup.py,
pyproject.toml, or any commit. The task has no `ignore_errors`, although the next two tasks already handle `rc != 0` and an
empty key. Debug with `-e maia_show_secrets=true`, or check on the guest: `command -v MAIA_fetch_openwebui_api_key`.
- Fix in this skill: the render step installs a stub `~/.local/bin/MAIA_fetch_openwebui_api_key` on the guest, only if the
  command is missing. It prints an empty key and exits 0, so `OPENWEBUI_API_KEY` stays `""`, as in the earlier verified runs.
- Upstream proposal: add `ignore_errors: true` (or `failed_when: false`) to the task, and ship the command as a console script.
- 2026-11-25: the user added `MAIA_scripts/MAIA_fetch_openwebui_api_key.sh` (installed via `setup.py` `scripts=`, so the
  command name keeps `.sh`). Tested on the guest: sign-in, get/create key, `--recreate`, `--json`; the key works on `/api/v1/models`.
  Two skill bugs found while testing, both fixed: the guest had no `/etc/hosts` entry for `chat.<domain>` (now mapped with
  iam/kubeflow), and env.json's `openwebui_admin_password` differed from the skill's `WEBUI_ADMIN_PASSWORD` (now pinned).

### UPSTREAM (18): `argocd app sync maia-admin-openwebui` → `connection reset by peer`, then OpenWebUI never deployed
`maia_admin_layer` runs `kubectl rollout restart deployment argocd-server` without waiting. On a slow disk the new pod becomes
ready minutes later, and the old pod gets killed while a later `argocd app sync` (ignore_errors) is connected to it. In the
2026-11-25 rebuild that dropped the OpenWebUI sync, so OpenWebUI had no resources and the API-key task failed too.
- Fix in this skill: none needed. Re-run `--from-step install_maia_admin`; by then argocd-server is stable.
- Upstream proposal: follow the restart with `kubectl -n argocd rollout status deployment/argocd-server --timeout=300s`
  before the next login.

### Dashboard 502 for several minutes after configure_maia_dashboard
The dashboard pod pip-installs MAIA@branch at start: ~80 s in the first run, **~7 min** in the rebuild. 60_verify now waits up to
10 min for `/maia/` to answer 200/30x before the ingress/OIDC checks.
