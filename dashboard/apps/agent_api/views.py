"""
MAIA Agent API views.

Provides two HTTP endpoints:

1. POST /maia/agent/chat/
   Generic REST endpoint — accepts {"message": "...", "history": [...]}
   and returns {"response": "...", "history": [...]}.

2. POST /maia/agent/mattermost/
   Mattermost-compatible endpoint — accepts the standard outgoing-webhook
   payload and returns {"text": "...", "response_type": "in_channel"}.

Both endpoints require the X-Agent-Token header (or "token" field in the
body) to match the AGENT_API_TOKEN setting.

The agent uses Claude with MAIA admin tools to perform user/project
management operations on behalf of the requester.
"""

import json
import os

from django.conf import settings
from loguru import logger
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .tools import TOOL_DEFINITIONS, execute_tool

# ---------------------------------------------------------------------------
# Agent runner
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


def _run_agent(message: str, history: list, model: str, api_key: str):
    """
    Run the Claude agentic loop with MAIA admin tools.

    Returns (response_text: str, updated_history: list).
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "The 'anthropic' package is required for the Agent API. "
            "Install it with: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)

    messages = list(history)
    messages.append({"role": "user", "content": message})

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )

        # Append the raw assistant message to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return text, messages

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(
                        f"Agent calling tool '{block.name}' with args: {block.input}"
                    )
                    result = execute_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason — return whatever text we have
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return text or "No response generated.", messages


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_config():
    """Return (api_key, model, agent_token) from settings / env."""
    api_key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.environ.get(
        "ANTHROPIC_API_KEY", ""
    )
    model = getattr(settings, "AGENT_MODEL", None) or os.environ.get(
        "AGENT_MODEL", "claude-sonnet-4-6"
    )
    agent_token = getattr(settings, "AGENT_API_TOKEN", None) or os.environ.get(
        "AGENT_API_TOKEN", ""
    )
    return api_key, model, agent_token


def _validate_token(request, agent_token: str) -> bool:
    """Return True if the request carries a valid agent token."""
    if not agent_token:
        # No token configured → open access (development only)
        return True
    provided = request.headers.get("X-Agent-Token") or request.data.get("token", "")
    return provided == agent_token


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


class AgentChatView(APIView):
    """
    Generic REST chat endpoint.

    Request body (JSON):
        {
            "message": "Create a user alice@example.com ...",
            "history": []        # optional conversation history
        }

    Response (JSON):
        {
            "response": "...",
            "history": [...]
        }
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        api_key, model, agent_token = _get_config()

        if not _validate_token(request, agent_token):
            return Response({"error": "Unauthorized"}, status=401)

        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "'message' field is required"}, status=400)

        if not api_key:
            return Response(
                {"error": "ANTHROPIC_API_KEY is not configured on the server"},
                status=503,
            )

        history = request.data.get("history", [])

        try:
            response_text, updated_history = _run_agent(
                message, history, model, api_key
            )
        except Exception as exc:
            logger.error(f"Agent error: {exc}")
            return Response({"error": str(exc)}, status=500)

        return Response({"response": response_text, "history": updated_history})


class AgentMattermostView(APIView):
    """
    Mattermost-compatible outgoing webhook / slash-command endpoint.

    Mattermost sends application/x-www-form-urlencoded or JSON with fields:
        token, team_id, channel_id, channel_name, user_id, user_name,
        command, text, response_url, trigger_id

    This view validates the Mattermost token, strips the slash-command trigger
    word if present, runs the agent, and returns the Mattermost response format:

        {"text": "...", "response_type": "in_channel"}
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        api_key, model, agent_token = _get_config()

        # Mattermost passes the integration token in the 'token' body field
        provided_token = request.data.get("token", "")
        if agent_token and provided_token != agent_token:
            return Response({"text": "Unauthorized: invalid token."})

        # Extract the user text — strip the slash-command name if present
        raw_text = request.data.get("text", "").strip()
        command = request.data.get("command", "").strip()  # e.g. "/maia-admin"
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

        if not api_key:
            return Response(
                {
                    "text": "MAIA Agent is not configured (missing ANTHROPIC_API_KEY).",
                    "response_type": "ephemeral",
                }
            )

        try:
            response_text, _ = _run_agent(raw_text, [], model, api_key)
        except Exception as exc:
            logger.error(f"Mattermost agent error: {exc}")
            return Response(
                {"text": f"Error: {exc}", "response_type": "ephemeral"}
            )

        return Response({"text": response_text, "response_type": "in_channel"})


# ---------------------------------------------------------------------------
# MCP Server — HTTP/SSE transport (JSON-RPC 2.0)
# ---------------------------------------------------------------------------


class AgentAdminChatView(APIView):
    """
    Session-based chat endpoint for the dashboard admin chat UI.

    Requires the requesting user to be authenticated AND a superuser —
    no extra token needed because the Django session already proves identity.

    POST /maia/agent/admin-chat/
        {"message": "..."}
        → {"response": "...", "history_length": N}

    DELETE /maia/agent/admin-chat/   (clear conversation)
        → {"cleared": true}
    """

    permission_classes = [AllowAny]  # auth enforced manually below

    SESSION_KEY = "agent_chat_history"

    def _require_admin(self, request):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return Response({"error": "Admin login required"}, status=403)
        return None

    def post(self, request, *args, **kwargs):
        deny = self._require_admin(request)
        if deny:
            return deny

        api_key, model, _ = _get_config()
        if not api_key:
            return Response(
                {"error": "ANTHROPIC_API_KEY is not configured on the server"},
                status=503,
            )

        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "'message' field is required"}, status=400)

        # Load history from session (contains only JSON-serialisable content)
        history = request.session.get(self.SESSION_KEY, [])

        try:
            response_text, updated_history = _run_agent(
                message, history, model, api_key
            )
        except Exception as exc:
            logger.error(f"Admin chat agent error: {exc}")
            return Response({"error": str(exc)}, status=500)

        # Persist only the serialisable portions (strings/dicts, not SDK objects)
        request.session[self.SESSION_KEY] = _serialise_history(updated_history)
        request.session.modified = True

        return Response(
            {
                "response": response_text,
                "history_length": len(request.session[self.SESSION_KEY]),
            }
        )

    def delete(self, request, *args, **kwargs):
        deny = self._require_admin(request)
        if deny:
            return deny
        request.session.pop(self.SESSION_KEY, None)
        request.session.modified = True
        return Response({"cleared": True})


def _serialise_history(history: list) -> list:
    """
    Convert a message list that may contain Anthropic SDK objects into plain
    JSON-serialisable dicts so they can be stored in the Django session.
    """
    serialisable = []
    for msg in history:
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)

        if isinstance(content, str):
            serialisable.append({"role": role, "content": content})
        elif isinstance(content, list):
            clean_blocks = []
            for block in content:
                if isinstance(block, dict):
                    clean_blocks.append(block)
                elif hasattr(block, "type"):
                    b = {"type": block.type}
                    if hasattr(block, "text"):
                        b["text"] = block.text
                    if hasattr(block, "id"):
                        b["id"] = block.id
                    if hasattr(block, "name"):
                        b["name"] = block.name
                    if hasattr(block, "input"):
                        b["input"] = block.input
                    if hasattr(block, "tool_use_id"):
                        b["tool_use_id"] = block.tool_use_id
                    if hasattr(block, "content"):
                        b["content"] = block.content
                    clean_blocks.append(b)
            serialisable.append({"role": role, "content": clean_blocks})
        # Skip messages with non-serialisable content silently
    return serialisable


class MCPServerView(APIView):
    """
    Minimal MCP server implemented over plain HTTP (JSON-RPC 2.0 subset).

    Supports the three MCP methods needed by clients:
        initialize   → returns server capabilities
        tools/list   → returns TOOL_DEFINITIONS in MCP schema format
        tools/call   → executes a tool and returns the result

    Authentication: X-Agent-Token header or 'token' query parameter.

    This endpoint is designed for lightweight integrations.  For full MCP
    stdio transport, use the standalone mcp_server/maia_mcp_server.py script.
    """

    permission_classes = [AllowAny]

    # MCP tool schema format differs slightly from Anthropic — convert once
    _MCP_TOOLS = [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["input_schema"],
        }
        for t in TOOL_DEFINITIONS
    ]

    def post(self, request, *args, **kwargs):
        _, _, agent_token = _get_config()

        # Allow token via header OR query param for MCP clients
        provided = request.headers.get("X-Agent-Token") or request.query_params.get(
            "token", ""
        )
        if agent_token and provided != agent_token:
            return Response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32001, "message": "Unauthorized"},
                    "id": None,
                },
                status=401,
            )

        try:
            body = request.data
            rpc_id = body.get("id")
            method = body.get("method", "")
            params = body.get("params", {})
        except Exception:
            return Response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None,
                }
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
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": "Missing 'name' in params",
                        },
                        "id": rpc_id,
                    }
                )
            raw_result = execute_tool(tool_name, tool_args)
            result = {
                "content": [{"type": "text", "text": raw_result}],
                "isError": False,
            }

        else:
            return Response(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                    "id": rpc_id,
                }
            )

        return Response({"jsonrpc": "2.0", "result": result, "id": rpc_id})
