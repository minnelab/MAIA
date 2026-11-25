"""Tests for the maia-cluster client, safety rules and task-level operations."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import ops  # noqa: E402
from lib.client import ClusterAPIClient, ClusterAPIConfig, ClusterAPIError, ReadOnlyViolation  # noqa: E402
from lib.safety import classify, positionals, precheck  # noqa: E402

TOKEN = "sk-test"


# --------------------------------------------------------------------------- safety


@pytest.mark.parametrize(
    "tool,args,expected",
    [
        ("kubectl", ["get", "pods", "-A"], "read"),
        ("kubectl", ["-n", "ns", "get", "pods"], "read"),
        ("kubectl", ["--namespace", "delete", "get", "pods"], "read"),  # namespace literally named 'delete'
        ("kubectl", ["logs", "pod", "--tail=10"], "read"),
        ("kubectl", ["rollout", "status", "deploy/x"], "read"),
        ("kubectl", ["rollout", "restart", "deploy/x"], "write"),
        ("kubectl", ["delete", "pod", "x"], "write"),
        ("kubectl", ["delete", "pod", "x", "--dry-run=server"], "read"),
        ("kubectl", ["apply", "-f", "-"], "write"),
        ("kubectl", ["diff", "-f", "-"], "read"),
        ("kubectl", ["auth", "can-i", "get", "pods"], "read"),
        ("kubectl", ["exec", "pod", "--", "ls"], "write"),
        ("kubectl", ["frobnicate"], "write"),  # unknown -> fail safe
        ("helm", ["list", "-A"], "read"),
        ("helm", ["get", "values", "r"], "read"),
        ("helm", ["upgrade", "r", "c", "--install"], "write"),
        ("helm", ["upgrade", "r", "c", "--dry-run=server"], "read"),
        ("helm", ["uninstall", "r", "--dry-run"], "read"),
        ("helm", ["repo", "add", "x", "https://x"], "write"),
        ("helm", ["repo", "list"], "read"),
        ("argocd", ["app", "list"], "read"),
        ("argocd", ["app", "get", "x", "-o", "json"], "read"),
        ("argocd", ["app", "diff", "x"], "read"),
        ("argocd", ["--loglevel", "debug", "app", "history", "x"], "read"),
        ("argocd", ["app", "sync", "x"], "write"),
        ("argocd", ["app", "sync", "x", "--dry-run"], "read"),
        ("argocd", ["app", "rollback", "x", "3"], "write"),
        ("argocd", ["app", "delete", "x"], "write"),
        ("argocd", ["proj", "list"], "read"),
    ],
)
def test_classify(tool, args, expected):
    assert classify(tool, args) == expected


def test_positionals_skip_flag_values():
    assert positionals("kubectl", ["-n", "ns", "logs", "-c", "app", "pod1"]) == ["logs", "pod1"]
    assert positionals("kubectl", ["exec", "pod", "--", "rm", "-rf"]) == ["exec", "pod"]


@pytest.mark.parametrize(
    "args",
    [
        ["edit", "deploy/x"],
        ["port-forward", "svc/x", "8080:80"],
        ["logs", "pod", "-f"],
        ["-n", "ns", "logs", "--follow", "pod"],  # flag before subcommand
        ["get", "pods", "-w"],
        ["exec", "-it", "pod", "--", "sh"],
    ],
)
def test_precheck_rejects(args):
    with pytest.raises(ValueError):
        precheck("kubectl", args)


@pytest.mark.parametrize(
    "args",
    [["login", "x"], ["context"], ["app", "edit", "x"], ["admin", "dashboard"], ["app", "logs", "x", "-f"],
     ["--server", "s", "app", "list"], ["--core", "app", "list"]],
)
def test_precheck_rejects_argocd(args):
    with pytest.raises(ValueError):
        precheck("argocd", args)


def test_precheck_allows_apply_dash_f():
    precheck("kubectl", ["apply", "-f", "-"])
    precheck("kubectl", ["exec", "pod", "--", "cat", "/etc/hostname"])


# --------------------------------------------------------------------------- config


def test_config_endpoint_normalisation():
    assert ClusterAPIConfig("https://m.org", "t").endpoint == "https://m.org/maia/cluster-api/"
    assert ClusterAPIConfig("https://m.org/", "t").endpoint == "https://m.org/maia/cluster-api/"
    assert ClusterAPIConfig("https://m.org/maia/cluster-api", "t").endpoint == "https://m.org/maia/cluster-api/"


def test_config_from_env_requires_values():
    with pytest.raises(ClusterAPIError, match="MAIA_CLUSTER_API_TOKEN"):
        ClusterAPIConfig.from_env({"MAIA_CLUSTER_API_URL": "http://x"})
    cfg = ClusterAPIConfig.from_env({"MAIA_CLUSTER_API_URL": "http://x", "MAIA_CLUSTER_API_TOKEN": "t",
                                     "MAIA_CLUSTER_READ_ONLY": "true"})
    assert cfg.read_only is True


# --------------------------------------------------------------------------- fake Cluster API server


class FakeAPI(BaseHTTPRequestHandler):
    calls: list = []
    responder = None  # callable(body) -> (status, payload)

    def log_message(self, *a):  # silence
        pass

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth_ok(self):
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def do_GET(self):  # noqa: N802
        if not self._auth_ok():
            return self._send(401, {"error": "Authentication required."})
        self._send(200, {"enabled": True, "caller": "cluster-api-token", "tools": {}})

    def do_POST(self):  # noqa: N802
        if not self._auth_ok():
            return self._send(401, {"error": "Authentication required."})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeAPI.calls.append(body)
        status, payload = FakeAPI.responder(body)
        self._send(status, payload)


def _result(body, stdout="", stderr="", code=0):
    return {"tool": body["tool"], "args": body["args"], "exit_code": code, "stdout": stdout, "stderr": stderr,
            "duration_seconds": 0.1, "timed_out": False, "truncated": False, "ok": code == 0,
            "command": " ".join([body["tool"], *body["args"]])}


@pytest.fixture()
def server():
    FakeAPI.calls = []
    FakeAPI.responder = lambda body: (200, _result(body, stdout="ok"))
    httpd = HTTPServer(("127.0.0.1", 0), FakeAPI)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_status_and_run(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    assert c.status()["caller"] == "cluster-api-token"
    res = c.kubectl("get", "pods", "-A")
    assert res["ok"] and res["stdout"] == "ok" and res["kind"] == "read"
    assert FakeAPI.calls[-1] == {"tool": "kubectl", "args": ["get", "pods", "-A"]}


def test_stdin_and_timeout_forwarded(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    c.run("kubectl", ["apply", "-f", "-"], stdin="kind: X", timeout=10)
    assert FakeAPI.calls[-1]["stdin"] == "kind: X"
    assert FakeAPI.calls[-1]["timeout"] == 10


def test_bad_token_raises_with_hint(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, "wrong"))
    with pytest.raises(ClusterAPIError) as exc:
        c.status()
    assert exc.value.status == 401 and "MAIA_CLUSTER_API_TOKEN" in str(exc.value)


def test_read_only_blocks_writes_but_not_dry_run(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN, read_only=True))
    with pytest.raises(ReadOnlyViolation):
        c.kubectl("delete", "pod", "x")
    assert c.kubectl("delete", "pod", "x", "--dry-run=server")["ok"]
    assert len(FakeAPI.calls) == 1


def test_failure_hints(server):
    FakeAPI.responder = lambda b: (200, _result(b, stderr="dial tcp: lookup api.x on 1.1.1.1:53: no such host",
                                                code=1))
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    res = c.kubectl("get", "nodes")
    assert not res["ok"] and any("resolve" in h for h in res["hints"])


def test_output_truncation_keeps_tail_for_logs(server):
    FakeAPI.responder = lambda b: (200, _result(b, stdout="old\n" * 100 + "NEWEST"))
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN, max_output_chars=50))
    res = ops.pod_logs(c, "pod1", "ns")
    assert res["truncated"] and res["stdout"].endswith("NEWEST")


def test_diff_exit_one_means_changes(server):
    FakeAPI.responder = lambda b: (200, _result(b, stdout="diff -u ...", code=1))
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    res = ops.apply_manifest(c, "kind: ConfigMap", "ns", mode="diff")
    assert res["ok"] and res["has_changes"]
    assert FakeAPI.calls[-1]["args"][:3] == ["diff", "-f", "-"]


def test_delete_defaults_to_dry_run(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    ops.delete_resource(c, "pod", "x", "ns")
    assert "--dry-run=server" in FakeAPI.calls[-1]["args"]
    with pytest.raises(ValueError):
        ops.delete_resource(c, "pod", None, "ns")


def test_helm_upgrade_values_via_stdin(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    ops.helm_upgrade(c, "r", "chart", "ns", repo="https://charts", values_yaml="a: 1", set_values={"b": 2},
                     dry_run=True)
    call = FakeAPI.calls[-1]
    assert call["tool"] == "helm" and call["stdin"] == "a: 1"
    assert ["-f", "-"] == call["args"][call["args"].index("-f"):call["args"].index("-f") + 2]
    assert "--dry-run=server" in call["args"] and "b=2" in call["args"]


# --------------------------------------------------------------------------- composite operations


def _pod(name, phase="Running", ready=True, restarts=0, waiting=None, last=None, labels=None):
    cs = {"name": "app", "ready": ready, "restartCount": restarts,
          "state": {"waiting": {"reason": waiting}} if waiting else {"running": {}}}
    if last:
        cs["lastState"] = {"terminated": {"reason": last, "exitCode": 137}}
    return {"metadata": {"name": name, "namespace": "ns", "labels": labels or {}},
            "spec": {"nodeName": "n1"}, "status": {"phase": phase, "containerStatuses": [cs]}}


def _responder_for(objects: dict):
    def respond(body):
        args = body["args"]
        key = " ".join(a for a in args if a not in ("-o", "json"))
        for prefix, payload in objects.items():
            if key.startswith(prefix):
                out = payload if isinstance(payload, str) else json.dumps(payload)
                return 200, _result(body, stdout=out)
        return 200, _result(body, stdout="")
    return respond


def test_diagnose_workload_crashloop(server):
    FakeAPI.responder = _responder_for({
        "get deployment/web -n ns": {"spec": {"replicas": 1, "selector": {"matchLabels": {"app": "web"}},
                                              "template": {"spec": {"containers": [{"name": "app", "image": "i"}]}}},
                                     "status": {"replicas": 1, "unavailableReplicas": 1}},
        "get pods -n ns -l app=web": {"items": [_pod("web-abc-1", ready=False, restarts=4,
                                                     waiting="CrashLoopBackOff", last="OOMKilled")]},
        "get events -n ns": {"items": [{"involvedObject": {"kind": "Pod", "name": "web-abc-1"}, "type": "Warning",
                                        "reason": "BackOff", "message": "Back-off restarting",
                                        "lastTimestamp": "2026-11-24T08:00:00Z"},
                                       {"involvedObject": {"kind": "Pod", "name": "other"}, "type": "Warning",
                                        "reason": "X", "lastTimestamp": "2026-11-24T08:00:00Z"}]},
        "logs web-abc-1 -n ns -c app --previous": "killed",
        "logs web-abc-1 -n ns -c app": "starting",
    })
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    rep = ops.diagnose_workload(c, "deploy/web", "ns")
    assert rep["target"] == "deployment/web" and rep["healthy"] is False
    assert rep["pods"][0]["reasons"] == ["CrashLoopBackOff", "OOMKilled"]
    assert [e["object"] for e in rep["events"]] == ["Pod/web-abc-1"]
    assert rep["logs"][0]["current"] == "starting" and rep["logs"][0]["previous"] == "killed"
    assert any(h.startswith("OOMKilled") for h in rep["hints"])


def test_cluster_overview(server):
    FakeAPI.responder = _responder_for({
        "get nodes": {"items": [{"metadata": {"name": "n1", "labels": {"node-role.kubernetes.io/control-plane": ""}},
                                 "status": {"conditions": [{"type": "Ready", "status": "True"}],
                                            "nodeInfo": {"kubeletVersion": "v1.30"}, "allocatable": {"cpu": "8"}},
                                 "spec": {}}]},
        "get pods -A --no-headers": (
            "ns ok Running true 0 <none> <none> <none> <none> n1\n"
            "ns bad Pending false 0 ImagePullBackOff <none> <none> <none> n1\n"
            "ns done Succeeded false 0 <none> <none> <none> <none> n1\n"
            "ns2 multi Running true,true 3,4 <none> <none> OOMKilled <none> n1\n"
            "ns2 waiting Pending <none> <none> <none> <none> <none> <none> <none>\n"
        ),
        "get events -A --field-selector type=Warning": {"items": []},
        "list -A --all": [{"name": "r1", "namespace": "ns", "status": "failed"},
                          {"name": "r2", "namespace": "ns", "status": "deployed"}],
    })
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    ov = ops.cluster_overview(c)
    assert ov["nodes"]["total"] == 1 and ov["nodes"]["items"][0]["roles"] == ["control-plane"]
    assert {p["name"] for p in ov["pods"]["unhealthy"]} == {"bad", "waiting"}
    assert ov["pods"]["high_restarts"] == [{"namespace": "ns2", "name": "multi", "restarts": 7}]
    assert any(h.startswith("ImagePullBackOff") for h in ov["hints"])
    assert [r["name"] for r in ov["helm"]["not_deployed"]] == ["r1"]
    assert "errors" not in ov


# --------------------------------------------------------------------------- MCP surface


def test_mcp_tools_listed():
    pytest.importorskip("mcp")
    import asyncio
    import importlib.util

    spec = importlib.util.spec_from_file_location("maia_cluster_mcp", ROOT / "mcp_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tools = asyncio.run(mod.list_tools())
    names = {t.name for t in tools}
    assert {"cluster_api_status", "cluster_overview", "diagnose_workload", "pod_logs", "apply_manifest",
            "helm_upgrade", "cluster_exec", "argocd_apps", "argocd_app_status", "argocd_diff", "argocd_sync",
            "argocd_rollback", "argocd_terminate_op"} <= names
    by_name = {t.name: t for t in tools}
    assert by_name["pod_logs"].annotations.readOnlyHint is True
    assert by_name["delete_resource"].annotations.destructiveHint is True
    assert by_name["argocd_apps"].annotations.readOnlyHint is True
    assert by_name["argocd_sync"].annotations.readOnlyHint is False


# --------------------------------------------------------------------------- argo cd


def test_argocd_apps_parses_jsonpath_table(server):
    rows = [
        ["maia-core-loki", "maia-core", "OutOfSync", "Missing", "", "", "2.9.9", "2.9.9",
         "https://grafana.github.io/helm-charts", "loki-stack", "observability", "", ""],
        ["maia-core-traefik", "maia-core", "Synced", "Healthy", '{"prune":true}', "Succeeded", "1", "1",
         "https://r", "traefik", "traefik", "", ""],
        ["maia-admin-rancher", "maia-admin", "Unknown", "Healthy", "", "", "", "2.13.0", "", "rancher",
         "cattle-system", "https://a https://b", "ComparisonError"],
    ]
    table = "".join("\t".join(r) + "\n" for r in rows)

    def respond(body):
        if body["args"][:1] == ["get"] and body["args"][1] == "applications.argoproj.io":
            assert body["args"][body["args"].index("-n") + 1] == "argocd"
            return 200, _result(body, stdout=table)
        return 200, _result(body)

    FakeAPI.responder = respond
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    c._argocd_namespace = "argocd"
    res = ops.argocd_apps(c, only_problems=True)
    assert res["total"] == 3 and res["out_of_sync"] == 1 and res["auto_sync"] == 1
    assert [a["name"] for a in res["applications"]] == ["maia-core-loki", "maia-admin-rancher"]
    rancher = res["applications"][1]
    assert rancher["conditions"] == ["ComparisonError"] and rancher["repo"] == "https://a https://b"


def test_argocd_app_status_condenses(server):
    app = {
        "spec": {"project": "maia-core", "source": {"repoURL": "r", "chart": "loki", "targetRevision": "2.9.9"},
                 "destination": {"namespace": "observability"}},
        "status": {
            "sync": {"status": "OutOfSync", "revision": "2.9.9"}, "health": {"status": "Missing"},
            "resources": [{"kind": "Service", "name": "a", "status": "OutOfSync", "health": {"status": "Missing"}},
                          {"kind": "ConfigMap", "name": "b", "status": "Synced", "health": {"status": "Healthy"}}],
            "operationState": {"phase": "Failed", "message": "one or more objects failed",
                               "syncResult": {"resources": [{"kind": "Job", "name": "j", "status": "SyncFailed",
                                                             "message": "boom"}]}},
            "history": [{"id": i, "revision": str(i)} for i in range(8)],
        },
    }
    FakeAPI.responder = lambda b: (200, _result(b, stdout=json.dumps(app)))
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    st = ops.argocd_app_status(c, "maia-core-loki", refresh="hard")
    assert FakeAPI.calls[-1]["args"] == ["app", "get", "maia-core-loki", "-o", "json", "--hard-refresh"]
    assert st["sync_policy"] == "manual" and st["health"] == "Missing"
    assert [r["name"] for r in st["resources_not_ok"]] == ["a"]
    assert st["last_operation"]["failed_resources"][0]["message"] == "boom"
    assert [h["id"] for h in st["history"]] == [3, 4, 5, 6, 7]


def test_argocd_sync_args(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    ops.argocd_sync(c, "app1", prune=True, resources=[":Service:ns/svc"], timeout_seconds=100)
    call = FakeAPI.calls[-1]
    assert call["tool"] == "argocd" and call["timeout"] == 130
    assert call["args"] == ["app", "sync", "app1", "--prune", "--resource", ":Service:ns/svc", "--timeout", "100"]
    ops.argocd_sync(c, "app1", wait=False)
    assert FakeAPI.calls[-1]["args"] == ["app", "sync", "app1", "--async"]


def test_argocd_sync_blocked_in_read_only_but_dry_run_allowed(server):
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN, read_only=True))
    with pytest.raises(ReadOnlyViolation):
        ops.argocd_sync(c, "app1")
    assert ops.argocd_sync(c, "app1", dry_run=True)["kind"] == "read"


def test_argocd_diff_exit_one(server):
    FakeAPI.responder = lambda b: (200, _result(b, stdout="===== /Service x ======", code=1))
    c = ClusterAPIClient(ClusterAPIConfig(server, TOKEN))
    res = ops.argocd_diff(c, "app1")
    assert res["ok"] and res["has_changes"]
