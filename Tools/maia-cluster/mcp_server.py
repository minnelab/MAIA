#!/usr/bin/env python3
"""
MAIA Cluster MCP Server — stdio transport.

Lets an agent monitor, troubleshoot and change a MAIA Kubernetes cluster
through the MAIA Dashboard Cluster API (``/maia/cluster-api/``), which runs
``kubectl`` / ``helm`` / ``argocd --core`` server-side with the dashboard's cluster credentials.
The agent never needs a kubeconfig.

Usage
-----
    MAIA_CLUSTER_API_URL=https://maia.example.org \\
    MAIA_CLUSTER_API_TOKEN=... \\
    python Tools/maia-cluster/mcp_server.py

Cursor / Claude Code example::

    {
      "mcpServers": {
        "maia-cluster": {
          "command": "python",
          "args": ["/path/to/MAIA/Tools/maia-cluster/mcp_server.py"],
          "env": {
            "MAIA_CLUSTER_API_URL": "https://maia.example.org",
            "MAIA_CLUSTER_API_TOKEN": "<CLUSTER_API_TOKEN>",
            "MAIA_CLUSTER_READ_ONLY": "false"
          }
        }
      }
    }
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from mcp import types as mcp_types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:
    print("ERROR: 'mcp' package not found. Install with: pip install -r Tools/maia-cluster/requirements.txt",
          file=sys.stderr)
    sys.exit(1)

from lib import ops  # noqa: E402
from lib.client import ClusterAPIClient, ClusterAPIError  # noqa: E402

app = Server("maia-cluster")
_client: ClusterAPIClient | None = None


def client() -> ClusterAPIClient:
    global _client
    if _client is None:
        _client = ClusterAPIClient()
    return _client


def _json(data) -> list:
    return [mcp_types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


# --------------------------------------------------------------------------- schema helpers

def _s(desc: str, **kw) -> dict:
    return {"type": "string", "description": desc, **kw}


def _i(desc: str, **kw) -> dict:
    return {"type": "integer", "description": desc, **kw}


def _b(desc: str, **kw) -> dict:
    return {"type": "boolean", "description": desc, **kw}


NS = _s("Namespace. MAIA project namespaces are named after the project group (lowercase, '-' for '_').")
READ = mcp_types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
WRITE = mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
DESTRUCTIVE = mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False,
                                        openWorldHint=True)

# name -> (description, properties, required, annotations, handler(args))
TOOLS: dict[str, tuple] = {
    "cluster_api_status": (
        "Check connectivity to the MAIA Dashboard Cluster API: whether it is enabled, the caller identity, "
        "kubectl/helm/argocd versions, credentials mode, Argo CD namespace and timeout limits. Call this first.",
        {}, [], READ,
        lambda a: client().status(),
    ),
    "cluster_overview": (
        "One-call health summary: node readiness/pressure, pod counts by phase, unhealthy pods with reasons, "
        "pods with many restarts, the 20 most recent Warning events, Helm releases not in 'deployed' state and "
        "Argo CD Applications that are OutOfSync/unhealthy. "
        "Omit namespace for the whole cluster.",
        {"namespace": NS, "max_items": _i("Max unhealthy pods to list (default 50)")}, [], READ,
        lambda a: ops.cluster_overview(client(), a.get("namespace"), int(a.get("max_items") or 50)),
    ),
    "kubectl_get": (
        "List or fetch Kubernetes objects (kubectl get). Use output='json'/'yaml' for full objects, "
        "'wide' (default) for tables, or 'jsonpath=...' / 'custom-columns=...'.",
        {
            "kind": _s("Resource kind, e.g. pods, deployments, svc, pvc, ingress, nodes, helmreleases, "
                       "applications.argoproj.io; comma-separated for several"),
            "name": _s("Object name (optional)"),
            "namespace": NS,
            "all_namespaces": _b("Search all namespaces (-A)"),
            "selector": _s("Label selector, e.g. app=jupyterhub"),
            "field_selector": _s("Field selector, e.g. status.phase!=Running"),
            "output": _s("Output format (default wide)"),
        }, ["kind"], READ,
        lambda a: ops.get_resources(client(), a["kind"], a.get("name"), a.get("namespace"),
                                    bool(a.get("all_namespaces")), a.get("selector"), a.get("field_selector"),
                                    a.get("output") or "wide"),
    ),
    "kubectl_describe": (
        "kubectl describe: human-readable detail of an object including its recent events.",
        {"kind": _s("Resource kind"), "name": _s("Object name (optional with selector)"), "namespace": NS,
         "selector": _s("Label selector")}, ["kind"], READ,
        lambda a: ops.describe(client(), a["kind"], a.get("name"), a.get("namespace"), a.get("selector")),
    ),
    "pod_logs": (
        "Fetch container logs (non-streaming). target is a pod name or 'deployment/NAME' (picks one pod). "
        "Use selector to aggregate across all matching pods. Use previous=true for the crashed instance. "
        "To monitor, call again with since='2m'. Output keeps the newest lines when truncated.",
        {
            "target": _s("Pod name or kind/name (deployment/x, statefulset/x, job/x)"),
            "namespace": NS,
            "container": _s("Container name (multi-container pods)"),
            "tail": _i("Number of most recent lines (default 200; -1 for all)"),
            "since": _s("Only logs newer than a duration, e.g. 10m, 1h"),
            "previous": _b("Logs of the previous (crashed) container instance"),
            "all_containers": _b("Include all containers"),
            "selector": _s("Label selector instead of target (logs of all matching pods, prefixed)"),
            "grep": _s("Case-insensitive substring filter applied to returned lines"),
            "timestamps": _b("Prefix lines with timestamps"),
        }, ["namespace"], READ,
        lambda a: ops.pod_logs(client(), a.get("target", ""), a.get("namespace"), a.get("container"),
                               int(a["tail"]) if a.get("tail") is not None else 200, a.get("since"),
                               bool(a.get("previous")), bool(a.get("all_containers")), a.get("selector"),
                               a.get("grep"), bool(a.get("timestamps"))),
    ),
    "cluster_events": (
        "Recent Kubernetes events (oldest first, newest last), optionally only Warnings and/or for one object "
        "(for_object='pod/x', 'deployment/y', 'node/z').",
        {"namespace": NS, "for_object": _s("kind/name to filter on"), "warnings_only": _b("Only type=Warning"),
         "limit": _i("Max events returned (default 50)")}, [], READ,
        lambda a: ops.events(client(), a.get("namespace"), a.get("for_object"), bool(a.get("warnings_only")),
                             int(a.get("limit") or 50)),
    ),
    "resource_usage": (
        "Live CPU/memory usage (kubectl top; requires metrics-server).",
        {"scope": _s("'nodes' or 'pods'", enum=["nodes", "pods"]), "namespace": NS,
         "containers": _b("Per-container breakdown (pods only)"),
         "sort_by": _s("cpu or memory", enum=["cpu", "memory"])}, [], READ,
        lambda a: ops.resource_usage(client(), a.get("scope") or "nodes", a.get("namespace"),
                                     bool(a.get("containers")), a.get("sort_by")),
    ),
    "diagnose_workload": (
        "Troubleshoot a workload in one call: rollout status and conditions, pods with container states and "
        "restart reasons, related events, current + previous logs of failing containers, and remediation hints "
        "(ImagePullBackOff, CrashLoopBackOff, OOMKilled, FailedScheduling, FailedMount, ...).",
        {"target": _s("deployment/x, statefulset/x, daemonset/x, job/x, pod/x or a pod name"), "namespace": NS,
         "log_tail": _i("Log lines per container (default 80)")}, ["target", "namespace"], READ,
        lambda a: ops.diagnose_workload(client(), a["target"], a["namespace"], int(a.get("log_tail") or 80)),
    ),
    "apply_manifest": (
        "Create/update objects from a YAML or JSON manifest (sent via stdin). ALWAYS run mode='diff' or "
        "'dry-run' first and show the user the change, then mode='apply'. mode='delete' deletes the objects "
        "in the manifest.",
        {"manifest": _s("Full YAML/JSON manifest (multi-document allowed)"), "namespace": NS,
         "mode": _s("diff | dry-run | apply | create | replace | delete (default apply)",
                    enum=["diff", "dry-run", "apply", "create", "replace", "delete"]),
         "server_side": _b("Use server-side apply")}, ["manifest"], WRITE,
        lambda a: ops.apply_manifest(client(), a["manifest"], a.get("namespace"), a.get("mode") or "apply",
                                     bool(a.get("server_side"))),
    ),
    "patch_resource": (
        "Patch an object in place (kubectl patch), e.g. change env, resources, labels, annotations.",
        {"resource": _s("kind/name, e.g. deployment/web"), "namespace": NS,
         "patch": {"type": ["object", "string"], "description": "Patch body (object or JSON string)"},
         "patch_type": _s("strategic (default) | merge | json", enum=["strategic", "merge", "json"]),
         "dry_run": _b("Server-side dry run only")}, ["resource", "patch"], WRITE,
        lambda a: ops.patch_resource(client(), a["resource"], a["patch"], a.get("namespace"),
                                     a.get("patch_type") or "strategic", bool(a.get("dry_run"))),
    ),
    "set_image": (
        "Change a container image of a workload (triggers a rollout).",
        {"resource": _s("kind/name, e.g. deployment/web"), "container": _s("Container name"),
         "image": _s("New image reference"), "namespace": NS, "dry_run": _b("Server-side dry run only")},
        ["resource", "container", "image", "namespace"], WRITE,
        lambda a: ops.set_image(client(), a["resource"], a["container"], a["image"], a["namespace"],
                                bool(a.get("dry_run"))),
    ),
    "rollout": (
        "Manage workload rollouts: status (waits up to wait_seconds), history, restart (rolling restart), "
        "undo (roll back, optionally to_revision), pause, resume.",
        {"action": _s("status | history | restart | undo | pause | resume",
                      enum=["status", "history", "restart", "undo", "pause", "resume"]),
         "resource": _s("deployment/x, statefulset/x or daemonset/x"), "namespace": NS,
         "to_revision": _i("Revision for undo"), "wait_seconds": _i("Timeout for status (default 120)")},
        ["action", "resource", "namespace"], WRITE,
        lambda a: ops.rollout(client(), a["action"], a["resource"], a["namespace"], a.get("to_revision"),
                              int(a.get("wait_seconds") or 120)),
    ),
    "scale_workload": (
        "Scale a deployment/statefulset/replicaset to N replicas (0 stops it).",
        {"resource": _s("kind/name"), "replicas": _i("Desired replicas"), "namespace": NS,
         "dry_run": _b("Server-side dry run only")}, ["resource", "replicas", "namespace"], WRITE,
        lambda a: ops.scale(client(), a["resource"], int(a["replicas"]), a["namespace"], bool(a.get("dry_run"))),
    ),
    "delete_resource": (
        "Delete objects by name or label selector. DEFAULTS TO A DRY RUN: review the output, confirm with the "
        "user, then call again with dry_run=false.",
        {"kind": _s("Resource kind"), "name": _s("Object name"), "namespace": NS,
         "selector": _s("Label selector (instead of name)"),
         "dry_run": _b("Default true. Set false to really delete."),
         "wait": _b("Wait for finalizers to complete")}, ["kind"], DESTRUCTIVE,
        lambda a: ops.delete_resource(client(), a["kind"], a.get("name"), a.get("namespace"), a.get("selector"),
                                      a.get("dry_run", True) is not False, bool(a.get("wait"))),
    ),
    "helm_info": (
        "Inspect Helm releases: list (all namespaces when namespace omitted), status, history, values "
        "(computed), manifest, notes, all.",
        {"action": _s("list | status | history | values | manifest | notes | all",
                      enum=["list", "status", "history", "values", "manifest", "notes", "all"]),
         "release": _s("Release name (not needed for list)"), "namespace": NS,
         "revision": _i("Specific revision")}, ["action"], READ,
        lambda a: ops.helm_info(client(), a["action"], a.get("release"), a.get("namespace"), a.get("revision")),
    ),
    "helm_upgrade": (
        "Install or upgrade a Helm release (helm upgrade --install). Run with dry_run=true first. "
        "chart is 'repo/chart', 'oci://...' or a chart name with repo=<URL>. values_yaml is sent via stdin. "
        "Use reuse_values=true to change only the given set_values on an existing release.",
        {"release": _s("Release name"), "chart": _s("Chart reference"), "namespace": NS,
         "repo": _s("Chart repository URL (optional)"), "version": _s("Chart version"),
         "values_yaml": _s("Values file content (YAML)"),
         "set_values": {"type": "object", "description": "--set key=value pairs", "additionalProperties": True},
         "install": _b("Install if missing (default true)"), "reuse_values": _b("Reuse the release's values"),
         "create_namespace": _b("Create the namespace if missing"), "dry_run": _b("Server-side dry run"),
         "wait": _b("Wait until resources are ready"), "timeout_seconds": _i("Wait timeout (default 300)")},
        ["release", "chart", "namespace"], WRITE,
        lambda a: ops.helm_upgrade(client(), a["release"], a["chart"], a["namespace"], a.get("repo"),
                                   a.get("version"), a.get("values_yaml"), a.get("set_values"),
                                   a.get("install", True) is not False, bool(a.get("reuse_values")),
                                   bool(a.get("create_namespace")), bool(a.get("dry_run")), bool(a.get("wait")),
                                   int(a.get("timeout_seconds") or 300)),
    ),
    "helm_rollback": (
        "Roll a Helm release back to a previous revision (default: the previous one). Check helm_info history first.",
        {"release": _s("Release name"), "namespace": NS, "revision": _i("Target revision"),
         "dry_run": _b("Dry run")}, ["release", "namespace"], WRITE,
        lambda a: ops.helm_rollback(client(), a["release"], a["namespace"], a.get("revision"),
                                    bool(a.get("dry_run"))),
    ),
    "helm_uninstall": (
        "Uninstall a Helm release. DEFAULTS TO A DRY RUN: confirm with the user, then call with dry_run=false.",
        {"release": _s("Release name"), "namespace": NS, "dry_run": _b("Default true"),
         "keep_history": _b("Keep release history")}, ["release", "namespace"], DESTRUCTIVE,
        lambda a: ops.helm_uninstall(client(), a["release"], a["namespace"], a.get("dry_run", True) is not False,
                                     bool(a.get("keep_history"))),
    ),
    "argocd_apps": (
        "List Argo CD Applications (MAIA's platform components and projects) with sync status, health, auto-sync, "
        "last operation phase, source and destination namespace. only_problems=true keeps OutOfSync / unhealthy / "
        "erroring ones.",
        {"project": _s("Argo CD project filter, e.g. maia-core, maia-admin, or a MAIA project id"),
         "only_problems": _b("Only OutOfSync, unhealthy, erroring or running apps")}, [], READ,
        lambda a: ops.argocd_apps(client(), a.get("project"), bool(a.get("only_problems"))),
    ),
    "argocd_app_status": (
        "Condensed 'argocd app get': sync/health, sync policy, conditions (ComparisonError, ...), last operation "
        "with failed resources, the resources that are OutOfSync or unhealthy, and recent history IDs. "
        "refresh='normal'|'hard' re-reads Git / re-renders the chart first.",
        {"name": _s("Application name, e.g. maia-core-loki"),
         "refresh": _s("normal | hard", enum=["normal", "hard"])}, ["name"], READ,
        lambda a: ops.argocd_app_status(client(), a["name"], a.get("refresh")),
    ),
    "argocd_diff": (
        "Show what a sync would change (live vs desired manifests). has_changes=false means in sync.",
        {"name": _s("Application name"), "refresh": _b("Hard-refresh first"),
         "server_side": _b("Server-side generate manifests")}, ["name"], READ,
        lambda a: ops.argocd_diff(client(), a["name"], bool(a.get("refresh")), bool(a.get("server_side"))),
    ),
    "argocd_sync": (
        "Sync an Argo CD Application (deploys the desired state). ALWAYS call argocd_diff or dry_run=true first and "
        "get the user's confirmation. prune=true deletes resources no longer in Git/chart. resources limits the "
        "sync to GROUP:KIND:NAME or GROUP:KIND:NAMESPACE/NAME entries (empty group for core kinds). "
        "wait=false starts it asynchronously; then poll argocd_app_status.",
        {"name": _s("Application name"), "dry_run": _b("Dry run only"), "prune": _b("Prune extraneous resources"),
         "resources": {"type": "array", "items": {"type": "string"}, "description": "Selective sync"},
         "revision": _s("Sync to a specific revision"), "apply_out_of_sync_only": _b("Only apply OutOfSync"),
         "server_side": _b("Server-side apply"), "wait": _b("Wait for completion (default true)"),
         "timeout_seconds": _i("Wait timeout (default 240)")}, ["name"], WRITE,
        lambda a: ops.argocd_sync(client(), a["name"], bool(a.get("dry_run")), bool(a.get("prune")),
                                  a.get("resources"), a.get("revision"), bool(a.get("apply_out_of_sync_only")),
                                  bool(a.get("server_side")), a.get("wait", True) is not False,
                                  int(a.get("timeout_seconds") or 240)),
    ),
    "argocd_rollback": (
        "Roll an Application back to a previous history ID (see argocd_app_status.history). Disables auto-sync on "
        "the app. Confirm with the user first.",
        {"name": _s("Application name"), "history_id": _i("History ID (default: previous)")}, ["name"], DESTRUCTIVE,
        lambda a: ops.argocd_rollback(client(), a["name"], a.get("history_id")),
    ),
    "argocd_terminate_op": (
        "Terminate the running sync operation of an Application (e.g. a stuck hook).",
        {"name": _s("Application name")}, ["name"], WRITE,
        lambda a: ops.argocd_terminate_op(client(), a["name"]),
    ),
    "cluster_exec": (
        "Escape hatch: run any kubectl, helm or argocd command through the dashboard. Use the dedicated tools "
        "when they fit. argocd always runs as 'argocd --core' (no login/context/--server). Not supported: edit, "
        "proxy, port-forward, attach, -it/--stdin, --watch, logs --follow. "
        "Pass manifests/values through stdin with '-f -'; paths refer to the dashboard server, not your machine. "
        "One-shot exec works: 'kubectl exec POD -n NS -- ls /data'.",
        {"command": _s("Full command line, e.g. 'kubectl get pvc -A', 'helm list -A', 'argocd app history x'"),
         "stdin": _s("Data piped to the command's stdin"),
         "timeout": _i("Seconds (capped by the dashboard's CLUSTER_API_MAX_TIMEOUT)")}, ["command"], DESTRUCTIVE,
        lambda a: client().run_command(a["command"], stdin=a.get("stdin"),
                                       timeout=float(a["timeout"]) if a.get("timeout") else None),
    ),
}


@app.list_tools()
async def list_tools():
    return [
        mcp_types.Tool(
            name=name,
            description=desc,
            inputSchema={"type": "object", "properties": props, "required": required},
            annotations=ann,
        )
        for name, (desc, props, required, ann, _) in TOOLS.items()
    ]


def _dispatch(name: str, args: dict):
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    return TOOLS[name][4](args)


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        return _json(await asyncio.to_thread(_dispatch, name, arguments or {}))
    except ClusterAPIError as exc:
        return _json({"error": str(exc), "tool": name, "http_status": exc.status})
    except (ValueError, KeyError) as exc:
        return _json({"error": f"Invalid request: {exc}", "tool": name})
    except Exception as exc:  # noqa: BLE001
        return _json({"error": f"{type(exc).__name__}: {exc}", "tool": name})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
