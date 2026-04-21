"""
MAIA Agent API views — multi-provider.

Supported AI providers (set via AGENT_PROVIDER env var):
  anthropic  (default) — Claude via Anthropic SDK
  openai               — GPT-4 / Azure / any OpenAI-compatible endpoint
  ollama               — local models via Ollama's OpenAI-compatible API

Endpoints
---------
POST   /maia/agent/chat/          Generic REST (token auth)
POST   /maia/agent/mattermost/    Mattermost outgoing webhook / slash command
POST   /maia/agent/admin-chat/    Dashboard chat UI (session auth, superuser only)
DELETE /maia/agent/admin-chat/    Clear session history
POST   /maia/agent/mcp/           HTTP MCP server (JSON-RPC 2.0)
"""

import json
import os

from django.conf import settings
from loguru import logger
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .tools import TOOL_DEFINITIONS, OPENAI_TOOL_DEFINITIONS, OPENAI_USER_TOOL_DEFINITIONS, execute_tool

# ---------------------------------------------------------------------------
# System prompt (shared across all providers)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are MAIA Admin Assistant, an AI agent that helps \
administrators manage the MAIA Medical-AI platform.

You have access to tools to manage users and research projects/groups.

Key concepts:
- Users: MAIA platform users stored in the database and registered in Keycloak.
- Projects/Groups: Research groups with Kubernetes namespaces, GPU quotas, \
and member users.
- Namespaces: Kubernetes namespace names, identical to the project/group ID.

Guidelines:
1. Always confirm the outcome of every operation.
2. For destructive operations (delete), briefly summarise what will be removed.
3. Format list results in a readable way (e.g. bullet lists or tables).
4. If an operation fails, explain the error clearly.
5. Keep responses concise and professional.
"""


def _build_system_prompt(username: str | None) -> str:
    """Append the operator identity to the base system prompt when known."""
    if not username:
        return SYSTEM_PROMPT
    return SYSTEM_PROMPT + f"\nYou are currently assisting the administrator: {username}."

# ---------------------------------------------------------------------------
# Configuration helper
# ---------------------------------------------------------------------------


def _get_config() -> dict:
    """
    Return a dict with all provider settings pulled from Django settings / env.

    Keys: provider, api_key, model, base_url, agent_token, is_ready
    """

    def _s(key, default=None):
        return getattr(settings, key, None) or os.environ.get(key, default) or default

    provider = _s("AGENT_PROVIDER", "anthropic").lower()
    agent_token = _s("AGENT_API_TOKEN", "")

    if provider == "openai":
        api_key = _s("OPENAI_API_KEY", "")
        model = _s("OPENAI_MODEL", "gpt-4o")
        base_url = _s("OPENAI_BASE_URL", "https://api.openai.com/v1")
        is_ready = bool(api_key)

    elif provider == "ollama":
        api_key = _s("OLLAMA_API_KEY", "ollama")  # use key if set, else dummy value
        model = _s("OLLAMA_MODEL", "llama3")
        base_url = _s("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        is_ready = True  # key is optional for local; required only for secured endpoints

    else:  # anthropic (default)
        provider = "anthropic"
        api_key = _s("ANTHROPIC_API_KEY", "")
        model = _s("AGENT_MODEL", "claude-sonnet-4-6")
        base_url = None
        is_ready = bool(api_key)

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "agent_token": agent_token,
        "is_ready": is_ready,
    }


def _not_ready_error(cfg: dict) -> str:
    if cfg["provider"] == "anthropic":
        return "ANTHROPIC_API_KEY is not configured on the server."
    if cfg["provider"] == "openai":
        return "OPENAI_API_KEY is not configured on the server."
    return f"Provider '{cfg['provider']}' is not configured."


# ---------------------------------------------------------------------------
# Anthropic agent runner
# ---------------------------------------------------------------------------


def _run_agent_anthropic(message: str, history: list, cfg: dict, username: str | None = None):
    """Agentic loop using the Anthropic SDK (Claude)."""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'anthropic' package: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=cfg["api_key"])
    messages = list(history)
    messages.append({"role": "user", "content": message})

    extra = {"metadata": {"user_id": username}} if username else {}

    while True:
        response = client.messages.create(
            model=cfg["model"],
            max_tokens=4096,
            system=_build_system_prompt(username),
            messages=messages,
            tools=TOOL_DEFINITIONS,
            **extra,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            return text, messages

        if response.stop_reason == "tool_use":
            results = []
            for b in response.content:
                if b.type == "tool_use":
                    logger.info(f"[anthropic] tool '{b.name}' args={b.input}")
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": b.id,
                            "content": execute_tool(b.name, b.input),
                        }
                    )
            messages.append({"role": "user", "content": results})
        else:
            text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            return text or "No response generated.", messages


# ---------------------------------------------------------------------------
# OpenAI-compatible agent runner  (OpenAI GPT-4, Ollama, …)
# ---------------------------------------------------------------------------


def _run_agent_openai(message: str, history: list, cfg: dict, username: str | None = None):
    """
    Agentic loop using the OpenAI SDK.

    Works with:
      - OpenAI (base_url = https://api.openai.com/v1)
      - Ollama  (base_url = http://localhost:11434/v1, api_key = 'ollama')
      - Any other OpenAI-compatible endpoint
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'openai' package: pip install openai"
        ) from exc

    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])

    # OpenAI keeps system prompt inside the messages list
    messages = [{"role": "system", "content": _build_system_prompt(username)}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    # 'user' field lets the provider attribute requests to a specific end-user
    extra = {"user": username} if username else {}

    while True:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            tools=OPENAI_USER_TOOL_DEFINITIONS,
            max_tokens=4096,
            **extra,
        )
        choice = response.choices[0]
        # Store as plain dict (always JSON-serialisable)
        messages.append(choice.message.model_dump(exclude_unset=False))

        if choice.finish_reason == "stop":
            return choice.message.content or "", messages[1:]  # strip system

        if choice.finish_reason == "tool_calls":
            for tc in (choice.message.tool_calls or []):
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                logger.info(
                    f"[openai] tool '{tc.function.name}' args={args}"
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": execute_tool(tc.function.name, args),
                    }
                )
        else:
            return choice.message.content or "No response generated.", messages[1:]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def _run_agent(message: str, history: list, cfg: dict, username: str | None = None):
    """Route to the correct provider runner and return (text, history)."""
    if cfg["provider"] == "anthropic":
        return _run_agent_anthropic(message, history, cfg, username)
    return _run_agent_openai(message, history, cfg, username)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


def _validate_token(request, agent_token: str) -> bool:
    if not agent_token:
        return True
    provided = request.headers.get("X-Agent-Token") or request.data.get("token", "")
    return provided == agent_token


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


class AgentChatView(APIView):
    """
    Generic REST agent endpoint.

    POST /maia/agent/chat/
    Headers: X-Agent-Token: <AGENT_API_TOKEN>
    Body:    {"message": "...", "history": []}
    → {"response": "...", "history": [...]}
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        cfg = _get_config()

        if not _validate_token(request, cfg["agent_token"]):
            return Response({"error": "Unauthorized"}, status=401)

        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "'message' field is required"}, status=400)

        if not cfg["is_ready"]:
            return Response({"error": _not_ready_error(cfg)}, status=503)

        history = request.data.get("history", [])

        # Use authenticated Django user when available, else accept an explicit
        # "user" field in the request body (for machine-to-machine callers).
        username = None
        if request.user.is_authenticated:
            username = request.user.email or request.user.username
        if not username:
            username = request.data.get("user") or None

        try:
            response_text, updated_history = _run_agent(message, history, cfg, username)
        except Exception as exc:
            logger.error(f"Agent error: {exc}")
            return Response({"error": str(exc)}, status=500)

        serialised = (
            _serialise_history(updated_history)
            if cfg["provider"] == "anthropic"
            else updated_history
        )
        return Response({"response": response_text, "history": serialised})


class AgentMattermostView(APIView):
    """
    Mattermost outgoing-webhook / slash-command endpoint.

    POST /maia/agent/mattermost/
    → {"text": "...", "response_type": "in_channel"}
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        cfg = _get_config()

        provided_token = request.data.get("token", "")
        if cfg["agent_token"] and provided_token != cfg["agent_token"]:
            return Response({"text": "Unauthorized: invalid token."})

        raw_text = request.data.get("text", "").strip()
        command = request.data.get("command", "").strip()
        if command and raw_text.startswith(command):
            raw_text = raw_text[len(command):].strip()

        if not raw_text:
            help_text = (
                "**MAIA Admin Assistant** — available operations:\n"
                "- List all users / projects\n"
                "- Create / update / delete a user\n"
                "- Create / delete a project\n"
                "- List pending project approvals\n\n"
                "Example: `list all users`"
            )
            return Response({"text": help_text, "response_type": "ephemeral"})

        if not cfg["is_ready"]:
            return Response(
                {
                    "text": f"MAIA Agent is not configured ({_not_ready_error(cfg)})",
                    "response_type": "ephemeral",
                }
            )

        # Mattermost sends user_name and user_email in the webhook payload
        username = request.data.get("user_email") or request.data.get("user_name") or None

        try:
            response_text, _ = _run_agent(raw_text, [], cfg, username)
        except Exception as exc:
            logger.error(f"Mattermost agent error: {exc}")
            return Response({"text": f"Error: {exc}", "response_type": "ephemeral"})

        return Response({"text": response_text, "response_type": "in_channel"})


class AgentAdminChatView(APIView):
    """
    Session-based chat endpoint for the dashboard admin chat UI.

    Requires Django session auth + superuser — no extra token needed.

    POST   /maia/agent/admin-chat/  {"message": "..."}
    DELETE /maia/agent/admin-chat/  (clear conversation)
    """

    permission_classes = [AllowAny]
    SESSION_KEY = "agent_chat_history"

    def _require_admin(self, request):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return Response({"error": "Admin login required"}, status=403)
        return None

    def post(self, request, *args, **kwargs):
        deny = self._require_admin(request)
        if deny:
            return deny

        cfg = _get_config()
        if not cfg["is_ready"]:
            return Response({"error": _not_ready_error(cfg)}, status=503)

        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "'message' field is required"}, status=400)

        history = request.session.get(self.SESSION_KEY, [])

        # Use email if set, fall back to username — always non-empty for superusers
        username = request.user.email or request.user.username

        try:
            response_text, updated_history = _run_agent(message, history, cfg, username)
        except Exception as exc:
            logger.error(f"Admin chat agent error [{username}]: {exc}")
            return Response({"error": str(exc)}, status=500)

        serialised = (
            _serialise_history(updated_history)
            if cfg["provider"] == "anthropic"
            else updated_history
        )
        request.session[self.SESSION_KEY] = serialised
        request.session.modified = True

        return Response(
            {
                "response": response_text,
                "history_length": len(serialised),
            }
        )

    def delete(self, request, *args, **kwargs):
        deny = self._require_admin(request)
        if deny:
            return deny
        request.session.pop(self.SESSION_KEY, None)
        request.session.modified = True
        return Response({"cleared": True})


# ---------------------------------------------------------------------------
# Anthropic history serialiser (converts SDK objects → plain dicts)
# ---------------------------------------------------------------------------


def _serialise_history(history: list) -> list:
    serialisable = []
    for msg in history:
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        content = (
            msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        )
        if isinstance(content, str):
            serialisable.append({"role": role, "content": content})
        elif isinstance(content, list):
            clean = []
            for block in content:
                if isinstance(block, dict):
                    clean.append(block)
                elif hasattr(block, "type"):
                    b = {"type": block.type}
                    for attr in ("text", "id", "name", "input", "tool_use_id", "content"):
                        if hasattr(block, attr):
                            b[attr] = getattr(block, attr)
                    clean.append(b)
            serialisable.append({"role": role, "content": clean})
    return serialisable


# ---------------------------------------------------------------------------
# HTTP MCP server (JSON-RPC 2.0)
# ---------------------------------------------------------------------------


class MCPServerView(APIView):
    """
    Stateless HTTP MCP endpoint.

    Methods: initialize, tools/list, tools/call
    Auth:    X-Agent-Token header or ?token= query param
    """

    permission_classes = [AllowAny]

    _MCP_TOOLS = [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["input_schema"],
        }
        for t in TOOL_DEFINITIONS
    ]

    def post(self, request, *args, **kwargs):
        cfg = _get_config()

        provided = request.headers.get("X-Agent-Token") or request.query_params.get(
            "token", ""
        )
        if cfg["agent_token"] and provided != cfg["agent_token"]:
            return Response(
                {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}, "id": None},
                status=401,
            )

        try:
            body = request.data
            rpc_id = body.get("id")
            method = body.get("method", "")
            params = body.get("params", {})
        except Exception:
            return Response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}
            )

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "maia-admin", "version": "1.0.0"},
            }

        elif method == "tools/list":
            result = {"tools": self._MCP_TOOLS}

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            if not tool_name:
                return Response(
                    {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing 'name'"}, "id": rpc_id}
                )
            result = {
                "content": [{"type": "text", "text": execute_tool(tool_name, tool_args)}],
                "isError": False,
            }

        else:
            return Response(
                {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method}"}, "id": rpc_id}
            )

        return Response({"jsonrpc": "2.0", "result": result, "id": rpc_id})
