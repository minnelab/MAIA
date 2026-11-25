# MAIA Projects Tool Suite

An MCP server, a CLI and an agent skill for **creating and deploying MAIA
projects and managing their users** through the MAIA Dashboard REST API
(`/maia/user-management/`). This is the API `MAIA_scripts/MAIA_deploy_project.py` uses.

- [`SKILL.md`](SKILL.md): agent workflow and rules.
- [`PARAMETERS.md`](PARAMETERS.md): every project parameter (generated from `lib/catalog.py`).
- [`templates/`](templates/): `project-base.json`, `project-pro.json` (the scapis-demo shape), and `project-full.json` (every option, disabled with the `:` key convention).

## Configure

| Variable | Purpose |
|----------|---------|
| `MAIA_DASHBOARD_URL` | Dashboard URL, e.g. `https://maia.example.org` (dev: `http://localhost:8000`) |
| `MAIA_DASHBOARD_TOKEN` | Keycloak **id_token** of a dashboard superuser. Needed to deploy. |
| `MAIA_USERNAME` / `MAIA_PASSWORD` / `CLIENT_SECRET` | Password grant, same as `MAIA_deploy_project.py` (`MAIA_OIDC_CLIENT_ID`, default `maia`) |
| `MAIA_DASHBOARD_DRF_TOKEN` | Django REST token: listing and user management only |
| `MAIA_DASHBOARD_CA_BUNDLE` / `MAIA_DASHBOARD_INSECURE` | TLS for self-signed clusters |
| `MAIA_USERS_GROUP` | Default users group (dashboard `USERS_GROUP`, default `users`) |
| `MAIA_PROJECTS_READ_ONLY` | `true` blocks every write |

With none of the credentials above, run `python Tools/maia-projects/maia_projects.py login` once. It does a browser PKCE login like the deploy script, and stores the tokens in `~/.config/maia-projects/token.json` (0600). They are refreshed automatically.

Why a Keycloak token for deploys: `project-chart/` builds the deployment kubeconfig from the caller's `id_token`.

## MCP server

```bash
pip install -r Tools/maia-projects/requirements.txt
claude mcp add maia-projects -e MAIA_DASHBOARD_URL=https://maia.example.org -- python /abs/path/Tools/maia-projects/mcp_server.py
```

| Tool | Kind | Purpose |
|------|------|---------|
| `projects_auth_status` | read | Dashboard, credential source, identity, can-deploy |
| `project_parameters_reference` | local | Every parameter, with types, defaults, secrets and known issues |
| `build_project_config` / `validate_project_config` | local | Build and validate a request; predicts the ArgoCD apps |
| `list_projects`, `list_pending_projects`, `projects_status`, `list_users` | read | Inspect |
| `deploy_project` | write | `project-chart/`: register, create users, render; with `auto_deploy`, also deploy. Has `dry_run` |
| `register_project` | write | `create-group/`: register only |
| `create_user`, `add_user_to_project` | write | Users |
| `remove_user_from_project`, `set_user_projects`, `delete_user`, `delete_project` | destructive | Confirm first |

## CLI

```bash
export MAIA_DASHBOARD_URL=https://maia.example.org
python Tools/maia-projects/maia_projects.py login
python Tools/maia-projects/maia_projects.py validate my-project.json
python Tools/maia-projects/maia_projects.py deploy my-project.json --dry-run
python Tools/maia-projects/maia_projects.py deploy my-project.json            # writes <namespace>-values.yaml (0600)
python Tools/maia-projects/maia_projects.py user-add new@example.org my-project --first Ada --last Lovelace
python Tools/maia-projects/maia_projects.py status --out MAIA-Projects.yaml   # = MAIA_deploy_project.py --get-status
python Tools/maia-projects/maia_projects.py reference --markdown > Tools/maia-projects/PARAMETERS.md
```

## Endpoints used

| Operation | Endpoint |
|-----------|----------|
| Discover Keycloak | `GET /maia/api/well-known/` |
| Deploy / update project | `POST /maia/user-management/project-chart/` |
| Register project | `POST /maia/user-management/create-group/` |
| Delete project | `DELETE /maia/user-management/delete-group/<ns>` |
| Projects | `GET list-groups/`, `list-pending-groups/`, `get-projects/` |
| Users | `GET list-users/`, `POST create-user/`, `PATCH update-user/`, `DELETE delete-user/?email=&force=` |

## Tests

```bash
python -m pytest Tools/maia-projects/tests -q
```

The tests also check that `PARAMETERS.md` matches the catalog. After changing `lib/catalog.py`, regenerate it with the command above.
