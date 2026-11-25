#!/usr/bin/env python3
"""
MAIA Projects MCP Server — stdio transport.

Create, deploy and manage MAIA projects and their users through the MAIA Dashboard
REST API (``/maia/user-management/``), the same API used by
``MAIA_scripts/MAIA_deploy_project.py``. Includes a reference of every project
parameter and a validator, so agents can build correct project requests.

Usage
-----
    MAIA_DASHBOARD_URL=https://maia.example.org python Tools/maia-projects/mcp_server.py

Credentials (see lib/auth.py): MAIA_DASHBOARD_TOKEN (Keycloak id_token),
MAIA_USERNAME/MAIA_PASSWORD (+CLIENT_SECRET), or a cached
``python Tools/maia-projects/maia_projects.py login``.

    {
      "mcpServers": {
        "maia-projects": {
          "command": "python",
          "args": ["/path/to/MAIA/Tools/maia-projects/mcp_server.py"],
          "env": {"MAIA_DASHBOARD_URL": "https://maia.example.org"}
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
    print("ERROR: 'mcp' package not found. Install with: pip install -r Tools/maia-projects/requirements.txt",
          file=sys.stderr)
    sys.exit(1)

from lib import catalog  # noqa: E402
from lib.auth import AuthError  # noqa: E402
from lib.client import DashboardClient, DashboardError  # noqa: E402

app = Server("maia-projects")
_client: DashboardClient | None = None


def client() -> DashboardClient:
    global _client
    if _client is None:
        _client = DashboardClient()
    return _client


def _json(data) -> list:
    return [mcp_types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def _s(desc, **kw):
    return {"type": "string", "description": desc, **kw}


def _b(desc):
    return {"type": "boolean", "description": desc}


def _load_config(a: dict) -> dict:
    if a.get("config") is not None:
        cfg = a["config"]
        return json.loads(cfg) if isinstance(cfg, str) else cfg
    if a.get("config_file"):
        return json.loads(Path(a["config_file"]).expanduser().read_text())
    raise ValueError("Provide 'config' (object) or 'config_file' (path to a project JSON).")


def _deploy(a: dict) -> dict:
    cfg = _load_config(a)
    if a.get("auto_deploy") is not None:
        cfg["auto_deploy"] = bool(a["auto_deploy"])
    check = catalog.validate(cfg, "deploy")
    if a.get("dry_run"):
        return {"dry_run": True, "would_call": "POST /maia/user-management/project-chart/",
                "config": catalog.redact(cfg), **check}
    res = client().deploy_project(cfg)
    values = res.get("values")
    out = {"ok": True, "namespace": cfg["namespace"], "auto_deploy": bool(cfg.get("auto_deploy")),
           "summary": check["summary"], "warnings": check["warnings"]}
    if isinstance(values, (dict, list)) or (isinstance(values, str) and values):
        if a.get("values_output_path"):
            import yaml  # noqa: PLC0415  (mcp depends on pydantic/yaml-capable env)

            p = Path(a["values_output_path"]).expanduser()
            p.write_text(yaml.safe_dump(values) if not isinstance(values, str) else values)
            p.chmod(0o600)
            out["values_saved_to"] = str(p)
        out["values_keys"] = sorted(values) if isinstance(values, dict) else type(values).__name__
        out["note"] = ("Rendered values contain generated credentials; they were not returned. Pass "
                       "values_output_path to save them (0600).")
    if cfg.get("auto_deploy"):
        out["next_steps"] = [f"Check ArgoCD: argocd_apps project={cfg['namespace']} (maia-cluster tools)",
                             f"Pods: cluster_overview namespace={cfg['namespace']}"]
    return out


READ = mcp_types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
LOCAL = mcp_types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
DESTRUCTIVE = mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False,
                                        openWorldHint=True)

CONFIG_PROPS = {
    "config": {"type": "object", "description": "Project request (same JSON as the project config files)."},
    "config_file": _s("Path to a project JSON file (alternative to config)."),
}

BUILD_PROPS = {
    "namespace": _s("Project ID / Kubernetes namespace (DNS label)."),
    "email": _s("Requesting admin / owner email."),
    "supervisor": _s("Supervisor / PI email (first member)."),
    "users": {"type": "array", "items": {"type": "string"}, "description": "Member emails."},
    "cluster": _s("Target cluster name (cluster_name of a dashboard cluster config)."),
    "date": _s("End date YYYY-MM-DD."),
    "description": _s("Project description."),
    "project_tier": _s("Base (minimal) or Pro (MinIO, MySQL, MLflow, Orthanc).", enum=["Base", "Pro"]),
    "gpu": _s("GPU type label ('NO' or a GPU name from the cluster's gpu_specs)."),
    "memory_limit": _s("Per-user memory limit, e.g. '4 Gi'."),
    "memory_request": _s("Per-user memory request, e.g. '2 Gi'."),
    "cpu_limit": _s("Per-user CPU limit, e.g. '2'."),
    "cpu_request": _s("Per-user CPU request, e.g. '100m'."),
    "auto_deploy": _b("Create namespace + ArgoCD apps on deploy (default false)."),
    "auto_deploy_apps": {"type": "array", "items": {"type": "string", "enum": list(catalog.AUTO_DEPLOY_APPS)},
                         "description": "ArgoCD apps to sync immediately."},
    "email_to_username_map": {"type": "object", "description": "email -> Keycloak username for new users."},
    "project_configuration": {"type": "object",
                              "description": "Overrides; see project_parameters_reference."},
}

# name -> (description, properties, required, annotations, handler)
TOOLS: dict[str, tuple] = {
    "projects_auth_status": (
        "Show which dashboard and credentials are used, the caller identity from the token, and whether the "
        "credentials can deploy projects (a Keycloak token is needed). Call this first.",
        {}, [], READ, lambda a: client().whoami(),
    ),
    "project_parameters_reference": (
        "Reference of every configurable MAIA project parameter: request fields, project_configuration keys, "
        "project_configuration.env keys (exported as <KEY>_<namespace>), allowed values, defaults, which are secrets, "
        "and known issues. Consult it before building a project config.",
        {"section": _s("Limit to one section", enum=["project", "project_configuration", "env"]),
         "include_secrets": _b("Include secret parameters (default true)")}, [], LOCAL,
        lambda a: catalog.reference(a.get("section"), a.get("include_secrets", True) is not False),
    ),
    "build_project_config": (
        "Assemble a project request (scapis-demo template shape) from parameters and validate it. Does not call "
        "the dashboard. Save the result to a JSON file if the user wants to keep it.",
        BUILD_PROPS, ["namespace", "email", "supervisor", "cluster", "date", "description"], LOCAL,
        lambda a: (lambda cfg: {"config": cfg, **catalog.validate(cfg, "deploy")})(catalog.build_project(**a)),
    ),
    "validate_project_config": (
        "Validate a project request against the dashboard's rules and the MAIA code: required fields, formats, "
        "project_configuration/env keys (unknown, misplaced, no per-project effect, known bugs), and predict the "
        "ArgoCD applications. No side effects.",
        {**CONFIG_PROPS, "mode": _s("deploy (project-chart, default) or register (create-group)",
                                    enum=["deploy", "register"])}, [], LOCAL,
        lambda a: catalog.validate(_load_config(a), a.get("mode") or "deploy"),
    ),
    "list_projects": (
        "List MAIA projects registered in the dashboard with resources, tier, cluster and Keycloak members.",
        {"namespace": _s("Only this project")}, [], READ,
        lambda a: client().list_projects(a.get("namespace")),
    ),
    "list_pending_projects": (
        "List project requests waiting for admin approval.", {}, [], READ,
        lambda a: client().list_pending_projects(),
    ),
    "projects_status": (
        "Users waiting to be registered in Keycloak / groups, users to remove, and the ArgoCD status of every "
        "project. Slow (queries Keycloak and ArgoCD).", {}, [], READ,
        lambda a: client().projects_status(),
    ),
    "list_users": (
        "List dashboard users with their projects and Keycloak registration status.",
        {"email": _s("Only this user"), "namespace": _s("Only members of this project")}, [], READ,
        lambda a: client().list_users(a.get("email"), a.get("namespace")),
    ),
    "deploy_project": (
        "Create or update a project through POST /maia/user-management/project-chart/ (what MAIA_deploy_project.py "
        "does): registers the project and creates missing users in the dashboard and Keycloak (invitation e-mails "
        "are sent), renders the project values and, with auto_deploy=true, creates the namespace/RBAC and ArgoCD "
        "applications and syncs auto_deploy_apps. Re-running updates the project. ALWAYS run with dry_run=true "
        "first, show the summary, and get the user's confirmation. Needs a Keycloak token.",
        {**CONFIG_PROPS, "dry_run": _b("Validate and show what would happen, without calling the dashboard"),
         "auto_deploy": _b("Override the config's auto_deploy"),
         "values_output_path": _s("Save the rendered values (contain credentials) to this file")}, [], WRITE,
        _deploy,
    ),
    "register_project": (
        "Register a project and its users only (POST create-group/): no values rendered, nothing deployed. Use when "
        "the project should be deployed later from the dashboard.",
        CONFIG_PROPS, [], WRITE,
        lambda a: client().register_project(_load_config(a)),
    ),
    "create_user": (
        "Create a MAIA user in the dashboard and Keycloak (Keycloak e-mails a temporary password) and add them to "
        "projects. The default users group is always added.",
        {"email": _s("Email"), "first_name": _s("First name"), "last_name": _s("Last name"),
         "username": _s("Keycloak username (default: email)"),
         "projects": {"type": "array", "items": {"type": "string"}, "description": "Project namespaces"}},
        ["email", "first_name", "last_name"], WRITE,
        lambda a: client().create_user(a["email"], a["first_name"], a["last_name"], a.get("username"),
                                       a.get("projects")),
    ),
    "add_user_to_project": (
        "Add a user to an existing project (keeps their other projects). Creates the user if missing, which needs "
        "first_name and last_name.",
        {"email": _s("Email"), "namespace": _s("Project namespace"), "first_name": _s("Needed if the user is new"),
         "last_name": _s("Needed if the user is new"), "username": _s("Keycloak username for a new user")},
        ["email", "namespace"], WRITE,
        lambda a: client().add_user_to_project(a["email"], a["namespace"], a.get("first_name"), a.get("last_name"),
                                               a.get("username")),
    ),
    "remove_user_from_project": (
        "Remove a user from one project (keeps the account and their other projects). Confirm with the user first.",
        {"email": _s("Email"), "namespace": _s("Project namespace")}, ["email", "namespace"], DESTRUCTIVE,
        lambda a: client().remove_user_from_project(a["email"], a["namespace"]),
    ),
    "set_user_projects": (
        "Replace a user's complete project/group list (dashboard update-user). Prefer add/remove_user_*_project.",
        {"email": _s("Email"), "projects": {"type": "array", "items": {"type": "string"},
                                            "description": "Full list of groups, include the users group"}},
        ["email", "projects"], DESTRUCTIVE,
        lambda a: client().set_user_projects(a["email"], a["projects"]),
    ),
    "delete_user": (
        "Delete a user from the dashboard and Keycloak. Irreversible: confirm explicitly with the user first.",
        {"email": _s("Email"), "force": _b("Delete even if the user still belongs to projects")}, ["email"],
        DESTRUCTIVE,
        lambda a: client().delete_user(a["email"], bool(a.get("force"))),
    ),
    "delete_project": (
        "Delete a project from the dashboard and its Keycloak group, and update its members. Does not delete the "
        "Kubernetes namespace or ArgoCD apps. Irreversible: confirm explicitly with the user first.",
        {"namespace": _s("Project namespace")}, ["namespace"], DESTRUCTIVE,
        lambda a: client().delete_project(a["namespace"]),
    ),
}


@app.list_tools()
async def list_tools():
    return [
        mcp_types.Tool(name=name, description=desc,
                       inputSchema={"type": "object", "properties": props, "required": required}, annotations=ann)
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
    except DashboardError as exc:
        return _json({"error": str(exc), "tool": name, "http_status": exc.status,
                      **({"validation": exc.payload} if isinstance(exc.payload, dict) and "errors" in exc.payload
                         else {})})
    except (AuthError, ValueError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        return _json({"error": f"{type(exc).__name__}: {exc}", "tool": name})
    except Exception as exc:  # noqa: BLE001
        return _json({"error": f"{type(exc).__name__}: {exc}", "tool": name})


async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
