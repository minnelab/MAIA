"""
MAIA Cluster API — run ``kubectl`` / ``helm`` through the dashboard.

The dashboard runs inside the cluster with admin privileges; this API exposes
that access to external automation. It is **disabled by default** and must be
switched on explicitly (``CLUSTER_API_ENABLED=True``).

Endpoints
---------
GET  /maia/cluster-api/       Status: enabled?, available tools, versions
POST /maia/cluster-api/exec/  Run a command

Authentication (any of):
  * ``Authorization: Bearer <CLUSTER_API_TOKEN>``  or  ``X-Cluster-Api-Token: <CLUSTER_API_TOKEN>``
  * A Django **superuser** authenticated with the dashboard's standard REST
    authentication (DRF token, basic auth or Keycloak JWT).

Request body for ``exec``::

    {"tool": "kubectl", "args": ["get", "pods", "-A"]}
    {"command": "helm list -A"}
    {"command": "kubectl apply -f -", "stdin": "<yaml manifest>"}
    optional: "timeout": <seconds>   (capped by CLUSTER_API_MAX_TIMEOUT)
"""

from __future__ import annotations

import hmac
import os

from django.conf import settings
from loguru import logger
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .executor import (
    SUPPORTED_TOOLS,
    CommandRejected,
    parse_request,
    redact_command,
    resolve_binary,
    run_command,
)


def _setting(name, default=None):
    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name)
    return default if value is None else value


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _get_config() -> dict:
    tools_raw = _setting("CLUSTER_API_ALLOWED_TOOLS", ",".join(SUPPORTED_TOOLS))
    if isinstance(tools_raw, str):
        tools_raw = [t.strip() for t in tools_raw.split(",")]
    tools = tuple(t for t in tools_raw if t in SUPPORTED_TOOLS)
    return {
        "enabled": _as_bool(_setting("CLUSTER_API_ENABLED", False)),
        "token": _setting("CLUSTER_API_TOKEN", "") or "",
        "allow_superusers": _as_bool(_setting("CLUSTER_API_ALLOW_SUPERUSERS", True)),
        "allowed_tools": tools,
        "default_timeout": float(_setting("CLUSTER_API_DEFAULT_TIMEOUT", 60)),
        "max_timeout": float(_setting("CLUSTER_API_MAX_TIMEOUT", 300)),
        "max_output_chars": int(_setting("CLUSTER_API_MAX_OUTPUT_CHARS", 1_000_000)),
        "max_stdin_chars": int(_setting("CLUSTER_API_MAX_STDIN_CHARS", 5_000_000)),
        "kubeconfig": _setting("CLUSTER_API_KUBECONFIG", "") or None,
        "binaries": {
            "kubectl": _setting("CLUSTER_API_KUBECTL_PATH", "") or "",
            "helm": _setting("CLUSTER_API_HELM_PATH", "") or "",
        },
    }


def _client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "?")


def _authenticate(request, cfg: dict) -> tuple[str | None, Response | None]:
    """Return ``(caller identity, None)`` on success or ``(None, error response)``."""
    auth_header = request.headers.get("Authorization", "")
    provided = request.headers.get("X-Cluster-Api-Token", "")
    if not provided and auth_header.lower().startswith("bearer "):
        provided = auth_header[7:].strip()

    if cfg["token"] and provided and hmac.compare_digest(provided.encode(), cfg["token"].encode()):
        return "cluster-api-token", None

    # Fall back to the dashboard's standard DRF authentication (token / basic / Keycloak).
    # A Bearer value that is not the cluster token may be a Keycloak JWT, so only
    # attempt this when the shared-token check did not match.
    if cfg["allow_superusers"]:
        try:
            user = request.user
        except Exception:  # authentication backend raised (e.g. invalid JWT)
            user = None
        if user is not None and user.is_authenticated:
            if user.is_superuser:
                return f"superuser:{getattr(user, 'email', '') or user.get_username()}", None
            return None, Response({"error": "Superuser privileges required."}, status=403)

    return None, Response({"error": "Authentication required."}, status=401)


class ClusterAPIThrottle(SimpleRateThrottle):
    """
    Per-client-IP rate limit (``CLUSTER_API_RATE``, default ``600/hour``).

    Keyed on IP rather than user so it never triggers DRF authentication
    before the shared cluster token has been checked.
    """

    scope = "cluster_api"

    def get_rate(self):
        return _setting("CLUSTER_API_RATE", "600/hour")

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class _ClusterAPIBase(APIView):
    # Authentication is handled manually in _authenticate() so the shared
    # cluster token works even though it isn't a DRF/Keycloak token. DRF auth
    # classes still run lazily when request.user is accessed.
    permission_classes = [AllowAny]
    throttle_classes = [ClusterAPIThrottle]

    def initial(self, request, *args, **kwargs):
        self.cfg = _get_config()
        super().initial(request, *args, **kwargs)

    def perform_authentication(self, request):
        # Defer: don't let a non-DRF bearer token (the cluster token) raise 401 up-front.
        pass

    def _guard(self, request):
        if not self.cfg["enabled"]:
            return None, Response({"error": "The Cluster API is disabled on this dashboard."}, status=404)
        if not self.cfg["token"] and not self.cfg["allow_superusers"]:
            return None, Response({"error": "The Cluster API has no authentication method configured."}, status=503)
        return _authenticate(request, self.cfg)


class ClusterAPIStatusView(_ClusterAPIBase):
    """GET /maia/cluster-api/ — report available tools and client versions."""

    def get(self, request, *args, **kwargs):
        caller, deny = self._guard(request)
        if deny:
            return deny

        version_args = {"kubectl": ["version", "--client", "-o", "json"], "helm": ["version", "--short"]}
        tools = {}
        for tool in self.cfg["allowed_tools"]:
            try:
                resolve_binary(tool, self.cfg["binaries"])
                res = run_command(tool, version_args[tool], timeout=15, binaries=self.cfg["binaries"])
                tools[tool] = {"available": True, "version": res.stdout.strip() or res.stderr.strip()}
            except FileNotFoundError as exc:
                tools[tool] = {"available": False, "error": str(exc)}

        return Response(
            {
                "enabled": True,
                "caller": caller,
                "tools": tools,
                "credentials": "kubeconfig" if self.cfg["kubeconfig"] else "in-cluster service account",
                "default_timeout": self.cfg["default_timeout"],
                "max_timeout": self.cfg["max_timeout"],
            }
        )


class ClusterAPIExecView(_ClusterAPIBase):
    """POST /maia/cluster-api/exec/ — run a kubectl / helm command."""

    def post(self, request, *args, **kwargs):
        caller, deny = self._guard(request)
        if deny:
            return deny

        cfg = self.cfg
        data = request.data if isinstance(request.data, dict) else {}

        try:
            tool, cmd_args = parse_request(data, cfg["allowed_tools"])
        except CommandRejected as exc:
            return Response({"error": str(exc)}, status=400)

        stdin = data.get("stdin")
        if stdin is not None:
            if not isinstance(stdin, str):
                return Response({"error": "'stdin' must be a string."}, status=400)
            if len(stdin) > cfg["max_stdin_chars"]:
                return Response({"error": f"'stdin' exceeds {cfg['max_stdin_chars']} characters."}, status=413)

        try:
            timeout = float(data.get("timeout", cfg["default_timeout"]))
        except (TypeError, ValueError):
            return Response({"error": "'timeout' must be a number of seconds."}, status=400)
        if timeout <= 0:
            return Response({"error": "'timeout' must be positive."}, status=400)
        timeout = min(timeout, cfg["max_timeout"])

        printable = redact_command(tool, cmd_args)
        logger.info(f"[cluster-api] caller={caller} ip={_client_ip(request)} cmd={printable}")

        try:
            result = run_command(
                tool,
                cmd_args,
                stdin=stdin,
                timeout=timeout,
                max_output_chars=cfg["max_output_chars"],
                kubeconfig=cfg["kubeconfig"],
                binaries=cfg["binaries"],
            )
        except FileNotFoundError as exc:
            return Response({"error": str(exc)}, status=501)
        except Exception as exc:  # pragma: no cover - unexpected OS errors
            logger.exception(f"[cluster-api] execution failed: {exc}")
            return Response({"error": f"Execution failed: {exc}"}, status=500)

        logger.info(
            f"[cluster-api] caller={caller} cmd={printable} exit={result.exit_code} "
            f"timed_out={result.timed_out} duration={result.duration_seconds}s"
        )
        # 200 even on non-zero exit: the API call itself succeeded; check "ok"/"exit_code".
        return Response(result.to_dict(), status=200 if not result.timed_out else 504)
