# MAIA Dashboard — Cluster API (kubectl / helm)

The MAIA Dashboard runs inside the cluster with admin privileges. The **Cluster API** lets
external clients run `kubectl` and `helm` commands through the running dashboard, using the
dashboard pod's credentials.

> ⚠️ This endpoint gives callers whatever access the dashboard's credentials have (for an admin
> service account, that means the whole cluster). It is **disabled by default**. Only enable it
> with a long random token, and only expose it over HTTPS.

## Enabling

Set these environment variables on the dashboard deployment (for example in the
`maia-dashboard` Helm values under `env:`, or in `env.env`):

| Variable | Default | Description |
|---|---|---|
| `CLUSTER_API_ENABLED` | `False` | Turns the API on. While it is off, all endpoints return `404`. |
| `CLUSTER_API_TOKEN` | – | Shared secret token, e.g. from `openssl rand -hex 32`. |
| `CLUSTER_API_ALLOW_SUPERUSERS` | `True` | Also accepts dashboard **superusers** authenticated by the standard REST auth (DRF token, basic auth, Keycloak JWT). |
| `CLUSTER_API_ALLOWED_TOOLS` | `kubectl,helm` | Comma-separated list of tools that callers may run. |
| `CLUSTER_API_DEFAULT_TIMEOUT` | `60` | Default per-command timeout, in seconds. |
| `CLUSTER_API_MAX_TIMEOUT` | `300` | Upper limit on the `timeout` a caller can request. |
| `CLUSTER_API_MAX_OUTPUT_CHARS` | `1000000` | stdout and stderr are each cut off after this many characters. |
| `CLUSTER_API_RATE` | `600/hour` | Rate limit for each client IP. |
| `CLUSTER_API_KUBECONFIG` | `$KUBECONFIG` at startup | Kubeconfig to use. If empty, the pod's in-cluster service account is used. |
| `CLUSTER_API_KUBECTL_PATH` / `CLUSTER_API_HELM_PATH` | found on `PATH` | Paths to the binaries. The dashboard image is built on `maia-kube`, which already includes both. |

Example Helm values:

```yaml
env:
  - name: CLUSTER_API_ENABLED
    value: "True"
  - name: CLUSTER_API_TOKEN
    valueFrom:
      secretKeyRef:
        name: maia-dashboard-cluster-api
        key: token
```

The commands run with the dashboard's credentials. Make sure its service account (or
`CLUSTER_API_KUBECONFIG`) has the RBAC permissions that the commands you plan to run need.

## Authentication

Send the token in either of these headers:

* `Authorization: Bearer <CLUSTER_API_TOKEN>`
* `X-Cluster-Api-Token: <CLUSTER_API_TOKEN>`

Alternatively, authenticate as a dashboard superuser with the usual REST mechanisms. One example
is a Keycloak access token: `Authorization: Bearer <JWT>`. Users who are not superusers get `403`.

## Endpoints

### `GET /maia/cluster-api/`

Returns the status of the API, the tools that are available with their client versions, and the
type of credentials in use.

### `POST /maia/cluster-api/exec/`

The request body (JSON) takes one of these forms:

```json
{"tool": "kubectl", "args": ["get", "pods", "-A"]}
{"command": "helm list -A"}
{"command": "kubectl apply -f -", "stdin": "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: demo\n"}
{"command": "kubectl rollout status deploy/x -n y", "timeout": 120}
```

Response:

```json
{
  "tool": "kubectl",
  "args": ["get", "pods", "-A"],
  "command": "kubectl get pods -A",
  "exit_code": 0,
  "ok": true,
  "stdout": "...",
  "stderr": "",
  "duration_seconds": 0.412,
  "timed_out": false,
  "truncated": false
}
```

* `200` means the command ran. Check `ok` / `exit_code` to see whether it succeeded.
* `400` means the request was invalid or the command is not allowed.
* `401` / `403` mean authentication failed or the caller lacks permission.
* `404` means the API is disabled.
* `504` means the command timed out.

### curl examples

```bash
export MAIA=https://maia.example.com
export TOKEN=...   # CLUSTER_API_TOKEN

curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"command": "kubectl get nodes -o wide"}' $MAIA/maia/cluster-api/exec/ | jq -r .stdout

curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool": "helm", "args": ["list", "-A"]}' $MAIA/maia/cluster-api/exec/

# Apply a local manifest
jq -Rs '{command: "kubectl apply -f -", stdin: .}' manifest.yaml | \
  curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d @- $MAIA/maia/cluster-api/exec/
```

## Safety behaviour

* The API runs only `kubectl` or `helm`, and never through a shell. A `command` string is split
  with `shlex`, so `;`, `|`, `&&` and `$(...)` are passed to the tool as literal arguments.
* It rejects interactive commands and commands that never finish on their own: `kubectl edit`,
  `proxy`, `port-forward`, `attach`, `exec -it`, `get -w`, and `logs -f`. To read logs, use
  `--tail` or `--since` instead.
* It never inherits a `KUBECONFIG` that another dashboard view switched temporarily.
* Every call is written to the audit log with the caller, the client IP and the command. Values
  of `--from-literal`, `--set`, `--password` and `--token` are replaced with `***` in the log.
