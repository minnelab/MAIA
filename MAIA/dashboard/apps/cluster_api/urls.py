from apps.cluster_api.views import ClusterAPIExecView, ClusterAPIStatusView
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # Status / available tools (token or superuser auth)
    path("", csrf_exempt(ClusterAPIStatusView.as_view()), name="cluster_api_status"),
    # Run a kubectl / helm command (token or superuser auth)
    path("exec/", csrf_exempt(ClusterAPIExecView.as_view()), name="cluster_api_exec"),
]
