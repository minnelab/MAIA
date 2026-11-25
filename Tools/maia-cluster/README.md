# MAIA Cluster Tool Suite

An MCP server, a shell CLI and an agent skill for **monitoring, troubleshooting
and changing** a MAIA cluster through the MAIA Dashboard's Cluster API
(`/maia/cluster-api/`). The dashboard runs `kubectl` / `helm` / `argocd --core`
server-side with its own cluster credentials, so agents need only a URL and a
token: no kubeconfig, and no Argo CD login.

Agent instructions live in [`SKILL.md`](SKILL.md).

## Enable the API on the dashboard

The dashboard's environment needs:

```env
CLUSTER_API_ENABLED=True
CLUSTER_API_TOKEN=<long random secret>          # e.g. "sk-$(openssl rand -hex 16)"
# Optional
CLUSTER_API_KUBECONFIG=/path/to/kubeconfig      # empty = in-cluster service account
CLUSTER_API_KUBECTL_PATH=/usr/local/bin/kubectl # if kubectl is not on the server PATH
CLUSTER_API_HELM_PATH=/usr/local/bin/helm
CLUSTER_API_ARGOCD_PATH=/usr/local/bin/argocd
CLUSTER_API_ARGOCD_NAMESPACE=argocd             # namespace Argo CD is installed in
CLUSTER_API_ALLOWED_TOOLS=kubectl,helm,argocd
CLUSTER_API_DEFAULT_TIMEOUT=60
CLUSTER_API_MAX_TIMEOUT=300
CLUSTER_API_RATE=600/hour
```

### How `argocd` runs

`argocd` always runs as `argocd --core`, talking to the Kubernetes API with the
dashboard's credentials. Core mode reads the Argo CD namespace from the
kubeconfig context, so the dashboard injects `CLUSTER_API_ARGOCD_NAMESPACE`:

- **With a kubeconfig:** it writes a temporary overlay kubeconfig that redefines only the current context with that namespace, and puts it first in `KUBECONFIG`. The original file is left untouched, and relative certificate paths in it still work. The overlay is deleted after each command.
- **In-cluster:** it sets `POD_NAMESPACE`.

The dashboard rejects:
- `login`, `logout`, `relogin`, `context` and `configure`;
- `app edit`, `proj edit` and `appset edit`;
- `admin dashboard` and `app logs -f`;
- `--server`, `--auth-token`, `--grpc-web` and `--core=...`.

The dashboard's credentials need RBAC on `applications`, `appprojects`, secrets and configmaps in the Argo CD namespace. Commands that render manifests (`app diff`, `app manifests`) also need `pods/portforward` to the repo-server. Cluster-admin covers all of this.

## Configure the client

| Variable | Purpose |
|----------|---------|
| `MAIA_CLUSTER_API_URL` | Dashboard base URL, e.g. `https://maia.example.org` (dev server: `http://localhost:8000`) |
| `MAIA_CLUSTER_API_TOKEN` | The dashboard's `CLUSTER_API_TOKEN`, or a superuser bearer token |
| `MAIA_CLUSTER_API_CA_BUNDLE` | CA bundle for self-signed (private) clusters |
| `MAIA_CLUSTER_API_INSECURE` | `true` to skip TLS verification (last resort) |
| `MAIA_CLUSTER_READ_ONLY` | `true` to refuse all mutating commands client-side (dry runs allowed) |
| `MAIA_CLUSTER_MAX_OUTPUT_CHARS` | Per-stream output cap returned to the agent (default 60000) |

## MCP server

```bash
pip install -r Tools/maia-cluster/requirements.txt
python Tools/maia-cluster/mcp_server.py
```

```json
{
  "mcpServers": {
    "maia-cluster": {
      "command": "python",
      "args": ["/absolute/path/to/MAIA/Tools/maia-cluster/mcp_server.py"],
      "env": {
        "MAIA_CLUSTER_API_URL": "https://maia.example.org",
        "MAIA_CLUSTER_API_TOKEN": "<CLUSTER_API_TOKEN>"
      }
    }
  }
}
```

Claude Code: `claude mcp add maia-cluster -e MAIA_CLUSTER_API_URL=... -e MAIA_CLUSTER_API_TOKEN=... -- python /abs/path/Tools/maia-cluster/mcp_server.py`

| Tool | Kind | Purpose |
|------|------|---------|
| `cluster_api_status` | read | Connectivity, auth, versions, limits |
| `cluster_overview` | read | Nodes, unhealthy pods, warnings, failed Helm releases |
| `kubectl_get` / `kubectl_describe` | read | Inspect objects |
| `pod_logs` | read | Logs (tail/since/previous/selector/grep) |
| `cluster_events` | read | Recent (warning) events |
| `resource_usage` | read | `kubectl top` |
| `diagnose_workload` | read | Status + pods + events + logs + hints for one workload |
| `helm_info` | read | Helm list/status/history/values/manifest |
| `apply_manifest` | write | diff / dry-run / apply / create / replace / delete via stdin |
| `patch_resource`, `set_image`, `scale_workload`, `rollout` | write | In-place changes, restarts, rollbacks |
| `helm_upgrade`, `helm_rollback` | write | Helm changes |
| `argocd_apps`, `argocd_app_status`, `argocd_diff` | read | Argo CD application list / status / diff |
| `argocd_sync`, `argocd_terminate_op` | write | Sync (with dry run, prune, selective resources) / stop a sync |
| `argocd_rollback` | destructive | Roll back to a history ID |
| `delete_resource`, `helm_uninstall` | destructive | **Dry run by default** |
| `cluster_exec` | any | Raw kubectl/helm/argocd escape hatch |

Tools carry MCP `readOnlyHint` / `destructiveHint` annotations, so clients can
auto-approve reads and prompt for writes.

## Shell CLI (no dependencies)

```bash
export MAIA_CLUSTER_API_URL=https://maia.example.org MAIA_CLUSTER_API_TOKEN=...
python Tools/maia-cluster/maia_cluster.py status
python Tools/maia-cluster/maia_cluster.py overview
python Tools/maia-cluster/maia_cluster.py diagnose deployment/hub -n myproject
python Tools/maia-cluster/maia_cluster.py logs deployment/hub -n myproject --since 15m --grep error
python Tools/maia-cluster/maia_cluster.py kubectl get pods -A
python Tools/maia-cluster/maia_cluster.py kubectl apply -f - --dry-run=server < manifest.yaml
python Tools/maia-cluster/maia_cluster.py --json helm list -A
python Tools/maia-cluster/maia_cluster.py apps --problems
python Tools/maia-cluster/maia_cluster.py argocd app diff maia-core-loki
```

The exit code mirrors the remote command's (124 on timeout, 2 for API or validation errors).

## Layout

```
Tools/maia-cluster/
  SKILL.md          # agent instructions (workflows, limits, safety)
  mcp_server.py     # MCP stdio server
  maia_cluster.py   # shell CLI
  lib/
    client.py       # HTTP client (stdlib), config, error hints, read-only guard
    safety.py       # read/write classification, pre-validation mirroring the server rules
    ops.py          # task-level operations (overview, diagnose, logs, apply, helm, ...)
  tests/
```

Server side: [`MAIA/dashboard/apps/cluster_api/`](../../MAIA/dashboard/apps/cluster_api/).

## Tests

```bash
python -m pytest Tools/maia-cluster/tests -q
```
