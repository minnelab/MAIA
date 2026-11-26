# Configuration reference

## Script flags (all scripts, parsed in scripts/lib.sh)
**Remembered per deployment** in `~/.maia-vm/<name>/install-flags.env` (0600, plain `VAR=value`, parsed, never sourced):
`--branch --domain --cluster-api --hypervisor --guest --ssh-port --https-port --http-port --api-port --disk-cache`. A script run
without one of them uses the saved value and prints `flags (saved in …): …` for those that differ from the defaults; a flag or
env var given explicitly wins, is saved, and prints `flags: VAR: old -> new (saved)`. Values are validated before saving.
`--name` picks the directory, so it is never saved: pass it on every call for a VM not named `maia-vm`. Teardown keeps the file
(a rebuild reuses the flags); `--purge-secrets` deletes it with secrets.env and overrides.yaml.
| Flag / env | Default | Meaning |
|---|---|---|
| `--hypervisor <alias>` / `HYPERVISOR` | empty = local | SSH alias of the VM host. Empty means the VM runs on the control node |
| `--guest <alias>` / `GUEST` | `maia-vm` | ssh_config alias for the MAIA node. HostName, Port, User and ProxyJump come from ssh_config |
| `--name` / `VM_NAME` | `maia-vm` | VM name, unit name, `~/.maia-vm/<name>/`, CLUSTER_NAME |
| `--branch` / `MAIA_BRANCH` | `157-add-tool-for-mcp-server-to-execute-helm-commands-from-dashboard` | any branch pushed to minnelab/MAIA (pip, raw script URLs, collection, MAIA_TAG) |
| `--domain` / `CLUSTER_DOMAIN` | `maia.local` | ingress hosts: `maia. iam. registry. kubeflow. chat. login.` |
| `--ssh-port --https-port --http-port --api-port` | 2222 8443 8080 16443 | hostfwd ports on the hypervisor's 127.0.0.1 |
| `VM_CPUS VM_MEM_GB VM_DISK_GB` | 8 16 150 | guest size (4 vCPU is too few for MAIA's requests) |
| `--disk-cache` / `VM_DISK_CACHE` | `writeback` | `unsafe` on HDD hypervisors, with user approval (see qemu-fallback.md) |
| `SSH_PUBKEY` | `~/.ssh/id_ed25519.pub` | key injected for guest user `maia` |
| `--cluster-api on\|off` / `CLUSTER_API` | `off` | 50_install, 60_verify. Dashboard Cluster API (`/maia/cluster-api/`: kubectl/helm/argocd over HTTPS). `on` sets `CLUSTER_API_ENABLED=True` and `CLUSTER_API_TOKEN` (= `MAIA_CLUSTER_API_TOKEN` from secrets.env); `off` sets `CLUSTER_API_ENABLED=False`. Toggle on an installed cluster: `--only-step render`, then `--only-step configure_maia_dashboard` (same flag on both), then `60_verify.sh` with the flag |
| `--overrides <file>` | none | 40, 50. Per-deployment images/charts file (below), copied to `~/.maia-vm/<name>/overrides.yaml` |
| `--approve-host-changes` | off | required by 05, 21 (unit stage) and 90; give it only after the user has seen the printed plan |

## Ansible vars (ansible/roles/maia/defaults/main.yml, override with `-e` or group_vars/maia.yml)
| Var | Default | Notes |
|---|---|---|
| `maia_branch` | as above | |
| `maia_version`, `maia_dashboard_image_version` | `2.6.0-preview` | For `master`, set release versions, e.g. `2.6.0` |
| `maia_tag` | `{{ maia_branch }}` | |
| `maia_env_overrides` | `{ADMIN_PROJECT_CHART_VERSION: "1.3.1"}` | extra keys for config.yaml `env:` (see MAIA/versions.py). 1.3.1 is needed for Guacamole |
| `maia_branch_chart_keys` | all git_repo `*_CHART_VERSION` keys | set to `maia_branch` unless the branch is `master` |
| `maia_core_apps`, `maia_admin_apps` | full verdi set (8 core, 6 admin) | drop items to save memory, but only with the user's OK |
| `maia_install_kyverno`, `maia_install_argocd`, `maia_prepare_ufw` | true | |
| `maia_openai_api_base_urls` (+`_keys`, `_configs`, `maia_default_models`, `maia_openwebui_model`) | empty → `ENABLE_OPENAI_API=false` | |
| `volume_path` | `""` | block device to mount on `/mnt/maia-data`. Empty means the root disk |
| `maia_timezone` | Europe/Stockholm | |
| `maia_cluster_api` | `"off"` | set by `--cluster-api`; `on` needs `maia_cluster_api_token` (≥ 32 chars, from secrets.yml) or the render's assert fails |

## Overrides file (`~/.maia-vm/<name>/overrides.yaml`)
Per-deployment images and charts, kept on the control node next to secrets.env (it holds no secrets). Start from
[profiles/example.yaml](../profiles/example.yaml); keep shared profiles in `profiles/`. `scripts/overrides.py` checks every key
against `MAIA/versions.py` of `origin/<branch>` and writes `overrides.vars.yml`, which every render passes with `-e @`.
| Section | Becomes (config.yaml `env:`) |
|---|---|
| `images.registry` | `MAIA_REGISTRY` (dashboard, gpu-booking and project images read it) |
| `images.<name>: <tag>` | `<NAME>_IMAGE_VERSION`; `maia-dashboard` sets `maia_dashboard_image_version` |
| `charts.ref` | every key in `maia_branch_chart_keys` + `MAIA_CHART_GIT_REF` (default: the branch; nothing on master) |
| `charts.<NAME>: <v>` or `{version, type}` | `<NAME>_CHART_VERSION` / `<NAME>_CHART_TYPE` |
| `env.<KEY>` | passed through (unknown keys allowed with a note; secret-looking keys rejected) |
Precedence, lowest first: branch pinning, `maia_env_overrides` (skill defaults), the overrides file. Keys the template sets
itself (`CLUSTER_DOMAIN`, `MAIA_TAG`, `CLUSTER_API_*`, …) are rejected: use their flag or var.
Rejected until MAIA changes land (plan step 2): `charts.git_repo/helm_repo` (`MAIA_PRIVATE_REGISTRY` is one URL for git charts,
Helm charts and images, and MAIA_Install doesn't export it), `images.<name>.repository`, and `values:`.
Apply a change to a running cluster: edit the file → `50_install.sh --only-step render` (flags come from install-flags.env)
→ re-run the step that owns the app (e.g.
`--only-step configure_maia_dashboard` for the dashboard image) or sync that ArgoCD app. Never sync `maia-admin-keycloak`.
Use unique image tags (`<version>-<git sha>`). A reused tag (e.g. `2.6.0-preview`) is only traceable through the digest that
`60_verify.sh` check 7 records in `~/.maia-vm/<name>/deployed/`; run `60_verify.sh --versions-only` after applying a change to see
exactly what it changed.

## Fixed config.yaml additions (vs verdi), all explained in troubleshooting.md
`install_k3s.proxy_ip/no_proxy_ips: ""`, `cluster_config_extra_env.selfsigned: true`, `externalCA` (= k3s server CA, after the
external-ca step), `metallb_ip_pool: <ip>-<ip>`, `ADMIN_PROJECT_CHART_VERSION: 1.3.1`, branch-pinned git chart refs, generated secrets.

## Secrets (`~/.maia-vm/<name>/secrets.env`, 0600, control node only)
`MAIA_KEYCLOAK_CLIENT_SECRET MAIA_OPENWEBUI_ADMIN_PASSWORD MAIA_WEBUI_SECRET_KEY MAIA_GUACAMOLE_PASSWORD MAIA_HARBOR_ADMIN_PASSWORD MAIA_CLUSTER_API_TOKEN`,
generated once with `openssl rand -hex 24` and turned into `secrets.yml` for `-e @`. The keycloak secret is seeded into
`/etc/maia-config/env.json`, so MAIA uses it for the Keycloak client and OpenWebUI's OAuth matches.
`MAIA_CLUSTER_API_TOKEN` is always generated but only reaches the guest with `--cluster-api on` (config.yaml `env:` → dashboard env).
Clients use it as `Authorization: Bearer …`, e.g. the maia-cluster MCP server: `MAIA_CLUSTER_API_URL=https://maia.<d>/`,
`MAIA_CLUSTER_API_TOKEN` read from secrets.env (through the tunnel).
MAIA itself generates the other platform passwords (Keycloak admin console user `user`, ArgoCD, MinIO, MySQL/Mongo) into
`/etc/maia-config/env.json` **on the guest** (0600). Read the admin logins from there:
`ssh maia-vm sudo jq -r 'keys[]' /etc/maia-config/env.json`.

## Guest layout
`/etc/maia-config/{config.yaml,env.json,inventory,main.sh,maia-step.sh,install_MAIA.sh,install_k3s.sh}`,
`/etc/maia-config/logs/job-<step>.{log,pid,rc}` (these **contain secret values**: upstream MAIA_Install logs env values), k3s data in `/mnt/maia-data/k3s` (linked from /var/lib/rancher/k3s).
