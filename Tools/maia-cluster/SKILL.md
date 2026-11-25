---
name: maia-cluster
description: >-
  Monitor, troubleshoot, read logs from and change a MAIA Kubernetes cluster
  through the MAIA Dashboard Cluster API (kubectl/helm/argocd executed
  server-side by the dashboard). Use when the user asks about cluster/pod/node
  health, logs, events, failing workloads, restarting/scaling/rolling back
  deployments, applying manifests, installing/upgrading Helm releases, or
  Argo CD application sync/health/rollback on a MAIA cluster.
  Prefer the maia-cluster MCP tools; fall back to Tools/maia-cluster/maia_cluster.py.
---

# MAIA Cluster Operations via the Dashboard API

The MAIA Dashboard exposes `kubectl`, `helm` and `argocd` over HTTPS at
`<dashboard>/maia/cluster-api/`. `argocd` always runs as `argocd --core`, which
talks to Kubernetes directly, so no Argo CD login is needed. Commands run **on the dashboard server**,
using its cluster credentials (usually cluster-admin). You do **not** need a
kubeconfig, and local `kubectl` is irrelevant. Treat every call as acting on a
production cluster with admin rights.

## How to reach it

Pick the first option that is available:

1. **MCP tools** (server `maia-cluster`, from `Tools/maia-cluster/mcp_server.py`).
2. **Shell CLI**: `python Tools/maia-cluster/maia_cluster.py ...` (stdlib only).
3. **Raw HTTP**: see [API contract](#api-contract).

All three read `MAIA_CLUSTER_API_URL` and `MAIA_CLUSTER_API_TOKEN`. If either
is missing, ask the user for them. Never print the token or write it to files.

**Always start with `cluster_api_status`** (CLI: `status`). It confirms
reachability, auth, tool versions and the timeout cap. Report problems using
the `hints` field it returns.

## Choose the tool

| Goal | MCP tool | CLI |
|------|----------|-----|
| "Is the cluster healthy?" | `cluster_overview` | `overview [-n NS]` |
| Why is X broken? | `diagnose_workload` | `diagnose deployment/x -n NS` |
| List / inspect objects | `kubectl_get`, `kubectl_describe` | `kubectl get ...` |
| Logs | `pod_logs` | `logs TARGET -n NS --since 10m` |
| Events | `cluster_events` | `events -n NS --warnings` |
| CPU / memory | `resource_usage` | `kubectl top pod -A` |
| Create / update objects | `apply_manifest` (diff → dry-run → apply) | `kubectl apply -f - < m.yaml` |
| Small in-place change | `patch_resource`, `set_image` | `kubectl patch ...` |
| Restart / rollback / wait | `rollout` | `kubectl rollout restart deploy/x -n NS` |
| Scale | `scale_workload` | `kubectl scale ...` |
| Delete | `delete_resource` (dry run by default) | `kubectl delete ... --dry-run=server` |
| Helm inspect | `helm_info` | `helm list -A` |
| Helm install / upgrade / rollback / remove | `helm_upgrade`, `helm_rollback`, `helm_uninstall` | `helm ...` |
| Argo CD apps: list / status | `argocd_apps`, `argocd_app_status` | `apps --problems`, `argocd app get X` |
| Argo CD: what would change | `argocd_diff` | `argocd app diff X` |
| Argo CD: deploy / rollback / stop | `argocd_sync`, `argocd_rollback`, `argocd_terminate_op` | `argocd app sync X` |
| Anything else | `cluster_exec` | `kubectl ...` / `helm ...` / `argocd ...` |

Prefer the dedicated tools. They build safe argument lists, condense JSON
output, cap output size, and attach `hints` on failure.

## Workflows

### Monitor

1. `cluster_overview` (whole cluster, or `namespace=` for one project).
2. For each entry in `pods.unhealthy`, `nodes.not_ready` or `helm.not_deployed`, drill down with `diagnose_workload` or `kubectl_describe`.
3. "Watch" is not available. To follow progress, call again: `pod_logs since="2m"`, `cluster_events warnings_only=true`, or `rollout action=status wait_seconds=120`.

### Troubleshoot a failing workload

1. `diagnose_workload target="deployment/NAME" namespace=NS`. It returns the conditions, pod states, related events, current and previous logs, and `hints`.
2. Act on the root cause, not the symptom:
   - **ImagePullBackOff**: check the image/tag and the `imagePullSecrets`.
   - **CrashLoopBackOff**: read `previous` logs.
   - **OOMKilled**: raise memory limits.
   - **FailedScheduling**: compare requests with node allocatable (GPU!), check taints and PVC binding.
   - **CreateContainerConfigError**: a ConfigMap or Secret key is missing.
3. Apply the fix (see Change), then `rollout action=status` and re-run `diagnose_workload` to verify.

### Logs

- `pod_logs target="deployment/x" namespace=NS tail=200` returns one pod.
- `selector="app=x"` aggregates all replicas. Add `grep="error"` to filter.
- `previous=true` gives the crashed instance's logs. Use `container=` for sidecars and init containers.
- Output keeps the **newest** lines when truncated. Narrow with `since` and `tail` rather than asking for everything.

### Change (always propose → preview → apply → verify)

1. Read the current state (`kubectl_get output=yaml`, `helm_info values`).
2. Preview:
   - `apply_manifest mode="diff"` or `mode="dry-run"`
   - `patch_resource dry_run=true`, `scale_workload dry_run=true`
   - `helm_upgrade dry_run=true`, `delete_resource` (dry run by default)
3. Show the user what will change. **Get explicit confirmation** for anything that affects running services. That includes deletes, uninstalls, scaling to 0, rollbacks, RBAC, CRDs, PV/PVC, namespaces, and the `maia-dashboard`, `keycloak`, `argocd`, `traefik` and `cert-manager` namespaces.
4. Apply, then verify with `rollout action=status` / `diagnose_workload` / `cluster_overview`.

### Helm

- `chart` can be `repo/chart` (only if the repo is already added on the dashboard server), `oci://registry/chart`, or a chart name plus `repo=<URL>`. Prefer the explicit `repo` URL.
- Values go in `values_yaml`, sent via stdin. Use `reuse_values=true` + `set_values` to tweak one key without resetting the others.
- Before upgrading, `helm_info action=history` lets you roll back with `helm_rollback revision=N` if needed.

### Argo CD

MAIA's platform runs as **Argo CD Applications**. Their names follow the pattern `maia-core-<component>` (traefik, cert-manager, metallb, loki, gpu-operator, kubeflow, ...) and `maia-admin-<component>` (keycloak, harbor, rancher, maia-dashboard, ...), plus one set per MAIA project.

1. `argocd_apps only_problems=true` finds what is OutOfSync, unhealthy or erroring.
2. `argocd_app_status name=X` shows conditions, the last operation, failed resources and the resources that are not OK. Use `refresh="hard"` after a chart or Git change.
3. `argocd_diff name=X` shows what a sync would change.
4. Show the diff, get confirmation, then `argocd_sync name=X`:
   - Add `prune=true` only if the user agreed to deleting resources.
   - Use `resources=[...]` to sync selectively.
   - `dry_run=true` previews the sync.
5. Verify with `argocd_app_status`. For a stuck sync, use `argocd_terminate_op`.

What to know about MAIA's Applications:
- **Manual sync policy.** They usually have no automated sync, so `OutOfSync` is normal until someone syncs. Never "fix" OutOfSync by syncing everything: sync one app at a time, after a diff.
- **Owned by Helm.** The Applications are created by the Helm releases `maia-core`, `maia-admin` and `<project>` in the `argocd` namespace (check with `helm_info action=list namespace=argocd`). A durable change to an Application's values, chart version or target revision goes through `helm_upgrade` of that parent release with `reuse_values=true`. A direct `argocd app set` or `kubectl patch` of the Application is reverted on the next `helm upgrade`. Tell the user when a change is only a hotfix.
- **Resources owned by an app.** Workload objects created by an app carry `argocd.argoproj.io/tracking-id` or `app.kubernetes.io/instance`. Editing them directly makes the app OutOfSync, and the next sync reverts the edit.
- **Not available:** `argocd login`, `context`, `--server`, `app edit`, and `app logs -f`. Use `pod_logs` for logs.

## MAIA specifics

- Platform components are Argo CD Applications in the `argocd` namespace (see the Argo CD section). **They do not appear in `helm list`**, which only shows the parent releases.
- **Project namespaces** are named after the MAIA project/group ID, lowercase. They hold JupyterHub (`hub`, `proxy`, `jupyter-<user>` pods), project apps (Orthanc, MLflow, MinIO, MONAI Label, ...) and PVCs. Project apps are often installed as Helm releases in that namespace (`helm_info action=list namespace=<project>`).
- User workspaces are `jupyter-<username>` pods. Don't delete them without the user's consent: unsaved work lives in the session.
- GPUs show up as `nvidia.com/gpu` in node allocatable, or as DRA ResourceClaims (`kubectl_get kind=resourceclaims -A`).

## Limits (enforced by the dashboard; don't retry, adapt)

| Not supported | Use instead |
|---------------|-------------|
| `kubectl edit` | `kubectl_get output=yaml` → modify → `apply_manifest`, or `patch_resource` |
| `logs -f`, `get -w`, `--watch` | Poll with `since=` / repeated calls; `rollout status --timeout`; `kubectl wait --for=... --timeout=` |
| `exec -it`, `run -i`, `attach` | One-shot: `cluster_exec command="kubectl exec POD -n NS -- cat /etc/os-release"` |
| `port-forward`, `proxy` | Not possible: inspect via `kubectl_get`/`describe`/logs, or a one-shot `exec` with `wget`/`curl` from inside a pod |
| Local files (`-f ./x.yaml`, `cp`) | Send the content via `stdin` and `-f -`. Paths refer to the **dashboard server**. |

Other limits:
- Each command has a timeout (default 60 s, max reported by status).
- Output is capped server-side (1 MB) and client-side (`MAIA_CLUSTER_MAX_OUTPUT_CHARS`, default 60k). Use selectors, `-n`, `--tail`, `jsonpath` or `custom-columns` to stay small.
- There is a rate limit (default 600 calls/hour per IP), so batch reads with `-o json` instead of looping per object.
- Every command is audit-logged on the dashboard with its caller.
- `MAIA_CLUSTER_READ_ONLY=true` makes the client refuse all mutations. Dry runs are still allowed.

## Interpreting results

Every command returns:

`{ok, exit_code, command, kind: read|write, stdout, stderr, timed_out, truncated, hints?}`

- The HTTP call succeeding does **not** mean the command succeeded. Check `ok` / `exit_code` and read `stderr`.
- `no such host` / `connection refused` in `stderr`: the dashboard cannot reach the Kubernetes API (network, VPN or kubeconfig on the server side). Tell the user; this is not something to fix by retrying.
- `Forbidden`: the dashboard's credentials lack RBAC for that action.
- `kubectl diff` exit code 1 means "has changes". The tool reports that as `ok=true, has_changes=true`.

## API contract

For use without MCP or CLI:

```bash
# Status
curl -s -H "Authorization: Bearer $MAIA_CLUSTER_API_TOKEN" "$MAIA_CLUSTER_API_URL/maia/cluster-api/"

# Run (argv form: no shell parsing, preferred)
curl -s -H "Authorization: Bearer $MAIA_CLUSTER_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"tool":"kubectl","args":["get","pods","-n","myproj","-o","wide"]}' \
  "$MAIA_CLUSTER_API_URL/maia/cluster-api/exec/" | jq -r '.stdout, .stderr'

# Command-string form, with stdin and a timeout
jq -n --rawfile m manifest.yaml '{command:"kubectl apply -f - --dry-run=server", stdin:$m, timeout:120}' |
  curl -s -H "Authorization: Bearer $MAIA_CLUSTER_API_TOKEN" -H "Content-Type: application/json" \
       -d @- "$MAIA_CLUSTER_API_URL/maia/cluster-api/exec/"
```

HTTP status codes:

| Status | Meaning |
|--------|---------|
| 200 | Command ran. Check `ok`. |
| 504 | Command timed out (body still has `stdout` / `stderr`). |
| 400 | Rejected command. |
| 401 / 403 | Auth failure. |
| 404 | API disabled. |
| 413 | stdin too large. |
| 429 | Rate limited. |
| 501 | Binary missing on the server. |

## Safety rules

- Never run destructive commands, such as `delete namespace`, `delete pvc/pv`, `helm uninstall`, `drain`, `cordon`, CRD or RBAC changes, without the user's explicit, specific confirmation in this conversation.
- Never print Secret values. `kubectl get secret -o yaml` returns base64 data, so summarize keys only unless the user explicitly asks for a value.
- Do not put credentials in `--set` on the command line when stdin (`values_yaml`) works. The audit log masks `--set` values, but stdin keeps them out of the log entirely.
- Prefer reversible actions: `rollout restart` before deleting pods, `scale` before `delete`, `helm rollback` before reinstalling.
