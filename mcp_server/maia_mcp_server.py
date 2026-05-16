#!/usr/bin/env python3
"""
MAIA Admin MCP Server — stdio transport.

Exposes MAIA user and project management operations as MCP tools so that any
MCP-compatible client (Claude Desktop, Cursor, Windsurf, custom agents …) can
perform admin operations on a MAIA platform instance.

Usage
-----
Set the following environment variables, then run this script or reference it
in your MCP client configuration:

    MAIA_API_URL    Base URL of the MAIA Dashboard (default: http://localhost:8000)
    MAIA_API_TOKEN  DRF token for an admin user (obtain via /maia/login/jwt/ or
                    the Django admin shell: Token.objects.get_or_create(user=…))

Claude Desktop example (claude_desktop_config.json):
-----------------------------------------------------
{
  "mcpServers": {
    "maia-admin": {
      "command": "python",
      "args": ["/path/to/MAIA/mcp_server/maia_mcp_server.py"],
      "env": {
        "MAIA_API_URL": "https://maia.example.com",
        "MAIA_API_TOKEN": "<your-token>"
      }
    }
  }
}

Generic agent connection (HTTP MCP endpoint):
---------------------------------------------
The MAIA Dashboard also exposes a stateless HTTP MCP endpoint at:

    POST /maia/agent/mcp/

Send JSON-RPC 2.0 requests with method initialize / tools/list / tools/call
and the X-Agent-Token header set to your AGENT_API_TOKEN.
"""

import asyncio
import json
import os
import sys

import httpx

# ---------------------------------------------------------------------------
# MCP SDK import (optional dependency — pip install mcp)
# ---------------------------------------------------------------------------
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types as mcp_types
except ImportError:
    print(
        "ERROR: 'mcp' package not found.  Install it with:  pip install mcp",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAIA_API_URL = os.environ.get("MAIA_API_URL", "http://localhost:8000").rstrip("/")
MAIA_API_TOKEN = os.environ.get("MAIA_API_TOKEN", "")

# ---------------------------------------------------------------------------
# MCP Server definition
# ---------------------------------------------------------------------------

app = Server("maia-admin")


def _headers() -> dict:
    return {
        "Authorization": f"Token {MAIA_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Tool list
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools():
    return [
        mcp_types.Tool(
            name="list_users",
            description="List all MAIA platform users with their group/namespace assignments.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        mcp_types.Tool(
            name="create_user",
            description=(
                "Create a new MAIA user and register them in Keycloak. "
                "An invitation email with a temporary password is sent automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"},
                    "username": {
                        "type": "string",
                        "description": "Username (lowercase, no spaces)",
                    },
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "namespace": {
                        "type": "string",
                        "description": "Comma-separated group/namespace IDs to assign (optional)",
                    },
                },
                "required": ["email", "username", "first_name", "last_name"],
            },
        ),
        mcp_types.Tool(
            name="update_user",
            description="Update a MAIA user's group/namespace assignments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"},
                    "namespace": {
                        "type": "string",
                        "description": "New comma-separated list of group/namespace IDs",
                    },
                },
                "required": ["email", "namespace"],
            },
        ),
        mcp_types.Tool(
            name="delete_user",
            description="Delete a MAIA user from the platform database (and optionally Keycloak).",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"},
                    "force": {
                        "type": "boolean",
                        "description": "Also delete from Keycloak (default: false)",
                    },
                },
                "required": ["email"],
            },
        ),
        mcp_types.Tool(
            name="list_projects",
            description="List all MAIA research projects/groups with resource allocations.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        mcp_types.Tool(
            name="list_pending_projects",
            description="List projects pending admin approval.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        mcp_types.Tool(
            name="create_project",
            description=(
                "Create a new MAIA research project with a Kubernetes namespace, "
                "GPU allocation, and member users."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "string",
                        "description": (
                            "Unique project ID / Kubernetes namespace "
                            "(lowercase alphanumeric + hyphens, max 63 chars)"
                        ),
                    },
                    "gpu": {
                        "type": "string",
                        "description": "GPU allocation (e.g. '1', '2', 'none')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Project start date (YYYY-MM-DD)",
                    },
                    "memory_limit": {
                        "type": "string",
                        "description": "Memory limit (e.g. '8Gi'). Default: '2Gi'",
                    },
                    "cpu_limit": {
                        "type": "string",
                        "description": "CPU limit (e.g. '4'). Default: '2'",
                    },
                    "cluster": {
                        "type": "string",
                        "description": "Target Kubernetes cluster name",
                    },
                    "project_tier": {
                        "type": "string",
                        "description": "Project tier ('Base', 'Advanced'). Default: 'Base'",
                    },
                    "user_email": {
                        "type": "string",
                        "description": "Primary PI / owner email",
                    },
                    "email_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional member emails",
                    },
                    "supervisor": {
                        "type": "string",
                        "description": "Supervisor email (student projects)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable project description",
                    },
                },
                "required": [
                    "group_id",
                    "gpu",
                    "date",
                    "memory_limit",
                    "cpu_limit",
                    "cluster",
                    "project_tier",
                ],
            },
        ),
        mcp_types.Tool(
            name="delete_project",
            description="Delete a MAIA project, its Keycloak group, and update all member users.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "string",
                        "description": "Project/group ID (Kubernetes namespace) to delete",
                    }
                },
                "required": ["group_id"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        try:
            result = await _dispatch(client, name, arguments)
            return [mcp_types.TextContent(type="text", text=result)]
        except Exception as exc:
            error_msg = json.dumps({"error": str(exc)})
            return [mcp_types.TextContent(type="text", text=error_msg)]


async def _dispatch(client: httpx.AsyncClient, name: str, args: dict) -> str:
    base = MAIA_API_URL
    h = _headers()

    if name == "list_users":
        r = await client.get(f"{base}/maia/user-management/list-users/", headers=h)
        return json.dumps(r.json(), indent=2)

    elif name == "create_user":
        payload = {
            "email": args["email"],
            "username": args["username"],
            "first_name": args.get("first_name", ""),
            "last_name": args.get("last_name", ""),
            "namespace": args.get("namespace", ""),
        }
        r = await client.post(
            f"{base}/maia/user-management/create-user/", headers=h, json=payload
        )
        return json.dumps(r.json(), indent=2)

    elif name == "update_user":
        payload = {"email": args["email"], "namespace": args["namespace"]}
        r = await client.patch(
            f"{base}/maia/user-management/update-user/", headers=h, json=payload
        )
        return json.dumps(r.json(), indent=2)

    elif name == "delete_user":
        force = str(args.get("force", False)).lower()
        r = await client.delete(
            f"{base}/maia/user-management/delete-user/",
            headers=h,
            params={"email": args["email"], "force": force},
        )
        return json.dumps(r.json(), indent=2)

    elif name == "list_projects":
        r = await client.get(f"{base}/maia/user-management/list-groups/", headers=h)
        return json.dumps(r.json(), indent=2)

    elif name == "list_pending_projects":
        r = await client.get(
            f"{base}/maia/user-management/list-pending-groups/", headers=h
        )
        return json.dumps(r.json(), indent=2)

    elif name == "create_project":
        payload = {
            "group_id": args["group_id"],
            "gpu": args["gpu"],
            "date": args["date"],
            "memory_limit": args.get("memory_limit", "2Gi"),
            "cpu_limit": args.get("cpu_limit", "2"),
            "cluster": args["cluster"],
            "project_tier": args.get("project_tier", "Base"),
        }
        for opt in ("user_id", "email_list", "supervisor", "description"):
            if opt in args:
                payload[opt] = args[opt]
        # Map user_email → user_id for the dashboard API
        if "user_email" in args:
            payload["user_id"] = args["user_email"]
        r = await client.post(
            f"{base}/maia/user-management/create-group/", headers=h, json=payload
        )
        return json.dumps(r.json(), indent=2)

    elif name == "delete_project":
        r = await client.delete(
            f"{base}/maia/user-management/delete-group/{args['group_id']}",
            headers=h,
        )
        return json.dumps(r.json(), indent=2)

    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
