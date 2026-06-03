from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.agent_api.views import (
    AgentChatView,
    AgentMattermostView,
    AgentAdminChatView,
    MCPServerView,
)

urlpatterns = [
    # Generic REST agent endpoint (token auth)
    path("chat/", csrf_exempt(AgentChatView.as_view()), name="agent_chat"),
    # Mattermost outgoing-webhook / slash-command endpoint
    path(
        "mattermost/",
        csrf_exempt(AgentMattermostView.as_view()),
        name="agent_mattermost",
    ),
    # Dashboard admin chat — session auth, CSRF protected
    path("admin-chat/", AgentAdminChatView.as_view(), name="agent_admin_chat"),
    # HTTP MCP server endpoint (JSON-RPC 2.0)
    path("mcp/", csrf_exempt(MCPServerView.as_view()), name="mcp_server"),
]
