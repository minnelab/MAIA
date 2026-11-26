#!/usr/bin/env python3
"""Print a Markdown manifest of what a MAIA cluster actually runs. Runs on the guest (60_verify.sh, check 7).

Sections: MAIA (pip package + git commit on the node, and in the dashboard pod), k3s node, ArgoCD apps (source repo,
chart/path, target and synced revision), Helm releases, and every running container image with its digest and the
workloads that use it. Only the first line (the timestamp) changes between identical runs, so manifests diff cleanly.
No env values or secrets are read; credentials embedded in URLs are masked.
"""
import datetime
import importlib.metadata as md
import json
import re
import subprocess

K = ["sudo", "-n", "k3s", "kubectl"]
HELM = ["sudo", "-n", "helm", "--kubeconfig", "/etc/rancher/k3s/k3s.yaml"]


def sh(cmd, default=""):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True).stdout
    except Exception:  # noqa: BLE001 - a missing tool/section must not abort the manifest
        return default


def kjson(*args):
    out = sh(K + list(args) + ["-o", "json"])
    return json.loads(out) if out else {"items": []}


def mask(url):
    return re.sub(r"//[^/@\s]+@", "//***@", str(url or ""))


def cell(v):
    return str(v if v not in (None, "") else "-").replace("|", "/")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out


def maia_node():
    try:
        d = md.distribution("maia-toolkit")
        du = json.loads(d.read_text("direct_url.json") or "{}")
        vcs = du.get("vcs_info", {})
        return d.version, du.get("url"), vcs.get("commit_id"), vcs.get("requested_revision")
    except Exception:  # noqa: BLE001
        return None, None, None, None


def workload(pod):
    owners = pod["metadata"].get("ownerReferences") or []
    if not owners:
        return pod["metadata"]["name"]
    o = owners[0]
    name = o["name"]
    if o["kind"] == "ReplicaSet":
        name = re.sub(r"-[a-z0-9]{6,10}$", "", name)
    elif o["kind"] == "Job":
        name = re.sub(r"-[0-9]{6,}$", "", name)
    return name


def main():
    lines = [f"<!-- generated {datetime.datetime.now().astimezone().isoformat(timespec='seconds')} -->",
             "# Deployed versions", ""]

    ver, url, commit, req = maia_node()
    lines += ["## MAIA", ""]
    rows = [["node (pip, ~/.local)", ver, mask(url), commit, req]]
    pods = kjson("get", "pods", "-A")["items"]
    dash = [p for p in pods if p["metadata"]["namespace"] == "maia-dashboard"
            and p["status"].get("phase") == "Running" and "mongodb" not in p["metadata"]["name"]
            and "minio" not in p["metadata"]["name"]]
    if dash:
        p = dash[0]
        c = p["spec"]["containers"][0]
        tag = next((e.get("value") for e in c.get("env", []) if e.get("name") == "MAIA_TAG"), None)
        dver = sh(K + ["-n", "maia-dashboard", "exec", p["metadata"]["name"], "-c", c["name"], "--", "python", "-c",
                       "import importlib.metadata as m; print(m.version('maia-toolkit'))"]).strip()
        rows.append(["dashboard pod", dver, "MAIA_TAG", tag, None])
    lines += table(["where", "maia-toolkit", "source", "commit / tag", "requested"], rows) + [""]

    lines += ["## k3s", ""]
    rows = []
    for n in kjson("get", "nodes")["items"]:
        i = n["status"]["nodeInfo"]
        rows.append([n["metadata"]["name"], i.get("kubeletVersion"), i.get("osImage"), i.get("kernelVersion"),
                     i.get("containerRuntimeVersion")])
    lines += table(["node", "k3s", "os", "kernel", "runtime"], sorted(rows)) + [""]

    lines += ["## ArgoCD applications", ""]
    rows = []
    for a in kjson("get", "applications", "-n", "argocd")["items"]:
        spec, st = a.get("spec", {}), a.get("status", {})
        srcs = spec.get("sources") or [spec.get("source") or {}]
        synced = st.get("sync", {}).get("revisions") or [st.get("sync", {}).get("revision")]
        for i, s in enumerate(srcs):
            rows.append([a["metadata"]["name"] + (f" [{i}]" if len(srcs) > 1 else ""), mask(s.get("repoURL")),
                         s.get("chart") or s.get("path"), s.get("targetRevision"),
                         (synced[i] if i < len(synced) else None),
                         f"{st.get('sync', {}).get('status', '-')}/{st.get('health', {}).get('status', '-')}"])
    lines += table(["app", "repo", "chart / path", "target", "synced revision", "sync/health"], sorted(rows)) + [""]

    lines += ["## Helm releases", ""]
    try:
        rel = json.loads(sh(HELM + ["list", "-A", "-o", "json"], "[]") or "[]")
    except ValueError:
        rel = []
    rows = [[r.get("name"), r.get("namespace"), r.get("chart"), r.get("app_version"), r.get("revision")] for r in rel]
    lines += table(["release", "namespace", "chart", "app version", "revision"], sorted(rows)) + [""]

    lines += ["## Container images (running pods)", ""]
    images = {}
    for p in pods:
        if p["status"].get("phase") not in ("Running", "Succeeded"):
            continue
        ns = p["metadata"]["namespace"]
        for cs in (p["status"].get("containerStatuses") or []) + (p["status"].get("initContainerStatuses") or []):
            digest = (cs.get("imageID") or "").rsplit("@", 1)[-1] if "@" in (cs.get("imageID") or "") else cs.get("imageID")
            images.setdefault((cs.get("image"), digest), set()).add(f"{ns}/{workload(p)}")
    rows = [[img, dg, ", ".join(sorted(w))] for (img, dg), w in images.items()]
    lines += table(["image", "digest", "used by"], sorted(rows, key=lambda r: (str(r[0]), str(r[1])))) + [""]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
