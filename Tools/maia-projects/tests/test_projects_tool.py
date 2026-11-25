"""Tests for the maia-projects catalog/validator, auth, dashboard client and MCP surface."""

from __future__ import annotations

import base64
import copy
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import catalog  # noqa: E402
from lib.auth import TokenProvider, jwt_claims, save_tokens, token_cache_path  # noqa: E402
from lib.client import DashboardClient, DashboardError  # noqa: E402

TEMPLATES = ROOT / "templates"


def _jwt(claims: dict) -> str:
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64(claims)}.sig"


def _project(**over) -> dict:
    cfg = json.loads((TEMPLATES / "project-base.json").read_text())
    cfg.update(over)
    return cfg


# --------------------------------------------------------------------------- catalog / validation


@pytest.mark.parametrize("name", ["project-base.json", "project-pro.json", "project-full.json"])
def test_templates_are_valid(name):
    res = catalog.validate(json.loads((TEMPLATES / name).read_text()))
    assert res["valid"], res["errors"]


def test_full_template_covers_every_documented_key():
    full = json.loads((TEMPLATES / "project-full.json").read_text())
    pc = full["project_configuration"]
    pc_keys = {k.split(":")[0] for k in pc} - {"env"}
    env_keys = {k.split(":")[0] for k in pc["env"]}
    documented_pc = {p.name for p in catalog.PC_PARAMS} - {"env", "minio_console_access_key",
                                                           "minio_console_secret_key"}
    # Left out of the template on purpose: broken (imagePullSecrets), server paths, rarely used, or
    # the *_LIMIT twins of the *_REQUEST keys that are shown.
    omitted = {"imagePullSecrets", "registry_server", "registry_username", "registry_password", "JSON_KEY_PATH",
               "base_url", "JHUB_IMAGE"}
    documented_env = {p.name for p in catalog.ENV_PARAMS if not p.name.endswith("_LIMIT")} - omitted
    assert documented_pc <= pc_keys
    assert documented_env - env_keys == set()


def test_parameters_md_is_up_to_date():
    assert (ROOT / "PARAMETERS.md").read_text().strip() == catalog.to_markdown().strip(), \
        "Regenerate: python Tools/maia-projects/maia_projects.py reference --markdown > Tools/maia-projects/PARAMETERS.md"


def test_enabling_every_full_template_option_reports_known_issues():
    full = json.loads((TEMPLATES / "project-full.json").read_text())
    pc = full["project_configuration"]
    enabled = {k.split(":")[0]: v for k, v in pc.items() if k != "env"}
    enabled["env"] = {k.split(":")[0]: v for k, v in pc["env"].items()}
    full["project_configuration"] = enabled
    res = catalog.validate(full)
    assert res["valid"], res["errors"]  # nvflare credentials are present, hub_image has hub_tag
    assert "full-example-kubeflow" in res["summary"]["argocd_apps"]
    assert "full-example-ehrbase" in res["summary"]["argocd_apps"]
    assert "full-example-nvflare-dashboard" in res["summary"]["argocd_apps"]
    assert "project_configuration.password" in res["summary"]["secrets_in_config"]


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda c: c.update(namespace="My_Project"), "DNS label"),
        (lambda c: c.pop("cluster"), "Missing required field 'cluster'"),
        (lambda c: c.pop("namespace"), "Missing required field 'namespace'"),
        (lambda c: c.update(group_id="x"), "use 'namespace'"),
        (lambda c: c.update(date="31/12/2027"), "YYYY-MM-DD"),
        (lambda c: c.update(memory_limit="lots"), "memory quantity"),
        (lambda c: c.update(users=["not-an-email"]), "valid email"),
        (lambda c: c.update(auto_deploy_apps=["jupyter"]), "not one of"),
        (lambda c: c.update(project_configuration={"env": {"DEPLOY_KUBEFLOW": {"on": 1}}}), "must be a string"),
        (lambda c: c.update(project_configuration={"env": {"hub_image": "x"}}), "requires hub_tag"),
        (lambda c: c.update(project_configuration={"DEPLOY_KUBEFLOW": "True"}), "belongs under"),
        (lambda c: c.update(project_configuration={"env": {"ip_whitelist": "x"}}), "top-level"),
    ],
)
def test_validation_errors(mutate, needle):
    cfg = _project()
    mutate(cfg)
    res = catalog.validate(cfg)
    assert not res["valid"]
    assert any(needle in e for e in res["errors"]), res["errors"]


@pytest.mark.parametrize(
    "pc,needle",
    [
        ({"env": {"MAIA_LAB_PRO_IMAGE_VERSION": "1"}}, "no per-project effect"),
        ({"env": {"DEPLOY_KUBEFLOW": "true"}}, "does not enable"),
        ({"env": {"enable_cifs": "maybe"}}, "disables CIFS"),
        ({"env": {"DEPLOY_KUBEFLOW": True}}, "converted"),
        ({"env": {"SOMETHING_ELSE": "1"}}, "not read per project"),
        ({"extra_configs": {}}, "no effect"),
        ({"group_subdomain": "x"}, "overrides a derived value"),
    ],
)
def test_validation_warnings(pc, needle):
    res = catalog.validate(_project(project_configuration=pc))
    assert any(needle in w for w in res["warnings"]), res["warnings"]


def test_disabled_keys_and_stack_prediction():
    cfg = _project(project_tier="Pro", auto_deploy_apps=["namespace", "kubeflow"],
                   project_configuration={"env": {"DEPLOY_KUBEFLOW": "True", "DEPLOY_EHRBASE:NO": "True"}})
    cfg["auto_deploy_apps:OLD"] = []
    res = catalog.validate(cfg)
    assert res["valid"]
    assert set(res["disabled_keys"]) == {"auto_deploy_apps:OLD", "project_configuration.env.DEPLOY_EHRBASE:NO"}
    assert res["summary"]["argocd_apps"] == ["my-project-namespace", "my-project-kubeflow", "my-project-filebrowser",
                                             "my-project-mysql", "my-project-mlflow", "my-project-orthanc"]
    assert res["summary"]["members"][0] == "pi@example.org"


def test_optional_fields_and_member_order():
    cfg = _project()
    for key in ("supervisor", "description", "users"):
        cfg.pop(key)
    res = catalog.validate(cfg)
    assert res["valid"], res["errors"]
    assert res["summary"]["members"] == ["admin@example.org"]  # supervisor defaults to the owner
    res = catalog.validate(_project())
    assert res["summary"]["members"] == ["pi@example.org", "researcher@example.org", "admin@example.org"]


def test_fixed_bugs_are_no_longer_flagged():
    pc = {"minio_console_access_key": "x", "mysql_user": "y",
          "env": {"imagePullSecrets": "reg", "registry_server": "r", "registry_username": "u",
                  "registry_password": "p", "DEPLOY_NVFLARE_DASHBOARD": "True", "enable_cifs": "False"}}
    res = catalog.validate(_project(project_configuration=pc))
    assert res["valid"] and res["warnings"] == [], (res["errors"], res["warnings"])
    assert "my-project-nvflare-dashboard" in res["summary"]["argocd_apps"]


def test_redact_masks_secrets_only():
    cfg = _project(project_configuration={"password": "pw", "admins": ["a@b.se"],
                                          "env": {"EHRBASE_DB_PASSWORD": "x", "DEPLOY_EHRBASE": "True",
                                                  "CUSTOM_PASSWORD:OFF": "y"}})
    red = catalog.redact(cfg)
    pc = red["project_configuration"]
    assert pc["password"] == "***" and pc["admins"] == ["a@b.se"]
    assert pc["env"] == {"EHRBASE_DB_PASSWORD": "***", "DEPLOY_EHRBASE": "True", "CUSTOM_PASSWORD:OFF": "***"}
    assert cfg["project_configuration"]["password"] == "pw"  # original untouched


def test_build_project_shape():
    cfg = catalog.build_project("p1", "a@x.se", "pi@x.se", "c1", "2027-01-01", "d", users=["u@x.se"])
    assert cfg["email_to_username_map"] == {"pi@x.se": "pi@x.se", "u@x.se": "u@x.se"}
    assert catalog.validate(cfg)["valid"]


# --------------------------------------------------------------------------- fake dashboard + keycloak


class Fake(BaseHTTPRequestHandler):
    state: dict = {}

    def log_message(self, *a):
        pass

    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode() if n else ""

    def _record(self, body=None):
        Fake.state["calls"].append({"method": self.command, "path": self.path, "auth": self.headers.get("Authorization"),
                                    "body": body})

    def do_GET(self):  # noqa: N802
        self._record()
        p = urlparse(self.path).path
        if p == "/maia/api/well-known/":
            return self._send(200, {"issuer": Fake.state["issuer"], "client_id": "maia-public", "realm": "maia"})
        if p.endswith("list-users/"):
            return self._send(200, {"users": Fake.state["users"]})
        if p.endswith("list-groups/"):
            return self._send(200, {"groups": Fake.state["groups"]})
        self._send(404, {"error": "nope"})

    def do_POST(self):  # noqa: N802
        raw = self._body()
        p = urlparse(self.path).path
        if p.endswith("/protocol/openid-connect/token"):
            form = {k: v[0] for k, v in parse_qs(raw).items()}
            self._record(form)
            return self._send(200, {"id_token": _jwt({"email": "admin@x.se", "exp": time.time() + 300}),
                                    "refresh_token": "r2"})
        body = json.loads(raw or "{}")
        self._record(body)
        if p.endswith("project-chart/"):
            return self._send(200, {"values": {"namespace": body["namespace"], "secret": "s3cr3t"}})
        if p.endswith("create-user/") or p.endswith("create-group/"):
            return self._send(201, {"message": "ok"})
        self._send(404, {"error": "nope"})

    def do_PATCH(self):  # noqa: N802
        body = json.loads(self._body() or "{}")
        self._record(body)
        self._send(200, {"message": "updated"})

    def do_DELETE(self):  # noqa: N802
        self._record()
        self._send(200, {"message": "deleted"})


@pytest.fixture()
def dash(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    Fake.state = {
        "calls": [],
        "issuer": f"{url}/realms/maia",
        "users": [{"email": "old@x.se", "username": "old", "namespace": "users,proj-a"}],
        "groups": [{"namespace": "proj-a"}, {"namespace": "proj-b"}],
    }
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield url
    httpd.shutdown()


TOKEN = _jwt({"email": "admin@x.se", "exp": time.time() + 3600})


def _client(url, **env):
    return DashboardClient(url, env={"MAIA_DASHBOARD_TOKEN": TOKEN, **env})


def test_deploy_sends_bearer_and_strips_disabled_keys(dash):
    c = _client(dash)
    cfg = json.loads((TEMPLATES / "project-pro.json").read_text())
    res = c.deploy_project(cfg)
    call = Fake.state["calls"][-1]
    assert call["path"] == "/maia/user-management/project-chart/" and call["auth"] == f"Bearer {TOKEN}"
    assert "auto_deploy_apps:DISABLED" not in call["body"]
    assert res["values"]["namespace"] == "scapis-demo"


def test_deploy_refuses_invalid_config_without_calling(dash):
    c = _client(dash)
    with pytest.raises(DashboardError, match="invalid"):
        c.deploy_project(_project(namespace="Bad_NS"))
    assert Fake.state["calls"] == []


def test_drf_token_cannot_deploy_but_can_list(dash):
    c = DashboardClient(dash, env={"MAIA_DASHBOARD_DRF_TOKEN": "abc"})
    assert c.list_projects()[0]["namespace"] == "proj-a"
    assert Fake.state["calls"][-1]["auth"] == "Token abc"
    with pytest.raises(DashboardError, match="Keycloak token"):
        c.deploy_project(_project())


def test_create_user_always_adds_users_group_and_requires_names(dash):
    c = _client(dash)
    c.create_user("n@x.se", "Ada", "Lovelace", namespaces=["proj-a"])
    assert Fake.state["calls"][-1]["body"]["namespace"] == "proj-a,users"
    with pytest.raises(DashboardError, match="first_name"):
        c.create_user("n@x.se", "", "L")


def test_add_and_remove_user_keep_other_projects(dash):
    c = _client(dash)
    res = c.add_user_to_project("old@x.se", "proj-b")
    assert res["action"] == "added"
    assert Fake.state["calls"][-1]["body"] == {"email": "old@x.se", "namespace": "users,proj-a,proj-b"}
    assert c.add_user_to_project("old@x.se", "proj-a")["action"] == "unchanged"
    c.remove_user_from_project("old@x.se", "proj-a")
    assert Fake.state["calls"][-1]["body"] == {"email": "old@x.se", "namespace": "users"}


def test_add_new_user_needs_names_and_existing_project(dash):
    c = _client(dash)
    with pytest.raises(DashboardError, match="first_name"):
        c.add_user_to_project("new@x.se", "proj-a")
    with pytest.raises(DashboardError, match="does not exist"):
        c.add_user_to_project("new@x.se", "nope", "A", "B")
    assert c.add_user_to_project("new@x.se", "proj-a", "A", "B")["action"] == "created"


def test_read_only_blocks_writes(dash):
    c = _client(dash, MAIA_PROJECTS_READ_ONLY="true")
    assert c.list_users()
    with pytest.raises(DashboardError, match="Read-only"):
        c.delete_user("old@x.se")


def test_password_grant_discovers_keycloak(dash):
    tp = TokenProvider(dash, env={"MAIA_USERNAME": "admin", "MAIA_PASSWORD": "pw", "CLIENT_SECRET": "cs"})
    header = tp.header()
    assert header.startswith("Bearer ") and jwt_claims(header[7:])["email"] == "admin@x.se"
    form = Fake.state["calls"][-1]["body"]
    assert form["grant_type"] == "password" and form["client_id"] == "maia" and form["client_secret"] == "cs"
    tp.header()  # cached: no second token request
    assert sum(1 for c in Fake.state["calls"] if c["path"].endswith("/token")) == 1


def test_cached_login_refreshes_expired_token(dash):
    save_tokens(dash, "maia-public", {"id_token": _jwt({"exp": time.time() - 10}), "refresh_token": "r1"})
    tp = TokenProvider(dash, env={})
    assert tp.source().startswith("login-cache")
    tp.header()
    form = Fake.state["calls"][-1]["body"]
    assert form == {"grant_type": "refresh_token", "client_id": "maia-public", "refresh_token": "r1"}
    saved = json.loads(token_cache_path().read_text())
    assert saved["refresh_token"] == "r2" and jwt_claims(saved["id_token"])["exp"] > time.time()


def test_no_credentials_message(dash):
    with pytest.raises(DashboardError, match="login"):
        DashboardClient(dash, env={}).list_users()


# --------------------------------------------------------------------------- MCP surface


def _mcp():
    pytest.importorskip("mcp")
    import importlib.util

    spec = importlib.util.spec_from_file_location("maia_projects_mcp", ROOT / "mcp_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mcp_tools_and_annotations():
    import asyncio

    mod = _mcp()
    tools = {t.name: t for t in asyncio.run(mod.list_tools())}
    assert {"project_parameters_reference", "validate_project_config", "deploy_project", "add_user_to_project",
            "delete_project"} <= set(tools)
    assert tools["list_users"].annotations.readOnlyHint is True
    assert tools["delete_user"].annotations.destructiveHint is True


def test_mcp_dry_run_masks_secrets_and_makes_no_call(dash, monkeypatch):
    mod = _mcp()
    monkeypatch.setattr(mod, "_client", _client(dash))
    cfg = _project(project_configuration={"password": "pw"})
    out = mod._dispatch("deploy_project", {"config": copy.deepcopy(cfg), "dry_run": True})
    assert out["dry_run"] and out["valid"] and out["config"]["project_configuration"]["password"] == "***"
    assert Fake.state["calls"] == []


def test_mcp_deploy_hides_values_unless_saved(dash, monkeypatch, tmp_path):
    mod = _mcp()
    monkeypatch.setattr(mod, "_client", _client(dash))
    out = mod._dispatch("deploy_project", {"config": _project()})
    assert "s3cr3t" not in json.dumps(out) and out["values_keys"] == ["namespace", "secret"]
    target = tmp_path / "v.yaml"
    out = mod._dispatch("deploy_project", {"config": _project(), "values_output_path": str(target)})
    assert out["values_saved_to"] == str(target) and "s3cr3t" in target.read_text()
    assert oct(target.stat().st_mode & 0o777) == "0o600"
