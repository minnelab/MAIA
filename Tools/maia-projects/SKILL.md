---
name: maia-projects
description: >-
  Create, deploy, update and inspect MAIA projects, and add/remove/create MAIA
  users, through the MAIA Dashboard API (the same API as
  MAIA_scripts/MAIA_deploy_project.py). Use when the user asks to add a project,
  onboard users to a project, change a project's resources/apps/configuration,
  or asks which project parameters exist. Prefer the maia-projects MCP tools;
  fall back to Tools/maia-projects/maia_projects.py.
---

# MAIA Projects and Users

A **MAIA project** is a Keycloak group (`MAIA:<namespace>`), a Kubernetes
namespace and a set of ArgoCD applications (JupyterHub or Kubeflow, FileBrowser
and, on the Pro tier, MinIO/MySQL/MLflow/Orthanc). It is defined by one JSON
request. Examples: `templates/project-base.json`, `templates/project-pro.json`,
and `templates/project-full.json` (every option). **Every parameter, with its
type, default and known issues, is in `PARAMETERS.md`** or the
`project_parameters_reference` tool. Look a key up before using it; don't guess.

## How to reach it

1. **MCP tools** (server `maia-projects`).
2. **CLI**: `python Tools/maia-projects/maia_projects.py ...`
3. The legacy script: `MAIA_scripts/MAIA_deploy_project.py --project-config-file F --dashboard-url URL`.

Configuration:
- `MAIA_DASHBOARD_URL` is required.
- Credentials are one of: `MAIA_DASHBOARD_TOKEN` (a Keycloak id_token), `MAIA_USERNAME`/`MAIA_PASSWORD` (plus `CLIENT_SECRET`), or a one-time `maia_projects.py login`. The caller must be a **dashboard superuser**.
- Deploying needs a Keycloak token. A DRF token is enough only for listing and for user management.

Start with `projects_auth_status`.

## Create or update a project

1. **Collect** the required fields. Ask for anything missing, and never invent emails, dates or clusters: `namespace`, `email` (requesting admin), `date`, `cluster`, `project_tier` (`Base` or `Pro`), `gpu`, `memory_limit`/`memory_request`, `cpu_limit`/`cpu_request`. Also ask for `supervisor` (defaults to `email`), `users` and `description`.
   - Check `list_projects` first. **Deploying an existing namespace updates it** (create-or-update).
2. **Map the wishes to parameters** with `project_parameters_reference`:
   - "Kubeflow instead of JupyterHub" → `env.DEPLOY_KUBEFLOW: "True"`
   - "EHRbase" → `env.DEPLOY_EHRBASE: "True"`
   - "NVFlare" → `env.DEPLOY_NVFLARE_DASHBOARD: "True"`, plus the top-level `nvflare_dashboard_admin_username`/`_password`
   - "GPUs in the workspaces" → `gpu_request`. `gpu` is only a label.
   - "custom workspace image":
     - Base tier: `env.maia_workspace_image`/`_version`
     - Pro tier: `env.maia_workspace_pro_image`/`_version`
   - "CIFS share" → `env.enable_cifs: "True"`
   - "restrict access to IPs" → `ip_whitelist`
   - "smaller MLflow/MySQL/Orthanc" → `env.<APP>_<CPU|MEMORY>_<REQUEST|LIMIT>`
   - JupyterHub admins and limits → `admins`, `active_server_limit`, `concurrent_spawn_limit`, `node_selector`, `jupyterhub_extraEnv`
3. **Build**: use `build_project_config`, or write the JSON from a template.
   - Write `project_configuration.env` values as **strings** (`"True"`, not `true`). Booleans are converted, but strings are unambiguous.
   - Leave credentials out unless the user provides them: they are generated, and kept on redeploy.
4. **Validate** with `validate_project_config`. Fix every `error`. Explain every `warning` to the user; warnings flag known MAIA bugs and keys that have no effect.
5. **Preview** with `deploy_project dry_run=true`. Show the user:
   - the namespace and tier;
   - the members (supervisor first);
   - the ArgoCD apps that will be created (`summary.argocd_apps`);
   - which apps are synced right away (`auto_deploy_apps`);
   - which secrets are in the config;
   - that missing users get Keycloak accounts and invitation e-mails.

   **Get explicit confirmation.**
6. **Deploy** with `deploy_project`.
   - `auto_deploy=false`: registers the project and users and renders values. Nothing is created in the cluster.
   - `auto_deploy=true`: also creates the namespace and RBAC (a Kubeflow profile when `DEPLOY_KUBEFLOW`) and the ArgoCD applications, and syncs `auto_deploy_apps`.
   - The response leaves out the rendered values, because they contain credentials. Save them with `values_output_path` only if the user asks.
7. **Verify** with the `maia-cluster` tools, if available:
   - `argocd_apps project=<namespace>` and `argocd_app_status`.
   - Apps that are not in `auto_deploy_apps` stay OutOfSync until synced: `argocd_diff`, then `argocd_sync` after confirmation.
   - `cluster_overview namespace=<namespace>`.

## Users

- **Add someone to a project:** `add_user_to_project email namespace`. If the user is new it also creates them, which needs `first_name` and `last_name`. It keeps their other projects.
- **New user:** `create_user`. Keycloak e-mails a temporary password. The default `users` group is always added.
- **Remove from one project:** `remove_user_from_project`. Confirm first. The account and other memberships stay.
- `set_user_projects` replaces the whole list. Avoid it unless asked.
- **Delete:** `delete_user` deletes the account. It is irreversible: confirm explicitly, and use `force` only if the user still has projects and the requester insists.
- **Bulk onboarding:** use the project's `users` list in `deploy_project`. That creates every missing user and adds them, in one call, with usernames from `email_to_username_map`.
- `projects_status` shows users waiting for Keycloak registration or group sync, and the ArgoCD state of each project.

## Gotchas (the validator enforces these, so don't fight it)

- Members are the supervisor (first, and the Kubeflow profile owner), then `users`, then the owner `email`. Missing accounts are created.
- The first member (the supervisor) owns the Kubeflow profile.
- `project_tier`: only `Base` is minimal. Any other value deploys the full Pro stack.
- **Disabled keys:** a key containing `:` (e.g. `"DEPLOY_KUBEFLOW:NO"`) is ignored. That's how the templates keep optional settings without applying them.
- **Keys with no per-project effect:** `MAIA_LAB_PRO_IMAGE_VERSION` (use `maia_workspace_pro_version`). `nvflare_dashboard_admin_*` must be top-level, not under `env`.
- A private registry secret per project needs `env.imagePullSecrets` plus `registry_server`/`registry_username`/`registry_password`. Missing ones fall back to the dashboard's global values.
- **Not settable** (recomputed): `extra_configs`, `ssh_users`, `minio_access_key`, `minio_secret_key`.
- `delete_project` removes the dashboard project and the Keycloak group. It does **not** delete the namespace, PVCs or ArgoCD apps.

## Safety

- Never print or echo secrets (passwords, MinIO/MySQL credentials). `deploy_project dry_run` already masks them.
- Never commit project files that contain credentials.
- Confirm with the user before: deploying (it creates accounts and sends e-mails), `auto_deploy=true`, removing or deleting users, and deleting projects.
- Use `MAIA_PROJECTS_READ_ONLY=true` to explore safely: it blocks all writes.
