#!/usr/bin/env python3
"""
MAIA projects & users CLI (Python 3.9+, PyYAML only for writing values files).

Superset of MAIA_scripts/MAIA_deploy_project.py for agents and humans.
Environment: MAIA_DASHBOARD_URL plus credentials (see lib/auth.py).

    maia_projects.py login                              # browser login (PKCE), cached + refreshed
    maia_projects.py whoami
    maia_projects.py reference [--section env] [--markdown]
    maia_projects.py validate project.json
    maia_projects.py deploy project.json --dry-run
    maia_projects.py deploy project.json [--auto-deploy | --no-auto-deploy] [--values-out FILE]
    maia_projects.py register project.json
    maia_projects.py projects [--namespace NS] | pending | status [--out MAIA-Projects.yaml]
    maia_projects.py users [--email E] [--namespace NS]
    maia_projects.py user-create EMAIL FIRST LAST [--username U] [--project NS ...]
    maia_projects.py user-add EMAIL NS [--first F --last L]
    maia_projects.py user-remove EMAIL NS
    maia_projects.py user-delete EMAIL [--force]
    maia_projects.py project-delete NS

Exit codes: 0 ok, 1 validation failed, 2 API/auth error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import catalog  # noqa: E402
from lib.auth import AuthError, browser_login  # noqa: E402
from lib.client import DashboardClient, DashboardError  # noqa: E402


def _print(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _load(path: str) -> dict:
    return json.loads(Path(path).expanduser().read_text())


def _write_values(values, path: Path) -> None:
    import yaml

    path.write_text(values if isinstance(values, str) else yaml.safe_dump(values))
    path.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="maia_projects.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dashboard-url", help="Overrides MAIA_DASHBOARD_URL")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login")
    s.add_argument("--port", type=int, default=8080)
    sub.add_parser("whoami")
    s = sub.add_parser("reference")
    s.add_argument("--section", choices=["project", "project_configuration", "env"])
    s.add_argument("--markdown", action="store_true")
    s = sub.add_parser("validate")
    s.add_argument("file")
    s.add_argument("--mode", choices=["deploy", "register"], default="deploy")
    s = sub.add_parser("deploy")
    s.add_argument("file")
    s.add_argument("--dry-run", action="store_true")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--auto-deploy", dest="auto_deploy", action="store_true", default=None)
    g.add_argument("--no-auto-deploy", dest="auto_deploy", action="store_false")
    s.add_argument("--values-out", help="Where to save the rendered values (default: <namespace>-values.yaml)")
    s = sub.add_parser("register")
    s.add_argument("file")
    s = sub.add_parser("projects")
    s.add_argument("--namespace")
    sub.add_parser("pending")
    s = sub.add_parser("status")
    s.add_argument("--out", help="Write the status as YAML (like MAIA_deploy_project.py --get-status)")
    s = sub.add_parser("users")
    s.add_argument("--email")
    s.add_argument("--namespace")
    s = sub.add_parser("user-create")
    s.add_argument("email")
    s.add_argument("first_name")
    s.add_argument("last_name")
    s.add_argument("--username")
    s.add_argument("--project", action="append", default=[])
    s = sub.add_parser("user-add")
    s.add_argument("email")
    s.add_argument("namespace")
    s.add_argument("--first")
    s.add_argument("--last")
    s.add_argument("--username")
    s = sub.add_parser("user-remove")
    s.add_argument("email")
    s.add_argument("namespace")
    s = sub.add_parser("user-delete")
    s.add_argument("email")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("project-delete")
    s.add_argument("namespace")
    a = p.parse_args(argv)

    try:
        # Commands that need no dashboard.
        if a.cmd == "reference":
            if a.markdown:
                print(catalog.to_markdown())
            else:
                _print(catalog.reference(a.section))
            return 0
        if a.cmd == "validate":
            res = catalog.validate(_load(a.file), a.mode)
            _print(res)
            return 0 if res["valid"] else 1
        if a.cmd == "deploy" and a.dry_run:
            cfg = _load(a.file)
            if a.auto_deploy is not None:
                cfg["auto_deploy"] = a.auto_deploy
            res = catalog.validate(cfg, "deploy")
            _print({"dry_run": True, "config": catalog.redact(cfg), **res})
            return 0 if res["valid"] else 1

        url = a.dashboard_url or os.environ.get("MAIA_DASHBOARD_URL")
        if a.cmd == "login":
            if not url:
                raise DashboardError("Set MAIA_DASHBOARD_URL or pass --dashboard-url.")
            _print(browser_login(url, a.port))
            return 0

        c = DashboardClient(url)
        if a.cmd == "whoami":
            _print(c.whoami())
        elif a.cmd == "deploy":
            cfg = _load(a.file)
            if a.auto_deploy is not None:
                cfg["auto_deploy"] = a.auto_deploy
            res = c.deploy_project(cfg)
            values = res.get("values")
            out = {"ok": True, "namespace": cfg["namespace"], "auto_deploy": bool(cfg.get("auto_deploy"))}
            if values:
                path = Path(a.values_out or f"{cfg['namespace']}-values.yaml")
                _write_values(values, path)
                out["values_saved_to"] = str(path)
            _print(out)
        elif a.cmd == "register":
            _print(c.register_project(_load(a.file)))
        elif a.cmd == "projects":
            _print(c.list_projects(a.namespace))
        elif a.cmd == "pending":
            _print(c.list_pending_projects())
        elif a.cmd == "status":
            data = c.projects_status()
            if a.out:
                _write_values(data, Path(a.out))
                print(f"Saved to {a.out}")
            else:
                _print(data)
        elif a.cmd == "users":
            _print(c.list_users(a.email, a.namespace))
        elif a.cmd == "user-create":
            _print(c.create_user(a.email, a.first_name, a.last_name, a.username, a.project))
        elif a.cmd == "user-add":
            _print(c.add_user_to_project(a.email, a.namespace, a.first, a.last, a.username))
        elif a.cmd == "user-remove":
            _print(c.remove_user_from_project(a.email, a.namespace))
        elif a.cmd == "user-delete":
            _print(c.delete_user(a.email, a.force))
        elif a.cmd == "project-delete":
            _print(c.delete_project(a.namespace))
        return 0
    except DashboardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1 if isinstance(exc.payload, dict) and "errors" in exc.payload else 2
    except (AuthError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
