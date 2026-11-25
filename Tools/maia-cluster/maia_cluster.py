#!/usr/bin/env python3
"""
Shell CLI for the MAIA Dashboard Cluster API (no dependencies beyond Python 3.9+).

For agents/users without MCP. Reads MAIA_CLUSTER_API_URL / MAIA_CLUSTER_API_TOKEN.

Examples
--------
    maia_cluster.py status
    maia_cluster.py overview [-n NS]
    maia_cluster.py diagnose deployment/jupyterhub -n maia-core
    maia_cluster.py logs deployment/web -n proj --since 10m
    maia_cluster.py kubectl get pods -A                      # passthrough
    maia_cluster.py kubectl apply -f - < manifest.yaml       # stdin is forwarded
    maia_cluster.py helm upgrade r chart -n ns -f - < values.yaml
    maia_cluster.py argocd app sync maia-core-loki --dry-run  # runs as argocd --core
    maia_cluster.py apps [--problems]                         # Argo CD application summary
    maia_cluster.py --json kubectl get nodes                 # full JSON result

Exit code mirrors the remote command's exit code (2 for API/validation errors).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import ops  # noqa: E402
from lib.client import ClusterAPIClient, ClusterAPIError  # noqa: E402


def _print_result(res: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(res, indent=2, default=str))
    else:
        if res.get("stdout"):
            sys.stdout.write(res["stdout"] if res["stdout"].endswith("\n") else res["stdout"] + "\n")
        if res.get("stderr"):
            sys.stderr.write(res["stderr"] if res["stderr"].endswith("\n") else res["stderr"] + "\n")
        for h in res.get("hints", []):
            sys.stderr.write(f"hint: {h}\n")
    if res.get("timed_out"):
        return 124
    code = res.get("exit_code")
    return 0 if res.get("ok") else (code if isinstance(code, int) and code > 0 else 1)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    as_json = False
    timeout = None
    while argv and argv[0] in ("--json", "--timeout"):
        if argv[0] == "--json":
            as_json, argv = True, argv[1:]
        else:
            timeout, argv = float(argv[1]), argv[2:]

    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    try:
        client = ClusterAPIClient()
        head = argv[0]
        if head in ("kubectl", "helm", "argocd"):
            stdin = None
            if "-" in argv and not sys.stdin.isatty():
                stdin = sys.stdin.read()
            return _print_result(client.run(head, argv[1:], stdin=stdin, timeout=timeout), as_json)

        p = argparse.ArgumentParser(prog="maia_cluster.py")
        sub = p.add_subparsers(dest="cmd", required=True)
        sub.add_parser("status")
        o = sub.add_parser("overview")
        o.add_argument("-n", "--namespace")
        d = sub.add_parser("diagnose")
        d.add_argument("target")
        d.add_argument("-n", "--namespace", required=True)
        d.add_argument("--log-tail", type=int, default=80)
        lg = sub.add_parser("logs")
        lg.add_argument("target", nargs="?", default="")
        lg.add_argument("-n", "--namespace", required=True)
        lg.add_argument("-c", "--container")
        lg.add_argument("-l", "--selector")
        lg.add_argument("--tail", type=int, default=200)
        lg.add_argument("--since")
        lg.add_argument("--previous", action="store_true")
        lg.add_argument("--grep")
        ev = sub.add_parser("events")
        ev.add_argument("-n", "--namespace")
        ev.add_argument("--for", dest="for_object")
        ev.add_argument("--warnings", action="store_true")
        ev.add_argument("--limit", type=int, default=50)
        ap = sub.add_parser("apps")
        ap.add_argument("--problems", action="store_true")
        ap.add_argument("--project")
        a = p.parse_args(argv)

        if a.cmd == "status":
            data = client.status()
        elif a.cmd == "overview":
            data = ops.cluster_overview(client, a.namespace)
        elif a.cmd == "diagnose":
            data = ops.diagnose_workload(client, a.target, a.namespace, a.log_tail)
        elif a.cmd == "apps":
            data = ops.argocd_apps(client, a.project, a.problems)
        elif a.cmd == "events":
            data = ops.events(client, a.namespace, a.for_object, a.warnings, a.limit)
        else:  # logs
            return _print_result(ops.pod_logs(client, a.target, a.namespace, a.container, a.tail, a.since,
                                              a.previous, selector=a.selector, grep=a.grep), as_json)
        print(json.dumps(data, indent=2, default=str))
        return 0
    except ClusterAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
