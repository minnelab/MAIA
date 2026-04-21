"""
MAIA Admin Tool Definitions and Executor.

These tools are used by both the in-process Agent API (Claude tool-use loop)
and exposed via the standalone MCP server.
"""

import json
from loguru import logger
from apps.models import MAIAUser, MAIAProject
from apps.user_management.services import (
    create_user,
    update_user,
    delete_user,
    create_group,
    delete_group,
)
from django.conf import settings
from MAIA.dashboard_utils import get_pending_projects

# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "list_users",
        "description": "List all MAIA platform users with their group/namespace assignments.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_user",
        "description": (
            "Create a new MAIA user and register them in Keycloak. "
            "An invitation email with a temporary password is sent automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "User's email address"},
                "username": {"type": "string", "description": "Username (lowercase, no spaces)"},
                "first_name": {"type": "string", "description": "First name"},
                "last_name": {"type": "string", "description": "Last name"},
                "namespace": {
                    "type": "string",
                    "description": "Comma-separated list of group/namespace IDs to assign (optional)",
                },
            },
            "required": ["email", "username", "first_name", "last_name"],
        },
    },
    {
        "name": "update_user",
        "description": "Update a MAIA user's group/namespace assignments in both the database and Keycloak.",
        "input_schema": {
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
    },
    {
        "name": "delete_user",
        "description": "Delete a MAIA user from the platform database and optionally from Keycloak.",
        "input_schema": {
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
    },
    {
        "name": "list_projects",
        "description": "List all MAIA research projects/groups with their resource allocations.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_pending_projects",
        "description": "List projects that have been submitted but are pending admin approval.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_project",
        "description": (
            "Create a new MAIA research project with a Kubernetes namespace, "
            "GPU allocation, and member users."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": (
                        "Unique project ID used as the Kubernetes namespace "
                        "(lowercase alphanumeric and hyphens, max 63 chars)"
                    ),
                },
                "gpu": {
                    "type": "string",
                    "description": "GPU allocation (e.g. '1', '2', 'none')",
                },
                "date": {
                    "type": "string",
                    "description": "Project start date in YYYY-MM-DD format",
                },
                "memory_limit": {
                    "type": "string",
                    "description": "Memory limit (e.g. '8Gi', '16Gi'). Default: '2Gi'",
                },
                "cpu_limit": {
                    "type": "string",
                    "description": "CPU limit as a number string (e.g. '4', '8'). Default: '2'",
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
                    "description": "Primary PI / owner email address",
                },
                "email_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional user emails to add to the project",
                },
                "supervisor": {
                    "type": "string",
                    "description": "Supervisor email address (for student projects)",
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
    },
    {
        "name": "delete_project",
        "description": "Delete a MAIA project, remove its Keycloak group, and update all member users.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Project/group ID (Kubernetes namespace) to delete",
                },
            },
            "required": ["group_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------
OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOL_DEFINITIONS
]

def execute_tool(name: str, arguments: dict) -> str:
    """Execute a MAIA admin tool and return the result as a JSON string."""
    try:
        if name == "list_users":
            users = list(
                MAIAUser.objects.all().values("id", "email", "username", "namespace")
            )
            return json.dumps({"users": users, "count": len(users)}, indent=2)

        elif name == "create_user":
            result = create_user(
                email=arguments["email"],
                username=arguments["username"],
                first_name=arguments.get("first_name", ""),
                last_name=arguments.get("last_name", ""),
                namespace=arguments.get("namespace", ""),
            )
            return json.dumps(result)

        elif name == "update_user":
            result = update_user(
                email=arguments["email"],
                namespace=arguments["namespace"],
            )
            return json.dumps(result)

        elif name == "delete_user":
            result = delete_user(
                email=arguments["email"],
                force=arguments.get("force", False),
            )
            return json.dumps(result)

        elif name == "list_projects":
            projects = list(
                MAIAProject.objects.all().values(
                    "id",
                    "namespace",
                    "gpu",
                    "date",
                    "memory_limit",
                    "cpu_limit",
                    "cluster",
                    "project_tier",
                    "email",
                    "description",
                    "supervisor",
                )
            )
            return json.dumps(
                {"projects": projects, "count": len(projects)},
                indent=2,
                default=str,
            )

        elif name == "list_pending_projects":
            pending = get_pending_projects(
                settings=settings, maia_project_model=MAIAProject
            )
            return json.dumps({"pending_projects": pending}, indent=2)

        elif name == "create_project":
            result = create_group(
                group_id=arguments["group_id"],
                gpu=arguments["gpu"],
                date=arguments["date"],
                memory_limit=arguments.get("memory_limit", "2Gi"),
                cpu_limit=arguments.get("cpu_limit", "2"),
                env_file=None,
                cluster=arguments["cluster"],
                project_tier=arguments.get("project_tier", "Base"),
                user_email=arguments.get("user_email"),
                email_list=arguments.get("email_list", []),
                description=arguments.get("description"),
                supervisor=arguments.get("supervisor"),
            )
            return json.dumps(result)

        elif name == "delete_project":
            result = delete_group(group_id=arguments["group_id"])
            return json.dumps(result)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# OpenAI / Ollama function-calling format
# (wraps the same input_schema — only the key name differs)
# ---------------------------------------------------------------------------



    except Exception as exc:
        logger.error(f"Tool execution error [{name}]: {exc}")
        return json.dumps({"error": str(exc)})
