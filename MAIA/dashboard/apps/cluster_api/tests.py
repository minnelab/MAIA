"""
Tests for the Cluster API (kubectl / helm execution).

Runs standalone with a minimal Django configuration so it doesn't need the
full dashboard settings (MinIO, Keycloak, MySQL, ...)::

    cd MAIA/dashboard && python -m pytest apps/cluster_api/tests.py -p no:django
"""

import os
import stat
import sys

import pytest

_DASHBOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="test",
        ROOT_URLCONF="apps.cluster_api.urls",
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "rest_framework"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.BasicAuthentication"]},
        ALLOWED_HOSTS=["*"],
    )
    django.setup()

from apps.cluster_api import executor
from apps.cluster_api.executor import CommandRejected, parse_request, redact_command
from apps.cluster_api.views import ClusterAPIExecView, ClusterAPIStatusView
from rest_framework.test import APIRequestFactory

TOKEN = "s3cr3t-cluster-token"


@pytest.fixture
def fake_bins(tmp_path):
    """Fake kubectl/helm that echo argv, stdin and KUBECONFIG; exit 3 on 'fail'."""
    paths = {}
    for tool in ("kubectl", "helm"):
        p = tmp_path / tool
        p.write_text(
            "#!/bin/sh\n"
            f'echo "{tool} $*"\n'
            'if [ "$1" = "fail" ]; then echo boom >&2; exit 3; fi\n'
            'if [ "$1" = "sleep" ]; then sleep 5; fi\n'
            'if [ "$1" = "stdin" ]; then cat; fi\n'
            'if [ "$1" = "env" ]; then echo "KUBECONFIG=${KUBECONFIG:-unset}"; fi\n'
        )
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        paths[tool] = str(p)
    return paths


@pytest.fixture
def cfg(fake_bins, settings_override):
    settings_override(
        CLUSTER_API_ENABLED=True,
        CLUSTER_API_TOKEN=TOKEN,
        CLUSTER_API_KUBECTL_PATH=fake_bins["kubectl"],
        CLUSTER_API_HELM_PATH=fake_bins["helm"],
        CLUSTER_API_KUBECONFIG="",
        CLUSTER_API_RATE="10000/hour",
    )


@pytest.fixture
def settings_override():
    from django.core.cache import cache

    saved = {}

    def apply(**kwargs):
        for k, v in kwargs.items():
            saved.setdefault(k, getattr(settings, k, None))
            setattr(settings, k, v)

    yield apply
    for k, v in saved.items():
        setattr(settings, k, v)
    cache.clear()


def _exec(body, headers=None):
    factory = APIRequestFactory()
    req = factory.post("/exec/", body, format="json", **(headers or {}))
    return ClusterAPIExecView.as_view()(req)


AUTH = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


# --------------------------------------------------------------------------- parsing


def test_parse_args_form():
    assert parse_request({"tool": "kubectl", "args": ["get", "pods"]}) == ("kubectl", ["get", "pods"])


def test_parse_command_form_with_quotes():
    tool, args = parse_request({"command": "kubectl get pods -l 'app=a b'"})
    assert tool == "kubectl" and args == ["get", "pods", "-l", "app=a b"]


def test_parse_command_with_tool_prefix_stripped():
    assert parse_request({"tool": "helm", "command": "helm list -A"}) == ("helm", ["list", "-A"])
    assert parse_request({"tool": "helm", "command": "list -A"}) == ("helm", ["list", "-A"])


@pytest.mark.parametrize(
    "payload",
    [
        {"command": "rm -rf /"},
        {"command": "bash -c 'kubectl get pods'"},
        {"tool": "sh", "args": ["-c", "id"]},
        {"tool": "kubectl"},
        {"tool": "kubectl", "args": "get pods"},
        {"tool": "kubectl", "args": ["get"], "command": "get"},
        {"command": "kubectl get 'unterminated"},
        {"command": "kubectl edit deploy x"},
        {"command": "kubectl port-forward svc/x 80"},
        {"command": "kubectl exec -it pod -- sh"},
        {"command": "kubectl get pods -w"},
        {"command": "kubectl logs pod -f"},
    ],
)
def test_parse_rejects(payload):
    with pytest.raises(CommandRejected):
        parse_request(payload)


def test_allowed_short_flags_for_other_subcommands():
    # -f is --filename for apply, -i is fine for non-interactive subcommands
    assert parse_request({"command": "kubectl apply -f -"})[1] == ["apply", "-f", "-"]
    assert parse_request({"command": "kubectl exec pod -- ls"})[1] == ["exec", "pod", "--", "ls"]


def test_tool_allowlist():
    with pytest.raises(CommandRejected):
        parse_request({"command": "helm list"}, allowed_tools=("kubectl",))


def test_redaction():
    out = redact_command("kubectl", ["create", "secret", "generic", "s", "--from-literal=pw=hunter2"])
    assert "hunter2" not in out
    out = redact_command("helm", ["install", "x", "y", "--set", "password=hunter2"])
    assert "hunter2" not in out


def test_shell_metacharacters_are_not_interpreted(fake_bins, tmp_path):
    marker = tmp_path / "pwned"
    tool, args = parse_request({"command": f"kubectl get pods; touch {marker}"})
    res = executor.run_command(tool, args, binaries=fake_bins)
    assert not marker.exists()
    assert f"touch {marker}" in res.stdout  # passed literally as arguments


def test_build_env_drops_inherited_kubeconfig(monkeypatch):
    monkeypatch.setenv("KUBECONFIG", "/tmp/kubeconfig-project")
    assert "KUBECONFIG" not in executor.build_env(None)
    assert executor.build_env("/etc/admin.yaml")["KUBECONFIG"] == "/etc/admin.yaml"


# --------------------------------------------------------------------------- views


def test_disabled_by_default(settings_override):
    settings_override(CLUSTER_API_ENABLED=False, CLUSTER_API_TOKEN=TOKEN)
    assert _exec({"command": "kubectl get pods"}, AUTH).status_code == 404


def test_requires_auth(cfg):
    assert _exec({"command": "kubectl get pods"}).status_code == 401
    bad = {"HTTP_AUTHORIZATION": "Bearer wrong"}
    assert _exec({"command": "kubectl get pods"}, bad).status_code == 401


def test_exec_with_bearer_token(cfg):
    r = _exec({"command": "kubectl get pods -A"}, AUTH)
    assert r.status_code == 200
    assert r.data["ok"] is True and r.data["exit_code"] == 0
    assert r.data["stdout"].strip() == "kubectl get pods -A"


def test_exec_with_header_token(cfg):
    r = _exec({"tool": "helm", "args": ["list", "-A"]}, {"HTTP_X_CLUSTER_API_TOKEN": TOKEN})
    assert r.status_code == 200 and r.data["stdout"].strip() == "helm list -A"


def test_nonzero_exit_reported(cfg):
    r = _exec({"command": "kubectl fail"}, AUTH)
    assert r.status_code == 200
    assert r.data["ok"] is False and r.data["exit_code"] == 3 and "boom" in r.data["stderr"]


def test_stdin_passed(cfg):
    r = _exec({"command": "kubectl stdin", "stdin": "apiVersion: v1\n"}, AUTH)
    assert "apiVersion: v1" in r.data["stdout"]


def test_timeout(cfg):
    r = _exec({"command": "kubectl sleep", "timeout": 0.5}, AUTH)
    assert r.status_code == 504 and r.data["timed_out"] is True


def test_invalid_command_400(cfg):
    assert _exec({"command": "cat /etc/passwd"}, AUTH).status_code == 400


def test_kubeconfig_not_inherited(cfg, monkeypatch):
    monkeypatch.setenv("KUBECONFIG", "/tmp/kubeconfig-project")
    r = _exec({"command": "kubectl env"}, AUTH)
    assert "KUBECONFIG=unset" in r.data["stdout"]


def test_superuser_basic_auth(cfg, django_db_setup_minimal):
    from django.contrib.auth.models import User

    User.objects.create_superuser("admin", "admin@example.com", "pw")
    User.objects.create_user("bob", "bob@example.com", "pw")
    import base64

    def basic(u):
        return {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(f"{u}:pw".encode()).decode()}

    assert _exec({"command": "kubectl get ns"}, basic("admin")).status_code == 200
    assert _exec({"command": "kubectl get ns"}, basic("bob")).status_code == 403


def test_status_view(cfg):
    req = APIRequestFactory().get("/", **AUTH)
    r = ClusterAPIStatusView.as_view()(req)
    assert r.status_code == 200
    assert r.data["tools"]["kubectl"]["available"] is True
    assert r.data["credentials"] == "in-cluster service account"


@pytest.fixture
def django_db_setup_minimal():
    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)
