#!/usr/bin/env python3
"""Compile a deployment's overrides.yaml into Ansible extra-vars for install-maia.yml.

Usage: overrides.py <overrides.yaml|-> <versions.py> <config.yaml.j2> <out.vars.yml>

overrides.yaml (all sections optional; see profiles/example.yaml):
  images:
    registry: <host/path>            -> MAIA_REGISTRY (dashboard, gpu-booking, project images read it)
    <image-name>: <tag> | {tag: <tag>}
                                     -> <IMAGE_NAME>_IMAGE_VERSION (must exist in MAIA/versions.py)
                                        maia-dashboard -> ansible var maia_dashboard_image_version
  charts:
    ref: <git ref>                   -> every git-sourced MAIA chart (maia_branch_chart_keys) and MAIA_CHART_GIT_REF
    <CHART-NAME>: <version> | {version: <v>, type: git_repo|helm_repo}
                                     -> <CHART_NAME>_CHART_VERSION / _CHART_TYPE (must exist in MAIA/versions.py)
  env:
    <KEY>: <value>                   -> raw config.yaml env: key, not validated (no secrets: they belong in secrets.env)

Not supported yet (needs MAIA changes, step 2 of the plan): charts.git_repo / charts.helm_repo (MAIA_PRIVATE_REGISTRY is
shared by git charts, Helm charts and images) and values: (no per-app Helm values hook in MAIA's generators).
Exit 0 and print the effective overrides on success; exit 1 with every error listed otherwise. Prints no values from env:
for keys that look secret (they are rejected anyway).
"""
import re
import sys

import yaml

SECRET_RE = re.compile(r"PASS|SECRET|TOKEN|_KEY$|^KEY", re.I)
# Not in versions.py but read by MAIA when building image names.
EXTRA_KNOWN = {"MAIA_REGISTRY"}


def norm(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_").upper()


def known_env_keys(versions_src: str) -> set:
    keys = set(re.findall(r"""os\.environ\.get\(\s*["']([A-Za-z0-9_]+)["']""", versions_src))
    keys |= set(re.findall(r"""["']([A-Za-z0-9_]+)["']\s+in\s+os\.environ""", versions_src))
    return keys | EXTRA_KNOWN


def template_env_keys(template_src: str) -> set:
    """Keys the template writes itself under env: (an override of one would duplicate the YAML key)."""
    keys, in_env = set(), False
    for line in template_src.splitlines():
        if re.match(r"^env:\s*$", line):
            in_env = True
            continue
        if in_env and re.match(r"^\S", line) and not line.startswith("{%"):
            break
        m = re.match(r"^  ([A-Za-z0-9_]+):", line) if in_env else None
        if m:
            keys.add(m.group(1))
    return keys


def scalar(v):
    if isinstance(v, (dict, list)) or v is None:
        raise ValueError("expected a string or number")
    return str(v)


def main(argv):
    if len(argv) != 5:
        print(__doc__)
        return 2
    src, versions_path, template_path, out_path = argv[1:]
    data = {} if src == "-" else (yaml.safe_load(open(src)) or {})
    known = known_env_keys(open(versions_path).read())
    reserved = template_env_keys(open(template_path).read())
    errors, env, ansible_vars, summary = [], {}, {}, []

    if not isinstance(data, dict):
        errors.append("top level must be a mapping with images:, charts:, env:")
        data = {}
    for section in data:
        if section not in ("images", "charts", "env", "values"):
            errors.append(f"unknown section '{section}' (allowed: images, charts, env)")
    if data.get("values"):
        errors.append("values: is not supported yet: MAIA's values generators have no per-app override hook (plan step 2)")

    def put(key, value, where):
        if key in reserved:
            errors.append(f"{where}: {key} is set by the skill's config.yaml template; change it through its flag/var instead")
        elif key in env and env[key] != value:
            errors.append(f"{where}: {key} is set twice ({env[key]!r} and {value!r})")
        else:
            env[key] = value

    images = data.get("images") or {}
    if not isinstance(images, dict):
        errors.append("images: must be a mapping")
        images = {}
    for name, spec in images.items():
        where = f"images.{name}"
        try:
            if name == "registry":
                put("MAIA_REGISTRY", scalar(spec), where)
                summary.append(f"MAIA_REGISTRY={spec}")
                continue
            if isinstance(spec, dict):
                extra = set(spec) - {"tag"}
                if extra:
                    errors.append(f"{where}: unsupported key(s) {sorted(extra)}; only 'tag' (repository overrides need plan step 2)")
                    continue
                spec = spec.get("tag")
            tag = scalar(spec)
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
            continue
        key = f"{norm(name)}_IMAGE_VERSION"
        if key not in known:
            errors.append(f"{where}: {key} is not read by MAIA/versions.py (known images: "
                          + ", ".join(sorted(k[:-14].lower().replace('_', '-') for k in known if k.endswith('_IMAGE_VERSION'))) + ")")
        elif key == "MAIA_DASHBOARD_IMAGE_VERSION":
            ansible_vars["maia_dashboard_image_version"] = tag
            summary.append(f"maia_dashboard_image_version={tag}")
        else:
            put(key, tag, where)
            summary.append(f"{key}={tag}")

    charts = data.get("charts") or {}
    if not isinstance(charts, dict):
        errors.append("charts: must be a mapping")
        charts = {}
    for name, spec in charts.items():
        where = f"charts.{name}"
        if name in ("git_repo", "helm_repo", "repo"):
            errors.append(f"{where}: not supported yet. MAIA_PRIVATE_REGISTRY is one URL shared by git-sourced charts, Helm "
                          "charts (cert-manager, minio) and images, and MAIA_Install doesn't export it (plan step 2)")
            continue
        try:
            if name == "ref":
                ref = scalar(spec)
                ansible_vars["maia_chart_ref"] = ref
                put("MAIA_CHART_GIT_REF", ref, where)
                summary.append(f"chart git ref={ref}")
                continue
            if not isinstance(spec, dict):
                spec = {"version": scalar(spec)}
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
            continue
        base = norm(name)
        if base.endswith("_CHART_VERSION"):
            base = base[: -len("_CHART_VERSION")]
        extra = set(spec) - {"version", "type"}
        if extra:
            errors.append(f"{where}: unsupported key(s) {sorted(extra)}; use version and/or type")
        if "type" in spec and spec["type"] not in ("git_repo", "helm_repo"):
            errors.append(f"{where}.type: must be git_repo or helm_repo")
        for field in ("version", "type"):
            if field not in spec:
                continue
            key = f"{base}_CHART_{field.upper()}"
            if key not in known:
                errors.append(f"{where}: {key} is not read by MAIA/versions.py")
                continue
            put(key, str(spec[field]), where)
            summary.append(f"{key}={spec[field]}")
        if spec.get("type") == "helm_repo" and "version" in spec and not re.match(r"^\d+\.\d+", str(spec["version"])):
            errors.append(f"{where}: type helm_repo needs a chart version like 1.2.3, not {spec['version']!r}")

    raw = data.get("env") or {}
    if not isinstance(raw, dict):
        errors.append("env: must be a mapping")
        raw = {}
    for key, value in raw.items():
        where = f"env.{key}"
        if SECRET_RE.search(str(key)):
            errors.append(f"{where}: looks like a secret; secrets go in secrets.env, not in overrides")
            continue
        try:
            put(str(key), scalar(value), where)
            summary.append(f"{key}={value}" + ("" if str(key) in known else "  (not in versions.py: passed through)"))
        except ValueError as exc:
            errors.append(f"{where}: {exc}")

    if errors:
        print("OVERRIDES INVALID:")
        for e in errors:
            print("  -", e)
        return 1
    ansible_vars["maia_override_env"] = env
    with open(out_path, "w") as fh:
        fh.write("# generated by scripts/overrides.py from overrides.yaml; do not edit\n")
        yaml.safe_dump(ansible_vars, fh, default_flow_style=False, sort_keys=True)
    print("overrides:", "none" if not summary else "")
    for s in summary:
        print("  ", s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
