# Configuration reference

## Script flags (all scripts, parsed in scripts/lib.sh)
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

## Fixed config.yaml additions (vs verdi), all explained in troubleshooting.md
`install_k3s.proxy_ip/no_proxy_ips: ""`, `cluster_config_extra_env.selfsigned: true`, `externalCA` (= k3s server CA, after the
external-ca step), `metallb_ip_pool: <ip>-<ip>`, `ADMIN_PROJECT_CHART_VERSION: 1.3.1`, branch-pinned git chart refs, generated secrets.

## Secrets (`~/.maia-vm/<name>/secrets.env`, 0600, control node only)
`MAIA_KEYCLOAK_CLIENT_SECRET MAIA_OPENWEBUI_ADMIN_PASSWORD MAIA_WEBUI_SECRET_KEY MAIA_AGENT_API_TOKEN MAIA_GUACAMOLE_PASSWORD`,
generated once with `openssl rand -hex 24` and turned into `secrets.yml` for `-e @`. The keycloak secret is seeded into
`/etc/maia-config/env.json`, so MAIA uses it for the Keycloak client and OpenWebUI's OAuth matches.
MAIA itself generates the other platform passwords (Keycloak admin console user `user`, ArgoCD, MinIO, MySQL/Mongo) into
`/etc/maia-config/env.json` **on the guest** (0600). Read the admin logins from there:
`ssh maia-vm sudo jq -r 'keys[]' /etc/maia-config/env.json`.

## Guest layout
`/etc/maia-config/{config.yaml,env.json,inventory,main.sh,maia-step.sh,install_MAIA.sh,install_k3s.sh}`,
`/etc/maia-config/logs/job-<step>.{log,pid,rc}` (these **contain secret values**: upstream MAIA_Install logs env values), k3s data in `/mnt/maia-data/k3s` (linked from /var/lib/rancher/k3s).
