# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from apps.namespaces import views

urlpatterns = [
    path("<str:namespace_id>", views.namespace_view),
    path("<str:namespace_id>/api/pods/", views.namespace_pods_api),
    path("<str:namespace_id>/api/pods/metrics/", views.namespace_pod_metrics_api),
    path("<str:namespace_id>/api/pods/<str:pod_name>/logs/", views.namespace_pod_logs_api),
]
