"""
Safe execution of ``kubectl`` / ``helm`` commands for the Cluster API.

This module is deliberately free of Django imports so it can be unit-tested
in isolation. The view layer is responsible for authentication; this layer is
responsible for:

* only ever running the configured binaries (never an arbitrary program),
* never going through a shell (arguments are passed as an argv list, so shell
  metacharacters such as ``;``, ``|``, ``$(...)`` have no special meaning),
* rejecting interactive / never-ending sub-commands that would hang a worker,
* enforcing a timeout and an output size cap,
* redacting obvious secrets before commands are written to the audit log.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field

SUPPORTED_TOOLS = ("kubectl", "helm")

# Sub-commands that need a TTY or never terminate on their own.
BLOCKED_SUBCOMMANDS = {
    "kubectl": {"edit", "proxy", "port-forward", "attach"},
    "helm": set(),
}

# Short flags such as ``-i``/``-t``/``-w``/``-f`` mean different things for
# different kubectl sub-commands (``-f`` is ``--filename`` for ``apply`` but
# ``--follow`` for ``logs``), so they are only rejected for the sub-commands
# where they would request a TTY, a stdin stream or an endless watch.
_INTERACTIVE_KUBECTL_SUBCOMMANDS = {"exec", "run", "debug"}
_WATCH_KUBECTL_SUBCOMMANDS = {"get", "rollout", "events"}

# Flags whose *value* should be masked in audit logs.
_SENSITIVE_FLAG_RE = re.compile(
    r"^(--from-literal|--password|--token|--client-key|--set|--set-string|--docker-password|--pass|--username)(=.*)?$"
)


class CommandRejected(ValueError):
    """Raised when a request is syntactically invalid or not allowed."""


@dataclass
class ExecutionResult:
    tool: str
    args: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    truncated: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("extra")
        data["ok"] = self.ok
        data["command"] = redact_command(self.tool, self.args)
        return data


def parse_request(payload: dict, allowed_tools: tuple[str, ...] = SUPPORTED_TOOLS) -> tuple[str, list[str]]:
    """
    Normalise a request body into ``(tool, args)``.

    Accepted forms::

        {"tool": "kubectl", "args": ["get", "pods", "-A"]}
        {"command": "kubectl get pods -A"}
        {"tool": "helm", "command": "list -A"}
    """
    if not isinstance(payload, dict):
        raise CommandRejected("Request body must be a JSON object.")

    tool = payload.get("tool")
    args = payload.get("args")
    command = payload.get("command")

    if args is not None and command is not None:
        raise CommandRejected("Provide either 'args' or 'command', not both.")

    if command is not None:
        if not isinstance(command, str) or not command.strip():
            raise CommandRejected("'command' must be a non-empty string.")
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            raise CommandRejected(f"Could not parse 'command': {exc}") from exc
        if tool is None:
            if not tokens:
                raise CommandRejected("'command' is empty.")
            tool, tokens = tokens[0], tokens[1:]
        elif tokens and tokens[0] == tool:
            tokens = tokens[1:]
        args = tokens
    elif args is None:
        raise CommandRejected("Either 'args' (list) or 'command' (string) is required.")

    if not isinstance(tool, str) or tool not in allowed_tools:
        raise CommandRejected(f"'tool' must be one of: {', '.join(allowed_tools)}.")
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise CommandRejected("'args' must be a list of strings.")
    if any("\x00" in a for a in args):
        raise CommandRejected("Arguments must not contain NUL bytes.")

    validate_args(tool, args)
    return tool, args


def _subcommand(args: list[str]) -> str | None:
    for a in args:
        if not a.startswith("-"):
            return a
    return None


def validate_args(tool: str, args: list[str]) -> None:
    """Reject sub-commands / flags that would block a worker indefinitely."""
    sub = _subcommand(args)
    if sub in BLOCKED_SUBCOMMANDS.get(tool, set()):
        raise CommandRejected(f"'{tool} {sub}' is interactive or long-running and is not supported.")

    if tool == "kubectl":
        flags = {a.split("=", 1)[0] for a in args if a.startswith("-")}
        if sub in _INTERACTIVE_KUBECTL_SUBCOMMANDS:
            bad = flags & {"-it", "-ti", "-t", "--tty", "-i", "--stdin", "--attach"}
            if bad:
                raise CommandRejected(f"Interactive flags {sorted(bad)} are not supported (no TTY available).")
        if sub in _WATCH_KUBECTL_SUBCOMMANDS:
            bad = flags & {"-w", "--watch", "--watch-only"}
            if bad:
                raise CommandRejected(f"Watch flags {sorted(bad)} are not supported.")
        if sub == "logs":
            bad = flags & {"-f", "--follow"}
            if bad:
                raise CommandRejected("'kubectl logs --follow' is not supported; use --tail / --since instead.")


def redact_command(tool: str, args: list[str]) -> str:
    """Return a printable command line with sensitive flag values masked."""
    out: list[str] = []
    mask_next = False
    for a in args:
        if mask_next:
            out.append("***")
            mask_next = False
            continue
        m = _SENSITIVE_FLAG_RE.match(a)
        if m:
            if m.group(2):
                out.append(f"{m.group(1)}=***")
            else:
                out.append(a)
                mask_next = True
            continue
        out.append(a)
    return shlex.join([tool, *out])


def build_env(kubeconfig: str | None) -> dict:
    """
    Build the child-process environment.

    Other dashboard views temporarily point ``KUBECONFIG`` at per-project
    kubeconfig files (process-wide), so we never inherit it blindly: either we
    use the explicitly configured kubeconfig, or we drop it so kubectl/helm fall
    back to the pod's in-cluster service-account credentials.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("KUBECONFIG",)}
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig
    env.setdefault("HOME", "/tmp")  # helm needs a writable cache/config dir
    return env


def resolve_binary(tool: str, binaries: dict[str, str] | None = None) -> str:
    path = (binaries or {}).get(tool) or shutil.which(tool)
    if not path:
        raise FileNotFoundError(f"'{tool}' binary not found on the dashboard server.")
    return path


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if limit and len(text) > limit:
        return text[:limit] + f"\n... [truncated, {len(text) - limit} more characters]", True
    return text, False


def run_command(
    tool: str,
    args: list[str],
    *,
    stdin: str | None = None,
    timeout: float = 60,
    max_output_chars: int = 1_000_000,
    kubeconfig: str | None = None,
    binaries: dict[str, str] | None = None,
) -> ExecutionResult:
    """Execute ``tool args...`` without a shell and capture the result."""
    binary = resolve_binary(tool, binaries)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [binary, *args],
            input=stdin if stdin is not None else None,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=build_env(kubeconfig),
            shell=False,
            check=False,
        )
        exit_code, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:

        def _s(v):
            return v.decode(errors="replace") if isinstance(v, bytes) else (v or "")

        exit_code, stdout, timed_out = None, _s(exc.stdout), True
        stderr = _s(exc.stderr) + f"\nCommand timed out after {timeout} seconds."
    duration = round(time.monotonic() - start, 3)

    stdout, t1 = _truncate(stdout, max_output_chars)
    stderr, t2 = _truncate(stderr, max_output_chars)
    return ExecutionResult(
        tool=tool,
        args=args,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        timed_out=timed_out,
        truncated=t1 or t2,
    )
