"""
MAIA Admin Tool Definitions and Executor.

These tools are used by both the in-process Agent API (Claude tool-use loop)
and exposed via the standalone MCP server.
"""

import json
from loguru import logger
from django.conf import settings as env_settings
if env_settings.MONGO_DB_ENABLED:
    from apps.mongodb_models import MAIAUser, MAIAProject
else:
    from apps.models import MAIAUser, MAIAProject
from apps.user_management.services import (
    create_user,
    update_user,
    delete_user,
    create_group,
    delete_group,
)
from apps.authentication.views import register_user, register_project
from django.conf import settings
from django.http import HttpRequest
from MAIA.dashboard_utils import get_pending_projects


USER_TOOL_DEFINITIONS = [
    {
        "name": "request_create_user",
        "description": (
            "Request a new MAIA user to be created, and optionally assigned to a group/namespace."
            "An invitation email with a temporary password is sent automatically."
        ),
        "input_schema": {"type": "object", "properties": {
            "email": {"type": "string", "description": "User's email address"},
            "username": {"type": "string", "description": "Username (lowercase, no spaces)"},
            "namespace": {"type": "string", "description": "Comma-separated list of group/namespace IDs to assign (optional)"}},
                         "required": ["email", "username"]},
    },
    {
        "name": "request_create_project",
        "description": (
            "Request a new MAIA project to be created."
        ),
        "input_schema": {"type": "object", "properties": 
            {"namespace": {"type": "string", "description": "Project Name"},
             "gpu": {"type": "string", "description": "GPU allocation"},
             "date": {"type": "string", "description": "Project expiration date in YYYY-MM-DD format"},
             "memory_limit": {"type": "string", "description": "Memory limit (e.g. '8Gi', '16Gi'). Default: '2Gi'"},
             "cpu_limit": {"type": "string", "description": "CPU limit as a number string (e.g. '4', '8'). Default: '2'"},
             "email": {"type": "string", "description": "Primary PI / owner email address"},
             "description": {"type": "string", "description": "Human-readable project description"},
             "supervisor": {"type": "string", "description": "Supervisor email address (for student projects)"},
             "description": {"type": "string", "description": "Human-readable project description"}},
            "required": ["namespace", "gpu", "date", "memory_limit", "cpu_limit", "email"]},
    },
]

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
                "namespace": {
                    "type": "string",
                    "description": "Comma-separated list of group/namespace IDs to assign (optional)",
                },
            },
            "required": ["email", "username"],
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
        "description": "List projects that have been submitted but are pending admin approval. The admin approval is verified by the corresponding Keycloak group registration.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_project",
        "description": (
            "Create or U a new MAIA research project with a Kubernetes namespace, "
            "GPU allocation, and member users. If the project already exists, it will be updated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
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
                    "description": "Project expiration date in YYYY-MM-DD format",
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
                "email": {
                    "type": "string",
                    "description": "Primary PI / owner email address",
                },
                "users": {
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
                "memory_request": {
                    "type": "string",
                    "description": "Memory request (e.g. '8Gi', '16Gi'). Default: '2Gi'",
                },
                "cpu_request": {
                    "type": "string",
                    "description": "CPU request as a number string (e.g. '4', '8'). Default: '2'",
                },
                "auto_deploy": {
                    "type": "boolean",
                    "description": "Whether to auto-deploy the project",
                },
                "auto_deploy_apps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of apps to auto-deploy",
                },
                "project_configuration": {
                    "type": "object",
                    "description": "Project configuration",
                },
                "email_to_username_map": {
                    "type": "object",
                    "description": "Map of email to username pairs",
                },
            },
            "required": [
                "namespace"
            ],
        },
    },
    {
        "name": "delete_project",
        "description": "Delete a MAIA project, remove its Keycloak group, and update all member users.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Project/group ID (Kubernetes namespace) to delete",
                },
            },
            "required": ["namespace"],
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

OPENAI_USER_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in USER_TOOL_DEFINITIONS
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
        elif name == "request_create_user":
            request = HttpRequest()
            request.method = "POST"
            request.data = arguments
            result = register_user(request=request, api=True)
            return json.dumps({"success": result.data["success"], "msg": result.data["msg"]})
        elif name == "request_create_project":
            request = HttpRequest()
            request.method = "POST"
            request.data = arguments
            result = register_project(request=request, api=True)
            return json.dumps({"success": result.data["success"], "msg": result.data["msg"]})
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as exc:
        logger.error(f"Tool execution error [{name}]: {exc}")
        return json.dumps({"error": str(exc)})